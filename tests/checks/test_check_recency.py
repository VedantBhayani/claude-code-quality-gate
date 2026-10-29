import pytest
from checks_fixtures import INTENT_SIGNALS, MODIFIED_SKILL, make_post, make_run, output

from quality_gate.checks import check_recency
from quality_gate.skill_rules import read_rules


@pytest.fixture(scope="module")
def rules():
    return read_rules(INTENT_SIGNALS)


@pytest.mark.parametrize(
    "age_days, band",
    [(0, "High"), (7, "High"), (8, "Medium"), (30, "Medium"), (31, "Low"), (90, "Low"), (91, "None")],
)
def test_band_matching_the_post_age_passes(rules, age_days, band):
    result = check_recency(make_run(output(recency_band=band)), make_post(days_ago=age_days), rules)
    assert result.name == "recency"
    assert result.passed, result.reason


@pytest.mark.parametrize(
    "age_days, wrong_band",
    [(7, "Medium"), (8, "High"), (30, "Low"), (31, "Medium"), (90, "None"), (91, "Low")],
)
def test_band_off_by_one_day_fails_and_states_age_and_expected_band(rules, age_days, wrong_band):
    result = check_recency(make_run(output(recency_band=wrong_band)), make_post(days_ago=age_days), rules)
    assert not result.passed
    assert f"{age_days} days" in result.reason


def test_judged_by_the_bands_in_the_runs_own_file():
    modified = read_rules(MODIFIED_SKILL)  # High <= 14 days
    run, post = make_run(output(recency_band="High")), make_post(days_ago=10)
    assert check_recency(run, post, modified).passed
    assert not check_recency(run, post, read_rules(INTENT_SIGNALS)).passed


def test_post_dated_after_collection_fails(rules):
    result = check_recency(make_run(output(recency_band="High")), make_post(days_ago=-1), rules)
    assert not result.passed
    assert "after the collection date" in result.reason
