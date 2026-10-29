import pytest
from checks_fixtures import INTENT_SIGNALS, MODIFIED_SKILL, make_run, output

from quality_gate.checks import check_tier
from quality_gate.skill_rules import read_rules


@pytest.fixture(scope="module")
def rules():
    return read_rules(INTENT_SIGNALS)


@pytest.mark.parametrize(
    "total, tier",
    [(0, "Noise"), (9, "Noise"), (10, "Low"), (19, "Low"), (20, "Medium"), (29, "Medium"),
     (30, "High"), (39, "High"), (40, "Critical"), (50, "Critical")],
)
def test_tier_matching_the_total_passes(rules, total, tier):
    result = check_tier(make_run(output(total=total, tier=tier)), rules)
    assert result.name == "tier"
    assert result.passed, result.reason


@pytest.mark.parametrize(
    "total, wrong_tier",
    [(9, "Low"), (10, "Noise"), (19, "Medium"), (20, "Low"), (29, "High"), (30, "Medium"),
     (39, "Critical"), (40, "High")],
)
def test_tier_off_by_one_point_fails_and_states_the_expected_tier(rules, total, wrong_tier):
    result = check_tier(make_run(output(total=total, tier=wrong_tier)), rules)
    assert not result.passed
    assert str(total) in result.reason and wrong_tier in result.reason


def test_judged_by_the_tier_table_in_the_runs_own_file():
    modified = read_rules(MODIFIED_SKILL)  # High starts at 35, Critical at 45
    run = make_run(output(total=42, tier="High"))
    assert check_tier(run, modified).passed
    assert not check_tier(run, read_rules(INTENT_SIGNALS)).passed
