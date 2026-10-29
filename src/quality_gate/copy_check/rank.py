"""Worst-first ranking of drafts (Resolution 15): the 10-80-10 demo's review order.

Order: most failed checks first, then highest total severity of the failed checks, then most
warnings, then draft_id (so the order is deterministic). A plain CheckResult with no severity
counts as severity 1.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from quality_gate.types import CheckResult


@dataclass(frozen=True)
class RankedDraft:
    draft_id: str
    failed: int
    severity: int  # sum of the failed checks' severities
    warnings: int
    failed_checks: tuple[str, ...]
    results: tuple[CheckResult, ...]


def _summarise(draft_id: str, results: Sequence[CheckResult]) -> RankedDraft:
    failed = [res for res in results if not res.passed]
    return RankedDraft(
        draft_id=draft_id,
        failed=len(failed),
        severity=sum(getattr(res, "severity", 1) for res in failed),
        warnings=sum(1 for res in results if getattr(res, "warning", False)),
        failed_checks=tuple(res.name for res in failed),
        results=tuple(results),
    )


def rank_worst_first(results_by_draft: Mapping[str, Sequence[CheckResult]]) -> list[RankedDraft]:
    ranked = [_summarise(draft_id, results) for draft_id, results in results_by_draft.items()]
    return sorted(ranked, key=lambda d: (-d.failed, -d.severity, -d.warnings, d.draft_id))
