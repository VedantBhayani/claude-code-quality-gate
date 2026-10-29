"""run_batch: one `claude -p` call per (post, arm, repeat), recorded as RunRecords.

- Preflight: `claude auth status` must report authMethod `claude.ai` (Pro login,
  no API key; 02a section 6), else nothing runs.
- Each call gets a fresh empty working directory; the stripped skill is written
  to a separate temp dir and passed with --append-system-prompt-file.
- Missing / schema-invalid structured_output and error results (including
  error_max_structured_output_retries) are recorded as failed runs, not dropped.
- A rate-limit (status rejected, api_retry rate_limit) or billing signal
  (errorCode credits_required, api_retry billing_error) stops the batch; the
  stopping call is not marked completed unless it still returned valid output.
- A re-run reads the log, skips completed keys and refuses to start before the
  last stop's resets_at.
- Sequential by default, 2-way parallel at most (research 02).
"""
from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from quality_gate.runner.command import RunSettings, build_command
from quality_gate.runner.invoker import Invoker
from quality_gate.runner.output import Outcome, Stop, interpret, parse_auth_method, parse_version
from quality_gate.runner.runlog import Key, LoggedRun, append_run, append_stop, read_run_log
from quality_gate.skill_rules import PreparedSkill
from quality_gate.types import Post, RunRecord

REQUIRED_AUTH_METHOD = "claude.ai"
MAX_PARALLEL = 2


class AuthMethodError(RuntimeError):
    """`claude auth status` does not report the Pro (claude.ai) login."""


class ResumeTooEarlyError(RuntimeError):
    """The last batch stopped on a limit whose reset time has not passed."""


@dataclass(frozen=True)
class RunJob:
    post_id: str
    arm: str
    model: str
    repeat: int
    prompt: str
    skill: PreparedSkill
    schema: dict[str, Any]

    @property
    def key(self) -> Key:
        return (self.post_id, self.arm, self.repeat)


@dataclass
class BatchResult:
    records: list[RunRecord] = field(default_factory=list)  # completed in this batch, in log order
    skipped: list[Key] = field(default_factory=list)  # already completed before this batch
    stop: Stop | None = None
    cli_version: str | None = None
    launch_failures: list[Key] = field(default_factory=list)  # never recorded; redone by the next batch


def signal_jobs(
    posts: Sequence[Post],
    arms: Iterable[dict[str, Any]],
    *,
    repeats: int,
    skill: PreparedSkill,
    schema: dict[str, Any],
    prompt_for,
    subsets: dict[str, set[str]] | None = None,
) -> list[RunJob]:
    """Jobs for every (post, arm, repeat). An arm with `subset = "<name>"` (config)
    runs only on the post IDs in subsets[<name>]. prompt_for(post) builds the prompt."""
    jobs = []
    for arm in arms:
        allowed = None
        if arm.get("subset"):
            if not subsets or arm["subset"] not in subsets:
                raise ValueError(f"arm {arm['name']} runs on subset {arm['subset']!r}, which was not given")
            allowed = subsets[arm["subset"]]
        for post in posts:
            if allowed is not None and post.post_id not in allowed:
                continue
            for r in range(1, repeats + 1):
                jobs.append(RunJob(post.post_id, arm["name"], arm["model"], r, prompt_for(post), skill, schema))
    return jobs


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _preflight(invoker: Invoker) -> str:
    with tempfile.TemporaryDirectory(prefix="qg-preflight-", ignore_cleanup_errors=True) as cwd:
        auth = invoker.invoke(["auth", "status"], Path(cwd))
        method = parse_auth_method(auth.stdout)
        if method != REQUIRED_AUTH_METHOD:
            raise AuthMethodError(
                f"claude auth status reports authMethod {method!r}; the gate runs only on the "
                f"{REQUIRED_AUTH_METHOD!r} (Pro) login. Unset ANTHROPIC_API_KEY and log in with `claude login`."
            )
        return parse_version(invoker.invoke(["--version"], Path(cwd)).stdout)


MAX_LAUNCH_FAILURES = 3  # in a row: Windows is refusing to start processes (sleep, lock, resources)


def _over_budget(limits: dict | None, max_five_hour: float | None, max_seven_day: float | None) -> Stop | None:
    for window, cap in (("five_hour", max_five_hour), ("seven_day", max_seven_day)):
        used = (limits or {}).get(window)
        if cap is not None and isinstance(used, (int, float)) and used >= cap:
            return Stop("budget", f"{window} utilization {used:.2f} reached the cap {cap:.2f}",
                        (limits or {}).get(f"{window}_resets_at"))
    return None


def _check_resume(stops: list[Stop], now: datetime) -> None:
    if not stops:
        return
    last = stops[-1]
    if isinstance(last.resets_at, (int, float)) and last.resets_at > now.timestamp():
        at = datetime.fromtimestamp(last.resets_at, timezone.utc).isoformat()
        raise ResumeTooEarlyError(f"last batch stopped ({last.reason}: {last.detail}); resume after {at}")


def _call(job: RunJob, invoker: Invoker, settings: RunSettings) -> Outcome:
    with tempfile.TemporaryDirectory(prefix="qg-skill-", ignore_cleanup_errors=True) as skill_dir, \
            tempfile.TemporaryDirectory(prefix="qg-run-", ignore_cleanup_errors=True) as cwd:
        skill_file = job.skill.write_to(Path(skill_dir) / "SKILL.md")
        argv = build_command(model=job.model, prompt=job.prompt, skill_file=skill_file, schema=job.schema,
                             settings=settings)
        call = invoker.invoke(argv, Path(cwd))
    return interpret(call.stdout, job.schema, call.returncode, call.stderr)


def _record(job: RunJob, out: Outcome, cli_version: str, settings: RunSettings) -> RunRecord:
    return RunRecord(
        post_id=job.post_id,
        arm=job.arm,
        model=job.model,
        repeat=job.repeat,
        structured_output=out.structured_output,
        failure_reason=out.failure_reason,
        model_usage_keys=out.model_usage_keys,
        answer_models=out.answer_models,
        model_usage=out.model_usage,
        cli_version=cli_version,
        skill_hash=job.skill.sha256,
        effort=settings.effort,
        usage=out.usage,
        cost_usd=out.cost_usd,
    )


def run_batch(
    jobs: Sequence[RunJob],
    *,
    invoker: Invoker,
    log_path: Path,
    settings: RunSettings,
    now: datetime | None = None,
    parallel: int = 1,
    max_five_hour: float | None = None,
    max_seven_day: float | None = None,
) -> BatchResult:
    """max_five_hour / max_seven_day: plan-utilization caps (0..1). The batch stops, reason
    "budget", after the first run that reports reaching one; resume waits for that window's reset."""
    if not 1 <= parallel <= MAX_PARALLEL:
        raise ValueError(f"parallel={parallel}: runs are sequential or 2-way parallel at most")
    now = now or datetime.now(timezone.utc)
    cli_version = _preflight(invoker)
    log = read_run_log(log_path)
    _check_resume(log.stops, now)

    done = log.completed_keys()
    result = BatchResult(cli_version=cli_version, skipped=[j.key for j in jobs if j.key in done])
    todo = [j for j in jobs if j.key not in done]

    streak = 0  # consecutive launch failures
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        for i in range(0, len(todo), parallel):
            chunk = todo[i:i + parallel]
            outcomes = list(pool.map(lambda j: _call(j, invoker, settings), chunk))
            for job, out in zip(chunk, outcomes):
                if out.launch_failed:
                    result.launch_failures.append(job.key)
                    streak += 1
                    if streak >= MAX_LAUNCH_FAILURES and result.stop is None:
                        result.stop = Stop("launch", f"{streak} calls in a row exited without starting claude",
                                           None, job.key)
                    continue
                streak = 0
                stopped = out.stop is not None
                if not stopped or out.structured_output is not None:
                    rec = _record(job, out, cli_version, settings)
                    append_run(log_path, LoggedRun(rec, out.init_model, out.subtype, out.session_id, _now_iso(),
                                                   out.limits))
                    result.records.append(rec)
                if stopped and result.stop is None:
                    result.stop = replace(out.stop, key=job.key)
                over = _over_budget(out.limits, max_five_hour, max_seven_day)
                if over and result.stop is None:
                    result.stop = replace(over, key=job.key)
            if result.stop:
                append_stop(log_path, result.stop, _now_iso())
                break
    return result
