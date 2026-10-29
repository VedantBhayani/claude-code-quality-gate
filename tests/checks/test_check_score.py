import pytest
from checks_fixtures import INTENT_SIGNALS, MODIFIED_SKILL, make_run, output

from quality_gate.checks import check_score
from quality_gate.skill_rules import read_rules


@pytest.fixture(scope="module")
def rules():
    return read_rules(INTENT_SIGNALS)


def test_total_matching_the_formula_passes(rules):
    # 5x3 + 4x3 + 3x2 + 3x1 + 4x1 = 40
    result = check_score(make_run(output(total=40)), rules)
    assert result.name == "score"
    assert result.passed, result.reason


def test_total_off_by_one_fails_and_states_the_expected_total(rules):
    result = check_score(make_run(output(total=41)), rules)
    assert not result.passed
    assert "40" in result.reason and "41" in result.reason


def test_unweighted_sum_fails(rules):
    # 5+4+3+3+4 = 19: the model forgot the multipliers
    assert not check_score(make_run(output(total=19)), rules).passed


def test_judged_by_the_weights_in_the_runs_own_file():
    modified = read_rules(MODIFIED_SKILL)  # recency x4, directness x2: 20 + 8 + 6 + 3 + 4 = 41
    assert check_score(make_run(output(total=41)), modified).passed
    assert not check_score(make_run(output(total=40)), modified).passed
