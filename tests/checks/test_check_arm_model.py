from checks_fixtures import load_run, make_run

from quality_gate.checks import check_arm_model, split_for_metrics
from quality_gate.config import load_config

PINNED = {arm["name"]: arm["model"] for arm in load_config().arms()}


def test_run_whose_model_usage_is_only_the_arms_pinned_model_passes():
    result = check_arm_model(make_run(), PINNED)
    assert result.name == "arm_model"
    assert result.passed, result.reason


def test_recorded_silent_model_switch_is_flagged_naming_the_other_model():
    result = check_arm_model(load_run("silent-model-switch"), PINNED)
    assert not result.passed
    assert "claude-opus-5-5" in result.reason and "claude-sonnet-5-5" in result.reason


def test_run_launched_with_a_model_other_than_its_arms_pin_is_flagged():
    run = make_run(model="claude-haiku-5-5", arm="sonnet-5-5")
    assert not check_arm_model(run, PINNED).passed


def test_run_with_no_model_usage_recorded_is_flagged():
    result = check_arm_model(make_run(model_usage_keys=()), PINNED)
    assert not result.passed
    assert "no modelUsage" in result.reason


def test_run_for_an_arm_with_no_pin_is_flagged():
    assert not check_arm_model(make_run(arm="mystery-arm"), PINNED).passed


def test_split_excludes_switched_runs_with_reason_and_keeps_failed_runs_as_failures():
    good = make_run(post_id="gh-1")
    switched = load_run("silent-model-switch")
    failed = load_run("max-structured-output-retries")
    split = split_for_metrics([good, switched, failed], PINNED)
    assert split.kept == [good, failed]
    assert [run for run, _ in split.excluded] == [switched]
    (_, reason), = split.excluded
    assert reason.name == "arm_model" and not reason.passed and "claude-opus-5-5" in reason.reason


def test_a_background_helper_model_is_not_a_switch_when_the_answer_is_the_pinned_model():
    run = make_run(model_usage_keys=("claude-haiku-5-5", "claude-sonnet-5-5"), answer_models=("claude-sonnet-5-5",))
    result = check_arm_model(run, PINNED)
    assert result.passed, result.reason
    assert "claude-haiku-5-5" in result.reason  # the helper is named, not hidden


def test_an_answer_written_by_another_model_is_a_switch_even_if_the_pin_appears():
    run = make_run(model_usage_keys=("claude-opus-5-5", "claude-sonnet-5-5"), answer_models=("claude-opus-5-5",))
    result = check_arm_model(run, PINNED)
    assert not result.passed
    assert "claude-opus-5-5" in result.reason


def test_an_unresolvable_answering_model_is_flagged():
    run = make_run(model_usage_keys=("claude-haiku-5-5", "claude-sonnet-5-5"), answer_models=())
    assert not check_arm_model(run, PINNED).passed
