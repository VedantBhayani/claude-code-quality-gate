import pytest
from checks_fixtures import INTENT_SIGNALS, label, load_run, make_post, make_run, output

from quality_gate.checks import (
    check_evidence,
    check_label_signal,
    check_label_type,
    check_recency,
    check_run,
    check_score,
    check_structured_output,
    check_tier,
)
from quality_gate.skill_rules import read_rules

RULES = read_rules(INTENT_SIGNALS)
PART_A = ["structured_output", "evidence", "score", "recency", "tier", "label_signal", "label_type"]


def _invalid(**overrides):
    out = output(**overrides)
    return make_run({k: v for k, v in out.items() if v is not None})


INVALID_RUNS = {
    "missing structured_output": make_run(ok=False),
    "max structured-output retries": load_run("max-structured-output-retries"),
    "total missing": _invalid(total=None),
    "factor out of range": _invalid(factors={"recency": 6, "directness": 4, "frequency": 3, "specificity": 3, "source": 4}),
    "unknown key": _invalid(confidence=0.9),
    "signal no with a signal type": _invalid(signal=False),
}


@pytest.mark.parametrize("run", INVALID_RUNS.values(), ids=INVALID_RUNS.keys())
def test_structured_output_check_fails_invalid_or_missing_output(run):
    result = check_structured_output(run)
    assert result.name == "structured_output"
    assert not result.passed


def test_structured_output_check_reports_the_cli_failure_reason():
    result = check_structured_output(load_run("max-structured-output-retries"))
    assert "error_max_structured_output_retries" in result.reason


def test_structured_output_check_passes_a_valid_output():
    assert check_structured_output(make_run()).passed


@pytest.mark.parametrize("run", INVALID_RUNS.values(), ids=INVALID_RUNS.keys())
def test_every_check_on_a_failed_run_is_an_explicit_failure_not_a_skip_or_crash(run):
    post, hand = make_post(), label()
    results = [
        check_evidence(run, post), check_score(run, RULES), check_recency(run, post, RULES),
        check_tier(run, RULES), check_label_signal(run, hand), check_label_type(run, hand),
    ]
    assert all(not r.passed for r in results)
    assert all("run failed" in r.reason for r in results)


def test_check_run_on_a_failed_run_returns_every_part_a_check_failed():
    results = check_run(load_run("max-structured-output-retries"), make_post(), RULES, label())
    assert [r.name for r in results] == PART_A
    assert not any(r.passed for r in results)


def test_check_run_on_a_good_run_passes_every_part_a_check():
    results = check_run(make_run(), make_post(), RULES, label())
    assert [r.name for r in results] == PART_A
    assert all(r.passed for r in results), [r for r in results if not r.passed]


def test_check_run_without_a_hand_label_leaves_out_only_the_label_checks():
    results = check_run(make_run(), make_post(), RULES)
    assert [r.name for r in results] == PART_A[:-2]
