"""The gate end to end on recorded outputs (spec Resolution 1, the confirmed test seam).

Recorded RunRecords (run logs) plus fixtures (posts, samples, hand labels) go in;
check results, metrics split natural/ambiguous, threshold verdicts, the gift and
the Part B worst-first ranking come out. Nothing here calls a model.

Part A, in order:
1. Every run is checked against the rules of the skill file it was given (looked
   up by its skill_hash), plus the arm model match.
2. Runs that fail the arm model match (silent model switch, wrong or missing model)
   are excluded from every metric and listed. Failed runs with the right model stay
   in and count as failures.
3. Per population (natural sample, ambiguous subset) and arm/repeat: macro-F1 vs
   hand labels on signal yes/no (gated) and signal type (reported), repeat noise,
   and for each comparison (baseline -> candidate) the F1 drop and flip rate on
   run 1, over the posts where both arms have a kept run-1 record. Thresholds come
   from the repeat noise measured on that population for the compared arms.
4. Rule-check failures (arithmetic, evidence, recency, tier) are counted per arm
   over runs that returned output: reported, not the headline.
5. Cohen's kappa between the hand-label passes: gated on yes/no, type reported.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from quality_gate.checks import check_arm_model, check_run, split_for_metrics
from quality_gate.config import Config
from quality_gate.copy_check import CHECK_NAMES, Draft, SignalContext, check_draft, rank_worst_first
from quality_gate.copy_check.checklist import CopyCheckResult
from quality_gate.gift.render import render_csv, render_html
from quality_gate.gift.select import GiftRow, select_gift
from quality_gate.labels import read_rows, validate_sheet
from quality_gate.metrics import F1, Rate, cohens_kappa, flip_rate, macro_f1, repeat_noise
from quality_gate.skill_rules import SkillRules, prepare_skill, read_rules
from quality_gate.thresholds import (
    Threshold,
    check_f1_drop,
    check_flip_rate,
    check_kappa,
    f1_drop_threshold,
    flip_rate_threshold,
)
from quality_gate.runner.prompts import DRAFT_MERGE_FIELDS
from quality_gate.types import CheckResult, HandLabel, Post, RunRecord

NATURAL, AMBIGUOUS = "natural sample", "ambiguous subset"
UNSAMPLED = "unsampled"
RULE_CHECKS = ("structured_output", "evidence", "score", "recency", "tier", "label_signal", "label_type")

# (baseline, candidate): the baseline is the arm being switched away from. Pairs whose
# arms have no runs in a population are skipped. Opus is just another model, never truth.
COMPARISONS: tuple[tuple[str, str], ...] = (
    ("sonnet-5-5", "haiku-5-5"),
    ("haiku-4-5", "haiku-5-5"),
    ("opus-5-5", "sonnet-5-5"),
    ("opus-5-5", "haiku-5-5"),
)
EXTRA_DRAFT_ACCOUNTS = 10  # Resolution 13: the 50 gift accounts plus up to 10 more


class GateInputError(ValueError):
    """The recorded inputs do not fit together (unknown post, unknown skill file...)."""


# ---------------------------------------------------------------- inputs


@dataclass(frozen=True)
class SampleIds:
    """data/samples/samples.json: post IDs of each sample. pilot is optional."""

    natural: tuple[str, ...]
    ambiguous: tuple[str, ...]
    opus: tuple[str, ...] = ()
    pilot: tuple[str, ...] = ()

    def populations(self) -> dict[str, tuple[str, ...]]:
        return {NATURAL: self.natural, AMBIGUOUS: self.ambiguous}

    def subsets(self) -> dict[str, set[str]]:
        return {"opus": set(self.opus)}

    def population_of(self, post_id: str) -> str:
        if post_id in self.natural:
            return NATURAL
        return AMBIGUOUS if post_id in self.ambiguous else UNSAMPLED


def read_samples(path: Path) -> SampleIds:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return SampleIds(*(tuple(d.get(k, ())) for k in ("natural", "ambiguous", "opus", "pilot")))


def write_samples(path: Path, samples: SampleIds, meta: Mapping[str, Any]) -> None:
    body = {"natural": list(samples.natural), "ambiguous": list(samples.ambiguous), "opus": list(samples.opus),
            "pilot": list(samples.pilot), **meta}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8", newline="\n")


def read_labels(path: Path) -> list[HandLabel]:
    """A filled labelling sheet (evals/labelling/guide.md format). Every row in it must carry a valid label."""
    return validate_sheet(Path(path), [r["post_id"] for r in read_rows(Path(path))])


def rules_by_hash(skill_paths: Iterable[Path]) -> dict[str, SkillRules]:
    """skill_hash -> the rules of that file, so each run is judged by the file it was given."""
    return {prepare_skill(p).sha256: read_rules(p) for p in skill_paths}


def pinned_models(cfg: Config) -> dict[str, str]:
    """Every arm's pinned model ID, candidate arms included (their pin is settled even
    while the arm itself waits on a pilot FACT)."""
    return {a["name"]: a["model"] for a in [*cfg.gate["arms"], *cfg.gate.get("candidate_arms", [])]}


def _arm_order(cfg: Config) -> list[str]:
    return list(pinned_models(cfg))


# ---------------------------------------------------------------- Part A


@dataclass(frozen=True)
class RunChecks:
    run: RunRecord
    population: str
    results: list[CheckResult]


@dataclass
class ArmStats:
    model: str
    repeats: dict[int, dict[str, Any]] = field(default_factory=dict)
    repeat_noise: dict[str, Any] | None = None
    check_failures: dict[str, int] = field(default_factory=dict)


@dataclass
class Comparison:
    baseline: str
    candidate: str
    kind: str
    post_count: int
    macro_f1_signal: dict[str, float | None]
    macro_f1_type: dict[str, float | None]
    flip_rate_signal: Rate
    flip_rate_type: Rate
    thresholds: dict[str, Threshold]
    verdicts: list[CheckResult]
    passed: bool | None  # None: no repeat noise measured, so no threshold and no verdict


@dataclass
class PopulationReport:
    post_ids: tuple[str, ...]
    arms: dict[str, ArmStats]
    comparisons: list[Comparison]


@dataclass
class PartAReport:
    run_checks: list[RunChecks]
    excluded: list[tuple[RunRecord, CheckResult]]
    failed: list[RunRecord]
    populations: dict[str, PopulationReport]
    label_agreement: dict[str, Any] | None


def _label_map(runs: Iterable[RunRecord], arm: str, repeat: int, key: str) -> dict[str, Any]:
    return {r.post_id: (None if r.structured_output is None else r.structured_output.get(key))
            for r in runs if r.arm == arm and r.repeat == repeat}


def _restrict(labels: Mapping[str, Any], ids: Iterable[str]) -> dict[str, Any]:
    return {k: labels[k] for k in ids if k in labels}


def _f1(predicted: Mapping[str, Any], gold: Mapping[str, Any]) -> float | None:
    try:
        return macro_f1(predicted, gold).macro_f1
    except ValueError:  # no hand-labelled post with a successful run
        return None


def _population(name: str, ids: tuple[str, ...], kept: list[RunRecord], excluded: list[RunRecord],
                checks: list[RunChecks], gold: Mapping[str, HandLabel], cfg: Config,
                pinned: Mapping[str, str]) -> PopulationReport:
    idset = set(ids)
    runs = [r for r in kept if r.post_id in idset]
    kept_ids = {id(r) for r in runs}
    gold_signal = {k: gold[k].signal for k in ids if k in gold}
    gold_type = {k: gold[k].signal_type for k in ids if k in gold}
    arms: dict[str, ArmStats] = {}
    for arm in [a for a in _arm_order(cfg) if any(r.arm == a for r in runs)]:
        stats = ArmStats(model=pinned[arm])
        for rep in sorted({r.repeat for r in runs if r.arm == arm}):
            mine = [r for r in runs if r.arm == arm and r.repeat == rep]
            stats.repeats[rep] = {
                "runs": len(mine),
                "failed_runs": sum(r.structured_output is None for r in mine),
                "excluded_runs": sum(r.arm == arm and r.repeat == rep and r.post_id in idset for r in excluded),
                "macro_f1_signal": _f1(_label_map(mine, arm, rep, "signal"), gold_signal),
                "macro_f1_type": _f1(_label_map(mine, arm, rep, "signal_type"), gold_type),
            }
        if {1, 2} <= stats.repeats.keys():
            f1s = [stats.repeats[r]["macro_f1_signal"] for r in (1, 2)]
            stats.repeat_noise = {
                "signal": repeat_noise(stats.model, _label_map(runs, arm, 1, "signal"),
                                       _label_map(runs, arm, 2, "signal")),
                "signal_type": repeat_noise(stats.model, _label_map(runs, arm, 1, "signal_type"),
                                            _label_map(runs, arm, 2, "signal_type")),
                "macro_f1_signal_points": None if None in f1s else round(abs(f1s[0] - f1s[1]) * 100, 6),
            }
        counts = Counter({c: 0 for c in RULE_CHECKS})
        for rc in checks:
            if rc.run.arm == arm and id(rc.run) in kept_ids and rc.run.structured_output is not None:
                counts.update(r.name for r in rc.results if not r.passed and r.name in RULE_CHECKS)
        stats.check_failures = dict(counts)
        arms[arm] = stats
    comparisons = [_compare(b, c, runs, arms, gold_signal, gold_type, cfg)
                   for b, c in COMPARISONS if b in arms and c in arms and 1 in arms[b].repeats
                   and 1 in arms[c].repeats]
    return PopulationReport(post_ids=ids, arms=arms, comparisons=comparisons)


def _compare(base: str, cand: str, runs: list[RunRecord], arms: Mapping[str, ArmStats],
             gold_signal: Mapping[str, bool], gold_type: Mapping[str, str], cfg: Config) -> Comparison:
    bs, cs = _label_map(runs, base, 1, "signal"), _label_map(runs, cand, 1, "signal")
    bt, ct = _label_map(runs, base, 1, "signal_type"), _label_map(runs, cand, 1, "signal_type")
    common = sorted(bs.keys() & cs.keys())
    gs, gt = _restrict(gold_signal, common), _restrict(gold_type, common)
    f1_sig = {"baseline": _f1(_restrict(bs, common), gs), "candidate": _f1(_restrict(cs, common), gs)}
    f1_typ = {"baseline": _f1(_restrict(bt, common), gt), "candidate": _f1(_restrict(ct, common), gt)}
    mb, mc = arms[base].model, arms[cand].model
    flip_sig = flip_rate(mb, _restrict(bs, common), mc, _restrict(cs, common))
    flip_typ = flip_rate(mb, _restrict(bt, common), mc, _restrict(ct, common))

    rules = cfg.gate["thresholds"]
    noise = {a: arms[a].repeat_noise for a in (base, cand) if arms[a].repeat_noise}
    f1_noise = {a: n["macro_f1_signal_points"] / 100 for a, n in noise.items()
                if n["macro_f1_signal_points"] is not None}
    flip_noise = {a: n["signal"].rate for a, n in noise.items()}
    thresholds: dict[str, Threshold] = {}
    verdicts: list[CheckResult] = []
    if f1_noise and None not in f1_sig.values():
        thresholds["macro_f1_drop"] = f1_drop_threshold(f1_noise, rules)
        verdicts.append(check_f1_drop(f1_sig["baseline"], f1_sig["candidate"], thresholds["macro_f1_drop"]))
    if flip_noise:
        thresholds["flip_rate"] = flip_rate_threshold(flip_noise, rules)
        verdicts.append(check_flip_rate(flip_sig, thresholds["flip_rate"]))
    return Comparison(
        baseline=base, candidate=cand, kind=flip_sig.kind, post_count=len(common),
        macro_f1_signal=f1_sig, macro_f1_type=f1_typ, flip_rate_signal=flip_sig, flip_rate_type=flip_typ,
        thresholds=thresholds, verdicts=verdicts,
        passed=all(v.passed for v in verdicts) if verdicts else None,
    )


def _agreement(labels: Sequence[HandLabel], relabel: Sequence[HandLabel] | None, cfg: Config) -> dict[str, Any] | None:
    if not relabel:
        return None
    first = {lab.post_id: lab for lab in labels}
    second = {lab.post_id: lab for lab in relabel if lab.post_id in first}
    yes_no = cohens_kappa({k: first[k].signal for k in second}, {k: v.signal for k, v in second.items()})
    types = cohens_kappa({k: first[k].signal_type for k in second}, {k: v.signal_type for k, v in second.items()})
    return {
        "signal_yes_no": {**asdict(yes_no), "verdict": check_kappa(yes_no.kappa, cfg.gate["agreement"])},
        "signal_type": {**asdict(types), "note": "reported only, not gated (Resolution 6)"},
    }


def evaluate_part_a(
    posts: Sequence[Post],
    labels: Sequence[HandLabel],
    runs: Sequence[RunRecord],
    samples: SampleIds,
    cfg: Config,
    rules: Mapping[str, SkillRules],
    relabel: Sequence[HandLabel] | None = None,
) -> PartAReport:
    by_id = {p.post_id: p for p in posts}
    gold = {lab.post_id: lab for lab in labels}
    pinned = pinned_models(cfg)
    missing_posts = sorted({r.post_id for r in runs} - by_id.keys())
    if missing_posts:
        raise GateInputError(f"runs name posts that are not in the posts file: {', '.join(missing_posts)}")
    unknown = sorted({r.skill_hash for r in runs} - rules.keys())
    if unknown:
        raise GateInputError(f"runs were given skill files the gate was not given (skill_hash {', '.join(unknown)}); "
                             "pass every SKILL.md the runs used with --skill")
    checks = [
        RunChecks(r, samples.population_of(r.post_id),
                  check_run(r, by_id[r.post_id], rules[r.skill_hash], gold.get(r.post_id)) + [check_arm_model(r, pinned)])
        for r in runs
    ]
    split = split_for_metrics(runs, pinned)
    excluded_runs = [r for r, _ in split.excluded]
    pops = {name: _population(name, ids, split.kept, excluded_runs, checks, gold, cfg, pinned)
            for name, ids in _with_fresh(samples.populations(), by_id, cfg).items()}
    return PartAReport(
        run_checks=checks,
        excluded=split.excluded,
        failed=[r for r in split.kept if r.structured_output is None],
        populations=pops,
        label_agreement=_agreement(labels, relabel, cfg),
    )


def _with_fresh(populations: Mapping[str, tuple[str, ...]], by_id: Mapping[str, Post],
                cfg: Config) -> dict[str, tuple[str, ...]]:
    """Each population, plus its posts at most [fresh] max_age_days old when that drops any."""
    days = int(cfg.gate["fresh"]["max_age_days"])
    out = dict(populations)
    for name, ids in populations.items():
        fresh = tuple(i for i in ids if (by_id[i].collection_date - by_id[i].post_date).days <= days)
        if len(fresh) < len(ids):
            out[f"{name}, posted within {days} days"] = fresh
    return out


# ---------------------------------------------------------------- writing


def _plain(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return _plain(asdict(obj))
    if isinstance(obj, Mapping):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    return obj


def _run_key(r: RunRecord) -> dict[str, Any]:
    return {"post_id": r.post_id, "arm": r.arm, "model": r.model, "repeat": r.repeat}


def _write_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fields), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _flag(b: bool) -> str:
    return "true" if b else "false"


def part_a_metrics(report: PartAReport) -> dict[str, Any]:
    return {
        "populations": {
            name: {
                "post_ids": list(pop.post_ids),
                "arms": {arm: _plain(s) for arm, s in pop.arms.items()},
                "comparisons": [_plain(c) for c in pop.comparisons],
            }
            for name, pop in report.populations.items()
        },
        "excluded_runs": [{**_run_key(r), "model_usage_keys": list(r.model_usage_keys), "reason": c.reason}
                          for r, c in report.excluded],
        "failed_runs": [{**_run_key(r), "failure_reason": r.failure_reason} for r in report.failed],
        "label_agreement": _plain(report.label_agreement),
        "inputs": {"runs": len(report.run_checks),
                   "skill_hashes": sorted({rc.run.skill_hash for rc in report.run_checks}),
                   "cli_versions": sorted({rc.run.cli_version for rc in report.run_checks}),
                   "efforts": sorted({rc.run.effort for rc in report.run_checks})},
    }


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def _f(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def part_a_summary(report: PartAReport) -> str:
    out = ["# Part A gate results", "",
           "Terms: \"model switch\" = a different model (e.g. Haiku vs Sonnet); \"model upgrade\" = a newer "
           "version of the same model; \"repeat noise\" = two runs of one model on the same post.", ""]
    out += ["## Verdicts", ""]
    for name, pop in report.populations.items():
        for c in pop.comparisons:
            state = "no verdict (no repeat noise measured)" if c.passed is None else ("PASS" if c.passed else "FAIL")
            out.append(f"- **{name}**, {c.kind} {c.baseline} -> {c.candidate} ({c.post_count} posts): {state}")
            for v in c.verdicts:
                out.append(f"  - {v.name}: {'pass' if v.passed else 'FAIL'}. {v.reason}")
    if report.label_agreement:
        v = report.label_agreement["signal_yes_no"]["verdict"]
        out.append(f"- Hand-label agreement: {'pass' if v.passed else 'FAIL'}. {v.reason} "
                   f"(signal type kappa {report.label_agreement['signal_type']['kappa']:.2f}, reported only)")
    out += ["", "## Metrics by population", ""]
    for name, pop in report.populations.items():
        out += [f"### {name} ({len(pop.post_ids)} posts)", "",
                "| arm | repeat | runs | failed | excluded | macro-F1 yes/no | macro-F1 type |",
                "|---|---|---|---|---|---|---|"]
        for arm, s in pop.arms.items():
            for rep, d in s.repeats.items():
                out.append(f"| {arm} | {rep} | {d['runs']} | {d['failed_runs']} | {d['excluded_runs']} | "
                           f"{_f(d['macro_f1_signal'])} | {_f(d['macro_f1_type'])} |")
        out.append("")
        for arm, s in pop.arms.items():
            if s.repeat_noise:
                out.append(f"- {s.repeat_noise['signal'].describe()}")
        for c in pop.comparisons:
            out.append(f"- {c.flip_rate_signal.describe()} (yes/no); signal type: {_pct(c.flip_rate_type.rate)}")
        out.append("")
    out += ["## Runs excluded from metrics", ""]
    if not report.excluded:
        out.append("None: every run's modelUsage matched its arm's pinned model.")
    for r, c in report.excluded:
        out.append(f"- {r.post_id} / {r.arm} / repeat {r.repeat}: {c.reason}")
    out += ["", "## Failed runs (kept, counted as failures)", ""]
    out += [f"- {r.post_id} / {r.arm} / repeat {r.repeat}: {r.failure_reason}" for r in report.failed] or ["None."]
    out += ["", "## Rule checks (reported, not the headline)", "",
            "Failures among runs that returned output, per population and arm.", ""]
    for name, pop in report.populations.items():
        for arm, s in pop.arms.items():
            fails = ", ".join(f"{k} {v}" for k, v in s.check_failures.items())
            out.append(f"- {name}, {arm}: {fails}")
    return "\n".join(out) + "\n"


CHECK_FIELDS = ("post_id", "population", "arm", "model", "repeat", "check", "passed", "heuristic", "reason")


def write_part_a(report: PartAReport, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(out_dir / "checks.csv", CHECK_FIELDS, (
        {**_run_key(rc.run), "population": rc.population, "check": c.name, "passed": _flag(c.passed),
         "heuristic": _flag(c.heuristic), "reason": c.reason}
        for rc in report.run_checks for c in rc.results))
    _write_csv(out_dir / "excluded_runs.csv", ("post_id", "arm", "model", "repeat", "model_usage_keys", "reason"), (
        {**_run_key(r), "model_usage_keys": " ".join(r.model_usage_keys), "reason": c.reason}
        for r, c in report.excluded))
    (out_dir / "metrics.json").write_text(json.dumps(part_a_metrics(report), indent=2) + "\n",
                                          encoding="utf-8", newline="\n")
    (out_dir / "summary.md").write_text(part_a_summary(report), encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- gift


def _ranking_runs(runs: Iterable[RunRecord], cfg: Config) -> dict[str, RunRecord]:
    g = cfg.gate["gift"]
    return {r.post_id: r for r in runs if r.arm == g["rank_by_arm"] and r.repeat == int(g["rank_by_repeat"])}


def build_gift(posts: Sequence[Post], labels: Sequence[HandLabel], runs: Sequence[RunRecord], cfg: Config,
               rules: Mapping[str, SkillRules], *, extra: int = 0) -> list[GiftRow]:
    """Resolution 10. extra > 0 widens the cut (Part B takes the gift plus up to 10 more)."""
    by_id = {p.post_id: p for p in posts}
    gold = {lab.post_id: lab for lab in labels}
    pinned = pinned_models(cfg)
    checks = {}
    for pid, r in _ranking_runs(runs, cfg).items():
        if pid in by_id and r.skill_hash in rules:
            checks[pid] = check_run(r, by_id[pid], rules[r.skill_hash], gold.get(pid)) + [check_arm_model(r, pinned)]
    gift_rules = dict(cfg.gate["gift"])
    gift_rules["top_n"] = int(gift_rules["top_n"]) + extra
    return select_gift(posts, labels, runs, checks, gift_rules)


def write_gift(rows: Sequence[GiftRow], out_dir: Path, top_n: int) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "gift.csv").write_text(render_csv(rows), encoding="utf-8", newline="")
    (out_dir / "gift.html").write_text(render_html(rows, top_n=top_n), encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- Part B


def draft_context(post: Post, signal_runs: Iterable[RunRecord], cfg: Config) -> SignalContext:
    """The signal a draft is written from: the role title and the evidence quotes of the
    post's Sonnet run-1 record (the run the gift ranks by). Used for the prompt and the check."""
    run = _ranking_runs([r for r in signal_runs if r.post_id == post.post_id], cfg).get(post.post_id)
    evidence = (run.structured_output or {}).get("evidence", []) if run else []
    if isinstance(evidence, str):
        evidence = [evidence]
    return SignalContext(role_title=post.title, evidence=tuple(q for q in evidence if isinstance(q, str)))


@dataclass
class PartBReport:
    results: dict[str, list]  # post_id -> CopyCheckResults
    drafts: dict[str, RunRecord]
    failed: list[RunRecord]
    excluded: list[tuple[RunRecord, CheckResult]]
    companies: dict[str, str]


SIGN_OFF = "{{senderName}}"
# Kenny's checklist, then this eval's own rule: a sample draft must not read as written by a real person.
PART_B_CHECKS: tuple[str, ...] = CHECK_NAMES + ("sign_off",)


def check_sign_off(draft: Draft) -> CopyCheckResult:
    """The last non-empty line of the body is the {{senderName}} merge field, not a name."""
    lines = [line.strip() for line in draft.body.splitlines() if line.strip()]
    last = lines[-1] if lines else ""
    if last == SIGN_OFF:
        return CopyCheckResult(name="sign_off", passed=True, reason=f"signs off with {SIGN_OFF}", severity=3)
    return CopyCheckResult(name="sign_off", passed=False, severity=3,
                           reason=f"signs off with {last!r}, not {SIGN_OFF} (this eval's rule, not Kenny's checklist)")


def evaluate_part_b(draft_runs: Sequence[RunRecord], posts: Sequence[Post], signal_runs: Sequence[RunRecord],
                    cfg: Config) -> PartBReport:
    by_id = {p.post_id: p for p in posts}
    missing = sorted({r.post_id for r in draft_runs} - by_id.keys())
    if missing:
        raise GateInputError(f"drafts name posts that are not in the posts file: {', '.join(missing)}")
    split = split_for_metrics(draft_runs, pinned_models(cfg))
    results, drafts, failed = {}, {}, []
    for r in split.kept:
        out = r.structured_output
        if out is None:
            failed.append(r)
            continue
        draft = Draft(r.post_id, str(out.get("subject", "")), str(out.get("body", "")))
        results[r.post_id] = check_draft(draft, draft_context(by_id[r.post_id], signal_runs, cfg),
                                         DRAFT_MERGE_FIELDS) + [check_sign_off(draft)]
        drafts[r.post_id] = r
    return PartBReport(results, drafts, failed, split.excluded, {p.post_id: p.company for p in posts})


SAMPLE_NOTE = ("Every draft is a SAMPLE written by claude-sonnet-5-5 for this evaluation. Each pitches Frontal's "
               "offer in its own site wording and signs off with a {{senderName}} merge field. None was sent, and "
               "Frontal did not ask for or review any of them.")


def write_part_b(report: PartBReport, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    checked = len(report.results)
    heuristic = {c.name: c.heuristic for res in report.results.values() for c in res}
    rates = []
    for name in PART_B_CHECKS:
        failed = sum(not c.passed for res in report.results.values() for c in res if c.name == name)
        warned = sum(getattr(c, "warning", False) for res in report.results.values() for c in res if c.name == name)
        rates.append({"check": name, "heuristic": _flag(heuristic.get(name, False)), "failed": failed,
                      "warned": warned, "checked": checked,
                      "failure_rate": f"{failed / checked:.4f}" if checked else ""})
    _write_csv(out_dir / "failure_rates.csv", ("check", "heuristic", "failed", "warned", "checked", "failure_rate"),
               rates)
    _write_csv(out_dir / "checks.csv", ("post_id", "company", "check", "passed", "warning", "heuristic", "severity",
                                        "reason"), (
        {"post_id": pid, "company": report.companies.get(pid, ""), "check": c.name, "passed": _flag(c.passed),
         "warning": _flag(getattr(c, "warning", False)), "heuristic": _flag(c.heuristic),
         "severity": getattr(c, "severity", 1), "reason": c.reason}
        for pid, res in report.results.items() for c in res))
    fields = ("rank", "label", "post_id", "company", "failed", "severity", "warnings", "failed_checks", "subject", "body")
    worst = []
    for r in report.failed:  # no draft at all: worse than any draft
        worst.append({"post_id": r.post_id, "company": report.companies.get(r.post_id, ""), "failed": "",
                      "severity": "", "warnings": "", "failed_checks": f"run failed: {r.failure_reason}",
                      "subject": "", "body": ""})
    for d in rank_worst_first(report.results):
        out = report.drafts[d.draft_id].structured_output or {}
        worst.append({"post_id": d.draft_id, "company": report.companies.get(d.draft_id, ""), "failed": d.failed,
                      "severity": d.severity, "warnings": d.warnings, "failed_checks": " ".join(d.failed_checks),
                      "subject": out.get("subject", ""), "body": out.get("body", "")})
    _write_csv(out_dir / "worst_first.csv", fields,
               ({"rank": i, "label": "sample", **row} for i, row in enumerate(worst, 1)))
    lines = ["# Part B copy-check results (sample drafts)", "", SAMPLE_NOTE, "",
             f"{checked} drafts checked; {len(report.failed)} draft runs failed; "
             f"{len(report.excluded)} excluded for a model mismatch.", "",
             "| check | failed | rate | warned |", "|---|---|---|---|"]
    for row in rates:
        mark = " (heuristic)" if row["heuristic"] == "true" else ""
        rate = f"{float(row['failure_rate']) * 100:.1f}%" if row["failure_rate"] else "n/a"
        lines.append(f"| {row['check']}{mark} | {row['failed']}/{checked} | {rate} | {row['warned']} |")
    lines += ["", "## Worst first (read these first)", ""]
    lines += [f"{i}. {w['company']} ({w['post_id']}): {w['failed_checks'] or 'all checks pass'}"
              for i, w in enumerate(worst, 1)]
    if report.excluded:
        lines += ["", "## Excluded draft runs", ""]
        lines += [f"- {r.post_id}: {c.reason}" for r, c in report.excluded]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
