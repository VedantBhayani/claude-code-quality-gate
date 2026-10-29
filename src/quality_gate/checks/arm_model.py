"""Arm model match: catch a silent model switch (02a section 1) and keep such runs out of metrics.

A run counts for its arm only if it was launched with the arm's pinned model ID and the
model that wrote the answer is exactly that ID. Claude Code's own background calls (e.g. a
small Haiku 5.5 call on every run) also appear in modelUsage; they are named, not counted. A failed run with the right model stays in:
the metrics count it as a failure. A run that fails this check is excluded, with the reason.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from quality_gate.types import CheckResult, RunRecord, answering_models_of


def check_arm_model(run: RunRecord, pinned: Mapping[str, str]) -> CheckResult:
    """pinned maps arm name -> pinned model ID, e.g. {a["name"]: a["model"] for a in config.arms()}."""
    want = pinned.get(run.arm)
    if want is None:
        return CheckResult("arm_model", False, f"arm {run.arm!r} has no pinned model ID")
    if run.model != want:
        return CheckResult("arm_model", False, f"run launched with {run.model} but arm {run.arm} pins {want}")
    if not run.model_usage_keys:
        return CheckResult("arm_model", False, f"no modelUsage recorded, so the model cannot be confirmed as {want}")
    answer = answering_models_of(run)
    if not answer:
        return CheckResult("arm_model", False,
                           f"no modelUsage entry matches the main turn, so the answer cannot be confirmed as {want}")
    if answer != (want,):
        return CheckResult(
            "arm_model", False,
            f"silent model switch: the answer was written by {', '.join(answer)}, not arm {run.arm}'s pinned {want}",
        )
    helpers = sorted(set(run.model_usage_keys) - {want})
    note = f" (background calls also billed to {', '.join(helpers)})" if helpers else ""
    return CheckResult("arm_model", True, f"answer written by {want}, the pinned model of arm {run.arm}{note}")


@dataclass(frozen=True)
class MetricsSplit:
    kept: list[RunRecord] = field(default_factory=list)
    excluded: list[tuple[RunRecord, CheckResult]] = field(default_factory=list)  # run + why it is out


def split_for_metrics(runs: Iterable[RunRecord], pinned: Mapping[str, str]) -> MetricsSplit:
    kept, excluded = [], []
    for run in runs:
        result = check_arm_model(run, pinned)
        (kept.append(run) if result.passed else excluded.append((run, result)))
    return MetricsSplit(kept=kept, excluded=excluded)
