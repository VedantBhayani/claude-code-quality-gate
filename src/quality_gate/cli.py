"""`python -m quality_gate`: the gate's command line.

  sample   draw the natural sample, ambiguous subset and Opus subset (+ optional pilot set)
  pilot    day-1 pilot: --probes (flag probe + old-Haiku probe), or --model haiku|sonnet|opus
  run      full Part A runs on the samples (resumable; stops on rate limit / billing)
  gate     Part A results (--part a, default) or Part B copy-check results (--part b)
  gift     the 50-account gift (CSV + HTML)
  drafts   Part B: one copy-frameworks draft per gift account plus up to 10 more

pilot, run and drafts are the only commands that call a model, always through the
runner's invocation interface (ClaudeCli in production, FakeInvoker in tests).
Default paths are relative to builds/quality-gate/.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence, TextIO

from quality_gate import gate
from quality_gate.config import PACKAGE_ROOT, Config, MissingFactError, load_config
from quality_gate.labels import SheetError, load_posts
from quality_gate.types import answering_models_of
from quality_gate.runner import (
    DRAFT_OUTPUT_SCHEMA,
    AuthMethodError,
    BatchResult,
    ClaudeCli,
    Invoker,
    ResumeTooEarlyError,
    RunJob,
    RunSettings,
    draft_prompt,
    read_offer_wording,
    read_run_log,
    run_batch,
    signal_jobs,
    signal_prompt,
)
from quality_gate.sampler import draw_samples, fresh_per_company
from quality_gate.skill_rules import prepare_skill

R = PACKAGE_ROOT
DEFAULTS = {
    "posts": R / "data" / "posts" / "posts.jsonl",
    "samples": R / "data" / "samples" / "samples.json",
    "labels": R / "evals" / "fixtures" / "labels_pass1.csv",
    "relabel": R / "evals" / "fixtures" / "labels_relabel.csv",
    "runs": R / "evals" / "results" / "runs" / "runs.jsonl",
    "pilot_dir": R / "evals" / "results" / "pilot",
    "drafts": R / "evals" / "results" / "drafts" / "drafts.jsonl",
    "part_a": R / "evals" / "results" / "part-a",
    "part_b": R / "evals" / "results" / "part-b",
    "gift": R / "evals" / "results" / "gift",
    "signal_skill": R / "evals" / "skills" / "intent-signals" / "SKILL.md",
    "copy_skill": R / "evals" / "skills" / "copy-frameworks" / "SKILL.md",
    "offer": R / "config" / "facts" / "offer.md",
    "schema": R / "src" / "quality_gate" / "schemas" / "signal_output.schema.json",
}

PILOT_SEED = 20261026  # pilot set draw (gate.toml [seeds] has no pilot entry)
MODEL_ALIASES = {"haiku": "haiku-5-5", "sonnet": "sonnet-5-5", "opus": "opus-5-5"}
# Pilot: 20 runs per model. Haiku/Sonnet: 10 pilot posts x 2 repeats; Opus: 20 x 1.
PILOT_PLAN = {"haiku-5-5": (10, 2), "sonnet-5-5": (10, 2), "opus-5-5": (20, 1)}
# Flag probe ladder (02a section 3): the first variant that still returns structured
# output is the one the pilot recommends. None = flag not passed.
PROBE_LADDER: tuple[tuple[str | None, int | None], ...] = (("", 1), ("", 2), (None, 2))
PROBE_ARM_MODEL = "haiku-5-5"
OLD_HAIKU_ARM = "haiku-4-5"

EXIT_OK, EXIT_INPUT, EXIT_SETUP, EXIT_STOPPED = 0, 1, 2, 3


class _Ctx:
    def __init__(self, cfg: Config, out: TextIO, invoker: Invoker | None, ask: Callable[[str], str],
                 now: datetime | None):
        self.cfg, self.out, self._invoker, self.ask, self.now = cfg, out, invoker, ask, now
        self.max_five_hour: float | None = None  # plan-utilization caps for model batches (0..1)
        self.max_seven_day: float | None = None

    @property
    def invoker(self) -> Invoker:
        if self._invoker is None:
            self._invoker = ClaudeCli()
        return self._invoker

    def say(self, text: str = "") -> None:
        print(text, file=self.out)


# ---------------------------------------------------------------- helpers


def _schema(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _arm(cfg: Config, name: str) -> dict[str, Any]:
    for a in [*cfg.gate["arms"], *cfg.gate.get("candidate_arms", [])]:
        if a["name"] == name:
            return a
    raise MissingFactError(f"no arm named {name!r} in config/gate.toml")


def _signal_prompt_for(offer_path: Path):
    offer = read_offer_wording(offer_path)
    return lambda post: signal_prompt(post, offer)


def _batch(ctx: _Ctx, jobs: Sequence[RunJob], log: Path, settings: RunSettings, parallel: int,
           max_runs: int | None = None) -> BatchResult:
    if max_runs is not None:
        done = read_run_log(log).completed_keys()
        jobs = [j for j in jobs if j.key not in done][:max_runs]
    return run_batch(jobs, invoker=ctx.invoker, log_path=log, settings=settings, now=ctx.now, parallel=parallel,
                     max_five_hour=ctx.max_five_hour, max_seven_day=ctx.max_seven_day)


def _report_batch(ctx: _Ctx, result: BatchResult, log: Path) -> int:
    pinned = gate.pinned_models(ctx.cfg)
    failed = sum(r.structured_output is None for r in result.records)
    switched = [r for r in result.records if pinned.get(r.arm) and answering_models_of(r) != (pinned[r.arm],)]
    if result.launch_failures:
        ctx.say(f"{len(result.launch_failures)} calls exited before claude started; not recorded, they run again next time")
    ctx.say(f"{len(result.records)} runs completed ({failed} recorded as failed), "
            f"{len(result.skipped)} already done; CLI {result.cli_version}; log: {log}")
    for r in switched:
        ctx.say(f"FLAG model mismatch: {r.post_id} / {r.arm} / repeat {r.repeat}: answer written by "
                f"{', '.join(answering_models_of(r)) or 'unconfirmed'} (modelUsage {', '.join(r.model_usage_keys) or 'empty'}; "
                f"pinned {pinned[r.arm]}); the gate will exclude it")
    stop = result.stop
    if stop is None:
        return EXIT_OK
    if stop.reason == "budget":
        when = (datetime.fromtimestamp(stop.resets_at, timezone.utc).isoformat()
                if isinstance(stop.resets_at, (int, float)) else "unknown")
        ctx.say(f"PAUSED at the budget cap ({stop.detail}). That window resets at {when}; run the same command "
                "again after that. Completed runs are skipped.")
        return EXIT_STOPPED
    if stop.reason == "launch":
        ctx.say(f"PAUSED: Windows did not start claude ({stop.detail}). Nothing was recorded for those posts. "
                "Check the machine is awake and unlocked, then run the same command again.")
        return EXIT_STOPPED
    if stop.reason == "billing":
        ctx.say(f"STOPPED on a billing / usage-credits signal ({stop.detail}). Do NOT enable usage credits; "
                "tell the agent.")
    else:
        when = (datetime.fromtimestamp(stop.resets_at, timezone.utc).isoformat()
                if isinstance(stop.resets_at, (int, float)) else "unknown")
        ctx.say(f"STOPPED on a rate limit ({stop.detail}). Resets at {when}. Run the same command again after that; "
                "completed runs are skipped.")
    return EXIT_STOPPED


def _posts_by_id(path: Path):
    return {p.post_id: p for p in load_posts(path)}


def _pick(by_id, ids: Sequence[str], what: str):
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise gate.GateInputError(f"{what} names posts missing from the posts file: {', '.join(missing)}")
    return [by_id[i] for i in ids]


# ---------------------------------------------------------------- sample


def _sample_fresh(ctx: _Ctx, a: argparse.Namespace) -> int:
    """One freshest sales-ish post per company inside the window: the "email this week" set."""
    natural, ambiguous = fresh_per_company(load_posts(a.posts), ctx.cfg.title_filter(),
                                           window_days=a.fresh_per_company)
    out = Path(a.out)
    ids = gate.SampleIds(tuple(p.post_id for p in natural), tuple(p.post_id for p in ambiguous))
    gate.write_samples(out, ids, {"seeds": {}, "sizes": {"natural": len(ids.natural), "ambiguous": len(ids.ambiguous),
                                                         "opus": 0, "pilot": 0,
                                                         "window_days": a.fresh_per_company}})
    ctx.say(f"wrote {out}: natural {len(ids.natural)}, ambiguous {len(ids.ambiguous)} "
            f"(freshest sales-ish post per company, 0-{a.fresh_per_company} days old)")
    return EXIT_OK


def cmd_sample(ctx: _Ctx, a: argparse.Namespace) -> int:
    if a.fresh_per_company is not None:
        return _sample_fresh(ctx, a)
    cfg = ctx.cfg
    natural = a.natural if a.natural is not None else cfg.fact("pilot.natural_sample_size")
    ambiguous = a.ambiguous if a.ambiguous is not None else cfg.fact("pilot.ambiguous_subset_size")
    opus = a.opus
    if opus is None:
        try:
            opus = cfg.fact("pilot.opus_subset_size")
        except MissingFactError:
            opus = None  # gate.toml samples.opus_subset_size (Resolution 8: 50)
    s = draw_samples(load_posts(a.posts), cfg, natural_size=int(natural), ambiguous_size=int(ambiguous),
                     opus_size=None if opus is None else int(opus))
    out = Path(a.out)
    natural_ids = [p.post_id for p in s.natural]
    if a.pilot:
        pilot = random.Random(PILOT_SEED).sample(sorted(natural_ids), a.pilot)
    else:
        pilot = list(gate.read_samples(out).pilot) if out.exists() else []
    ids = gate.SampleIds(tuple(natural_ids), tuple(p.post_id for p in s.ambiguous), tuple(p.post_id for p in s.opus),
                         tuple(pilot))
    gate.write_samples(out, ids, {"seeds": {**cfg.gate["seeds"], "pilot": PILOT_SEED},
                                  "sizes": {"natural": len(ids.natural), "ambiguous": len(ids.ambiguous),
                                            "opus": len(ids.opus), "pilot": len(ids.pilot)}})
    ctx.say(f"wrote {out}: natural {len(ids.natural)}, ambiguous {len(ids.ambiguous)}, opus {len(ids.opus)}, "
            f"pilot {len(ids.pilot)}")
    return EXIT_OK


# ---------------------------------------------------------------- pilot


def _ask_percent(ctx: _Ctx, prompt: str) -> float:
    while True:
        raw = ctx.ask(prompt).strip().rstrip("%")
        try:
            value = float(raw)
        except ValueError:
            ctx.say("enter a number such as 12 or 12.5")
            continue
        if 0 <= value <= 100:
            return value
        ctx.say("enter a percentage between 0 and 100")


def _probe(ctx: _Ctx, log: Path, post, arm: str, model: str, settings: RunSettings, prompt_for, skill, schema):
    job = RunJob(post.post_id, arm, model, 1, prompt_for(post), skill, schema)
    result = _batch(ctx, [job], log, settings, 1)
    record = next((r.record for r in read_run_log(log).runs if (r.record.post_id, r.record.arm, r.record.repeat)
                   == job.key), None)
    return result, record


def _probes(ctx: _Ctx, a: argparse.Namespace, posts) -> int:
    cfg = ctx.cfg
    log_dir = Path(a.log_dir)
    log = log_dir / "probes.jsonl"
    effort = cfg.gate["run"]["effort"]
    skill, schema, prompt_for = prepare_skill(a.skill), _schema(a.schema), _signal_prompt_for(a.offer)
    post = posts[0]
    model = _arm(cfg, PROBE_ARM_MODEL)["model"]
    summary: dict[str, Any] = {"post_id": post.post_id, "effort": effort, "flag_probe": [], "chosen": None}
    chosen = None
    for i, (tools, turns) in enumerate(PROBE_LADDER, 1):
        settings = RunSettings(effort=effort, tools=tools, max_turns=turns)
        result, rec = _probe(ctx, log, post, f"probe-flags-{i}", model, settings, prompt_for, skill, schema)
        summary["cli_version"] = result.cli_version
        if result.stop:
            return _report_batch(ctx, result, log)
        ok = rec is not None and rec.structured_output is not None
        summary["flag_probe"].append({"tools_flag": False if tools is None else tools,
                                      "max_turns": False if turns is None else turns, "structured_output": ok,
                                      "failure_reason": rec.failure_reason if rec else "no record",
                                      "model_usage_keys": list(rec.model_usage_keys) if rec else [],
                                      "answer_models": list(answering_models_of(rec)) if rec else []})
        ctx.say(f"flag probe {i} (--tools {tools!r}, --max-turns {turns}): "
                f"{'structured output returned' if ok else 'NO structured output'}")
        if ok:
            chosen = settings
            summary["chosen"] = {"tools_flag": summary["flag_probe"][-1]["tools_flag"],
                                 "max_turns": summary["flag_probe"][-1]["max_turns"]}
            break
    old = _arm(cfg, OLD_HAIKU_ARM)
    settings = chosen or RunSettings(effort=effort, tools=PROBE_LADDER[0][0], max_turns=PROBE_LADDER[0][1])
    result, rec = _probe(ctx, log, post, old["name"], old["model"], settings, prompt_for, skill, schema)
    if result.stop:
        return _report_batch(ctx, result, log)
    passed = rec is not None and rec.structured_output is not None and answering_models_of(rec) == (old["model"],)
    summary["haiku_4_5_probe"] = {"model": old["model"], "passed": passed,
                                  "failure_reason": rec.failure_reason if rec else "no record",
                                  "model_usage_keys": list(rec.model_usage_keys) if rec else [],
                                  "answer_models": list(answering_models_of(rec)) if rec else []}
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "probes.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    ctx.say(f"old-Haiku probe ({old['model']}): {'works' if passed else 'FAILED'}")
    ctx.say(f"wrote {log_dir / 'probes.json'}. FACTs for config/facts/pilot.toml:")
    if summary["chosen"]:
        ctx.say(f"  tools_flag = {json.dumps(summary['chosen']['tools_flag'])}")
        ctx.say(f"  max_turns = {json.dumps(summary['chosen']['max_turns'])}")
    else:
        ctx.say("  no flag variant returned structured output: tell the agent before running the pilot")
    ctx.say(f"  haiku_4_5_probe_passed = {json.dumps(passed)}")
    return EXIT_OK


def cmd_pilot(ctx: _Ctx, a: argparse.Namespace) -> int:
    samples = gate.read_samples(a.samples)
    if not samples.pilot:
        raise gate.GateInputError(f"{a.samples} has no pilot set (key 'pilot'); draw one with `sample --pilot 20`")
    posts = _pick(_posts_by_id(a.posts), samples.pilot, "the pilot set")
    if a.probes:
        return _probes(ctx, a, posts)
    cfg = ctx.cfg
    arm = _arm(cfg, MODEL_ALIASES[a.model])
    n_posts, repeats = PILOT_PLAN[arm["name"]]
    settings = RunSettings.from_config(cfg)
    jobs = signal_jobs(posts[:n_posts], [{k: v for k, v in arm.items() if k != "subset"}], repeats=repeats,
                       skill=prepare_skill(a.skill), schema=_schema(a.schema), prompt_for=_signal_prompt_for(a.offer))
    log_dir = Path(a.log_dir)
    log = log_dir / "runs.jsonl"
    result = _batch(ctx, jobs, log, settings, a.parallel)
    code = _report_batch(ctx, result, log)
    if not a.no_usage_prompt:
        ctx.say("Run /usage in an interactive `claude` session and type the readings (percent used).")
        reading = {
            "arm": arm["name"], "model": arm["model"], "runs_this_batch": len(result.records),
            "five_hour_before": _ask_percent(ctx, "5-hour % BEFORE this pilot batch: "),
            "five_hour_after": _ask_percent(ctx, "5-hour % AFTER: "),
            "weekly_before": _ask_percent(ctx, "weekly % BEFORE: "),
            "weekly_after": _ask_percent(ctx, "weekly % AFTER: "),
            "recorded_at": (ctx.now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
        }
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "usage.jsonl").open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(reading, sort_keys=True) + "\n")
        ctx.say(f"saved usage readings to {log_dir / 'usage.jsonl'}")
    return code


# ---------------------------------------------------------------- run


def run_jobs(cfg: Config, posts, samples: gate.SampleIds, *, skill, schema, prompt_for) -> list[RunJob]:
    """Every (post, arm, repeat) of Part A: natural + ambiguous posts; subset arms (Opus)
    run once on their subset, the others gate.toml run.repeats times."""
    jobs: list[RunJob] = []
    for arm in cfg.arms(include_candidates=True):
        repeats = int(arm.get("repeats", 1 if arm.get("subset") else cfg.gate["run"]["repeats"]))
        jobs += signal_jobs(posts, [arm], repeats=repeats, skill=skill, schema=schema, prompt_for=prompt_for,
                            subsets=samples.subsets())
    return jobs


def cmd_run(ctx: _Ctx, a: argparse.Namespace) -> int:
    samples = gate.read_samples(a.samples)
    posts = _pick(_posts_by_id(a.posts), [*samples.natural, *samples.ambiguous], "the samples file")
    if a.arm:
        known = {arm["name"] for arm in ctx.cfg.arms(include_candidates=True)}
        unknown = [n for n in a.arm if n not in known]
        if unknown:
            raise gate.GateInputError(f"unknown or disabled arm(s): {', '.join(unknown)} "
                                      f"(enabled: {', '.join(sorted(known))})")
    jobs = run_jobs(ctx.cfg, posts, samples, skill=prepare_skill(a.skill), schema=_schema(a.schema),
                    prompt_for=_signal_prompt_for(a.offer))
    # --arm / --repeats narrow tonight's batch; keys stay (post, arm, repeat), so a later
    # full run skips what is already done.
    jobs = [j for j in jobs if (not a.arm or j.arm in a.arm) and (a.repeats is None or j.repeat <= a.repeats)]
    settings = RunSettings.from_config(ctx.cfg)
    log = Path(a.log)
    result = _batch(ctx, jobs, log, settings, a.parallel, a.max_runs)
    remaining = len([j for j in jobs if j.key not in read_run_log(log).completed_keys()])
    ctx.say(f"{remaining} of {len(jobs)} planned runs still to do")
    return _report_batch(ctx, result, log)


# ---------------------------------------------------------------- gate / gift / drafts


def cmd_gate(ctx: _Ctx, a: argparse.Namespace) -> int:
    posts = load_posts(a.posts)
    runs = read_run_log(a.runs).records
    if a.part == "b":
        report_b = gate.evaluate_part_b(read_run_log(a.drafts).records, posts, runs, ctx.cfg)
        out = Path(a.out or DEFAULTS["part_b"])
        gate.write_part_b(report_b, out)
        ctx.say(f"Part B: {len(report_b.results)} drafts checked, {len(report_b.failed)} failed runs; wrote {out}")
        return EXIT_OK
    relabel = gate.read_labels(a.relabel) if a.relabel and Path(a.relabel).exists() else None
    report = gate.evaluate_part_a(posts, gate.read_labels(a.labels), runs, gate.read_samples(a.samples), ctx.cfg,
                                  gate.rules_by_hash(a.skill_files or [DEFAULTS["signal_skill"]]), relabel)
    out = Path(a.out or DEFAULTS["part_a"])
    gate.write_part_a(report, out)
    failed = False
    for name, pop in report.populations.items():
        for c in pop.comparisons:
            state = "no verdict" if c.passed is None else ("PASS" if c.passed else "FAIL")
            failed |= c.passed is False
            ctx.say(f"{name}: {c.kind} {c.baseline} -> {c.candidate}: {state}")
    ctx.say(f"{len(report.excluded)} runs excluded (model mismatch), {len(report.failed)} failed runs; wrote {out}")
    return EXIT_INPUT if a.strict and failed else EXIT_OK


def cmd_gift(ctx: _Ctx, a: argparse.Namespace) -> int:
    rows = gate.build_gift(load_posts(a.posts), gate.read_labels(a.labels), read_run_log(a.runs).records, ctx.cfg,
                           gate.rules_by_hash(a.skill_files or [DEFAULTS["signal_skill"]]))
    top_n = int(ctx.cfg.gate["gift"]["top_n"])
    gate.write_gift(rows, Path(a.out), top_n)
    ctx.say(f"gift: {len(rows)} of {top_n} accounts; wrote {a.out}")
    return EXIT_OK


def cmd_drafts(ctx: _Ctx, a: argparse.Namespace) -> int:
    cfg = ctx.cfg
    posts = load_posts(a.posts)
    by_id = {p.post_id: p for p in posts}
    signal_runs = read_run_log(a.runs).records
    rows = gate.build_gift(posts, gate.read_labels(a.labels), signal_runs, cfg,
                           gate.rules_by_hash([a.skill]), extra=a.extra)
    arm = _arm(cfg, cfg.gate["gift"]["rank_by_arm"])
    offer, skill = read_offer_wording(a.offer), prepare_skill(a.copy_skill)
    jobs = []
    for row in rows:
        ctx_ = gate.draft_context(by_id[row.post_id], signal_runs, cfg)
        prompt = draft_prompt(company=row.company, domain=row.domain, role_title=row.role_title,
                              evidence=ctx_.evidence, offer=offer)
        jobs.append(RunJob(row.post_id, arm["name"], arm["model"], 1, prompt, skill, DRAFT_OUTPUT_SCHEMA))
    ctx.say(f"{len(jobs)} draft accounts (gift top {cfg.gate['gift']['top_n']} + up to {a.extra} more). "
            "Every draft is a sample; nothing is sent.")
    log = Path(a.log)
    return _report_batch(ctx, _batch(ctx, jobs, log, RunSettings.from_config(cfg), a.parallel), log)


# ---------------------------------------------------------------- parser


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m quality_gate", description=__doc__.split("\n\n")[0])
    p.add_argument("--config", type=Path, default=PACKAGE_ROOT, help="package root holding config/ (default: this build)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, *names):
        for n in names:
            sp.add_argument(f"--{n}", type=Path, default=DEFAULTS[n])

    s = sub.add_parser("sample", help="draw the samples (sizes default to FACT pilot.*)")
    common(s, "posts")
    s.add_argument("--out", type=Path, default=DEFAULTS["samples"])
    s.add_argument("--natural", type=int)
    s.add_argument("--ambiguous", type=int)
    s.add_argument("--opus", type=int)
    s.add_argument("--pilot", type=int, default=0, help="also draw a pilot set of N posts from the natural sample")
    s.add_argument("--fresh-per-company", type=int, metavar="DAYS",
                   help="instead: the freshest sales-ish post per company, 0..DAYS old (no seeds, no Opus subset)")

    for name, helptext in (("pilot", "day-1 pilot"), ("run", "full Part A runs"), ("drafts", "Part B drafts")):
        sp = sub.add_parser(name, help=helptext)
        common(sp, "posts", "offer", "schema")
        sp.add_argument("--skill", type=Path, default=DEFAULTS["signal_skill"])
        sp.add_argument("--parallel", type=int, default=1, choices=(1, 2))
        sp.add_argument("--max-five-hour", type=float, default=0.80,
                        help="pause once a run reports this share of the 5-hour limit used (default 0.80)")
        sp.add_argument("--max-weekly", type=float, default=0.70,
                        help="pause once a run reports this share of the weekly limit used (default 0.70)")
        if name == "pilot":
            common(sp, "samples")
            mode = sp.add_mutually_exclusive_group(required=True)
            mode.add_argument("--probes", action="store_true", help="flag probe + old-Haiku probe")
            mode.add_argument("--model", choices=sorted(MODEL_ALIASES))
            sp.add_argument("--log-dir", type=Path, default=DEFAULTS["pilot_dir"])
            sp.add_argument("--no-usage-prompt", action="store_true")
        elif name == "run":
            common(sp, "samples")
            sp.add_argument("--log", type=Path, default=DEFAULTS["runs"])
            sp.add_argument("--max-runs", type=int, help="cap this batch (spread runs across days)")
            sp.add_argument("--arm", action="append", help="only this arm (repeatable), e.g. sonnet-5-5")
            sp.add_argument("--repeats", type=int, help="only repeats 1..N")
        else:
            common(sp, "labels", "runs", "copy_skill")
            sp.add_argument("--log", type=Path, default=DEFAULTS["drafts"])
            sp.add_argument("--extra", type=int, default=gate.EXTRA_DRAFT_ACCOUNTS)

    g = sub.add_parser("gate", help="Part A (default) or Part B results from recorded runs")
    common(g, "posts", "samples", "labels", "relabel", "runs", "drafts")
    g.add_argument("--part", choices=("a", "b"), default="a")
    g.add_argument("--skill", dest="skill_files", type=Path, action="append",
                   help="a SKILL.md the runs used (repeatable; default intent-signals)")
    g.add_argument("--out", type=Path)
    g.add_argument("--strict", action="store_true", help="exit 1 if any verdict fails")

    gf = sub.add_parser("gift", help="the 50-account gift")
    common(gf, "posts", "labels", "runs")
    gf.add_argument("--skill", dest="skill_files", type=Path, action="append")
    gf.add_argument("--out", type=Path, default=DEFAULTS["gift"])
    return p


COMMANDS = {"sample": cmd_sample, "pilot": cmd_pilot, "run": cmd_run, "gate": cmd_gate, "gift": cmd_gift,
            "drafts": cmd_drafts}


def main(argv: Sequence[str] | None = None, *, invoker: Invoker | None = None,
         ask: Callable[[str], str] = input, out: TextIO | None = None, now: datetime | None = None) -> int:
    args = _parser().parse_args(argv)
    out = out or sys.stdout
    try:
        ctx = _Ctx(load_config(args.config), out, invoker, ask, now)
        ctx.max_five_hour = getattr(args, "max_five_hour", None)
        ctx.max_seven_day = getattr(args, "max_weekly", None)
        return COMMANDS[args.cmd](ctx, args)
    except (MissingFactError, AuthMethodError) as e:
        print(f"error: {e}", file=out)
        return EXIT_SETUP
    except ResumeTooEarlyError as e:
        print(f"not yet: {e}", file=out)
        return EXIT_STOPPED
    except (gate.GateInputError, SheetError, FileNotFoundError) as e:
        print(f"error: {e}", file=out)
        return EXIT_INPUT
