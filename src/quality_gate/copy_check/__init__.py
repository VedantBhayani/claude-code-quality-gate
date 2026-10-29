"""Part B copy checker: Kenny's copy QA checklist in code, Flesch-Kincaid, worst-first ranking."""
from quality_gate.copy_check.checklist import (
    CHECK_NAMES,
    SEVERITY,
    CopyCheckResult,
    Draft,
    SignalContext,
    check_draft,
)
from quality_gate.copy_check.fk_grade import fk_grade, text_stats
from quality_gate.copy_check.rank import RankedDraft, rank_worst_first

__all__ = [
    "CHECK_NAMES", "SEVERITY", "CopyCheckResult", "Draft", "SignalContext", "check_draft",
    "fk_grade", "text_stats", "RankedDraft", "rank_worst_first",
]
