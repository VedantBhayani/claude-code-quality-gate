"""Worst-first ranking of drafts (Resolution 15): failed-check count, then severity."""
import json
from pathlib import Path

from quality_gate.copy_check.checklist import CopyCheckResult, Draft, SignalContext, check_draft
from quality_gate.copy_check.rank import rank_worst_first
from quality_gate.types import CheckResult

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "drafts"


def r(name: str, passed: bool, severity: int = 1, warning: bool = False) -> CopyCheckResult:
    return CopyCheckResult(name=name, passed=passed, reason="x", severity=severity, warning=warning)


def test_more_failed_checks_rank_first():
    ranked = rank_worst_first({
        "one_fail": [r("a", False, 3), r("b", True)],
        "two_fails": [r("a", False, 1), r("b", False, 1)],
        "clean": [r("a", True), r("b", True)],
    })
    assert [d.draft_id for d in ranked] == ["two_fails", "one_fail", "clean"]
    assert [d.failed for d in ranked] == [2, 1, 0]


def test_equal_failed_count_breaks_tie_on_severity():
    ranked = rank_worst_first({
        "minor": [r("reading_level", False, 1)],
        "major": [r("variables", False, 3)],
    })
    assert [d.draft_id for d in ranked] == ["major", "minor"]
    assert ranked[0].severity == 3


def test_then_warnings_then_draft_id_keep_order_deterministic():
    ranked = rank_worst_first({
        "b_clean": [r("length", True)],
        "a_clean": [r("length", True)],
        "warned": [r("length", True, 2, warning=True)],
    })
    assert [d.draft_id for d in ranked] == ["warned", "a_clean", "b_clean"]


def test_passed_checks_carry_no_severity_and_plain_checkresults_count_as_severity_one():
    ranked = rank_worst_first({"plain": [CheckResult("a", False, "x"), r("b", True, 3)]})
    assert ranked[0].failed == 1 and ranked[0].severity == 1
    assert ranked[0].failed_checks == ("a",)


def test_fixture_drafts_rank_the_many_failures_draft_first_and_clean_ones_last():
    results = {}
    for p in FIXTURES.glob("*.json"):
        raw = json.loads(p.read_text(encoding="utf-8"))
        draft = Draft(raw["draft_id"], raw["subject"], raw["body"])
        results[raw["draft_id"]] = check_draft(draft, SignalContext(raw["role_title"], tuple(raw["evidence"])))
    ranked = [d.draft_id for d in rank_worst_first(results)]
    assert ranked[0] == "fail_many"
    assert ranked[-3:] == ["warn_length", "pass", "pass_no_greeting"]
