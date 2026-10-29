"""run_batch on recorded CLI outputs: the runner's seam. No real `claude` call anywhere.

FakeInvoker replays tests/fixtures/cli/*; every behaviour is read back through
BatchResult and the run log (read_run_log), never through internals.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from quality_gate.runner import (
    AuthMethodError,
    FakeInvoker,
    ResumeTooEarlyError,
    RunJob,
    RunSettings,
    read_run_log,
    run_batch,
)
from quality_gate.runner.invoker import CliCall
from quality_gate.skill_rules import PreparedSkill

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "cli"
SCHEMA = json.loads(
    (Path(__file__).resolve().parents[2] / "src" / "quality_gate" / "schemas" / "signal_output.schema.json").read_text()
)
SKILL = PreparedSkill(source=Path("intent-signals/SKILL.md"), text="# skill\nrules\n", sha256="abc123")
SETTINGS = RunSettings(effort="cli-default", tools="", max_turns=2)
BEFORE_RESET = datetime(2026, 10, 22, tzinfo=timezone.utc)  # resetsAt in fixtures = 1792800000 (2026-10-24)
AFTER_RESET = datetime(2026, 11, 1, tzinfo=timezone.utc)


def fx(name):
    return (FIX / name).read_text(encoding="utf-8")


def job(post_id="p1", arm="haiku-5-5", repeat=1, model="claude-haiku-5-5"):
    return RunJob(post_id=post_id, arm=arm, model=model, repeat=repeat, prompt=f"post {post_id}", skill=SKILL, schema=SCHEMA)


def fake(*runs, auth="auth_status_claude_ai.json"):
    return FakeInvoker(auth_status=fx(auth), version=fx("version.txt"), runs=[fx(r) for r in runs])


def run(jobs, invoker, tmp_path, now=BEFORE_RESET, **kw):
    return run_batch(jobs, invoker=invoker, log_path=tmp_path / "runs.jsonl", settings=SETTINGS, now=now, **kw)


def test_success_records_output_model_usage_version_hash_effort_and_cost(tmp_path):
    result = run([job()], fake("success.json"), tmp_path)
    assert result.stop is None
    [rec] = result.records
    assert rec.structured_output["tier"] == "High"
    assert rec.failure_reason is None
    assert rec.model_usage_keys == ("claude-haiku-5-5",)
    assert (rec.cli_version, rec.skill_hash, rec.effort, rec.cost_usd) == ("2.1.302", "abc123", "cli-default", 0.0123)
    [entry] = read_run_log(tmp_path / "runs.jsonl").runs
    assert entry.record == rec
    assert entry.init_model == "claude-haiku-5-5"


def test_bare_result_object_is_parsed_too(tmp_path):
    [rec] = run([job()], fake("success_result_only.json"), tmp_path).records
    assert rec.structured_output is not None
    assert read_run_log(tmp_path / "runs.jsonl").runs[0].init_model is None


def test_every_model_usage_key_is_recorded_so_a_silent_switch_is_visible(tmp_path):
    [rec] = run([job()], fake("model_switch.json"), tmp_path).records
    assert rec.model_usage_keys == ("claude-haiku-5-5", "claude-haiku-5")


@pytest.mark.parametrize(
    "fixture, reason",
    [
        ("success_without_output.json", "structured_output missing"),
        ("invalid_output.json", "structured_output invalid"),
        ("retries_error.json", "error_max_structured_output_retries"),
    ],
)
def test_missing_invalid_or_retried_output_is_a_recorded_failed_run(tmp_path, fixture, reason):
    result = run([job(), job(post_id="p2")], fake(fixture, "success.json"), tmp_path)
    assert result.stop is None
    failed, ok = result.records
    assert failed.structured_output is None and reason in failed.failure_reason
    assert ok.structured_output is not None
    assert [e.record for e in read_run_log(tmp_path / "runs.jsonl").runs] == [failed, ok]


def test_rate_limit_stops_the_batch_and_records_resets_at(tmp_path):
    invoker = fake("rate_limit_stop.json", "success.json")
    result = run([job(), job(post_id="p2")], invoker, tmp_path)
    assert result.stop.reason == "rate_limit"
    assert result.stop.resets_at == 1792800000
    assert result.stop.key == ("p1", "haiku-5-5", 1)
    assert result.records == []
    assert len(invoker.run_calls) == 1  # p2 never ran
    log = read_run_log(tmp_path / "runs.jsonl")
    assert log.runs == [] and log.stops[-1].resets_at == 1792800000


@pytest.mark.parametrize("fixture", ["billing_stop.json", "billing_error_retry.json"])
def test_credits_or_billing_errors_stop_the_batch(tmp_path, fixture):
    invoker = fake(fixture, "success.json")
    result = run([job(), job(post_id="p2")], invoker, tmp_path)
    assert result.stop.reason == "billing"
    assert len(invoker.run_calls) == 1


def test_wrong_auth_method_refuses_to_start(tmp_path):
    invoker = fake("success.json", auth="auth_status_api_key.json")
    with pytest.raises(AuthMethodError, match="api_key"):
        run([job()], invoker, tmp_path)
    assert invoker.run_calls == []
    assert not (tmp_path / "runs.jsonl").exists()


def test_resume_skips_completed_keys_including_failed_runs(tmp_path):
    jobs = [job("p1"), job("p2"), job("p3")]
    first = run(jobs, fake("retries_error.json", "rate_limit_stop.json"), tmp_path)
    assert first.stop.key == ("p2", "haiku-5-5", 1)

    second_invoker = fake("success.json", "success.json")
    second = run(jobs, second_invoker, tmp_path, now=AFTER_RESET)
    assert second.stop is None
    assert second.skipped == [("p1", "haiku-5-5", 1)]
    assert [r.post_id for r in second.records] == ["p2", "p3"]
    assert [e.record.post_id for e in read_run_log(tmp_path / "runs.jsonl").runs] == ["p1", "p2", "p3"]


def test_resume_before_resets_at_refuses_without_calling_the_model(tmp_path):
    run([job("p1")], fake("rate_limit_stop.json"), tmp_path)
    invoker = fake("success.json")
    with pytest.raises(ResumeTooEarlyError):
        run([job("p1")], invoker, tmp_path, now=BEFORE_RESET)
    assert invoker.run_calls == []


def test_each_call_runs_in_an_empty_working_dir_with_the_skill_file_outside_it(tmp_path):
    invoker = fake("success.json")
    run([job()], invoker, tmp_path)
    [call] = invoker.run_calls
    assert call.cwd_listing == []
    skill_path = Path(call.argv[call.argv.index("--append-system-prompt-file") + 1])
    assert call.files[str(skill_path)] == SKILL.text
    assert Path(call.cwd) not in skill_path.parents
    assert "--bare" not in call.argv


def test_two_way_parallel_runs_everything_and_more_is_refused(tmp_path):
    result = run([job("p1"), job("p2"), job("p3")], fake("success.json", "success.json", "success.json"), tmp_path,
                 parallel=2)
    assert sorted(r.post_id for r in result.records) == ["p1", "p2", "p3"]
    with pytest.raises(ValueError, match="2-way"):
        run([job("p9")], fake("success.json"), tmp_path, parallel=3)


def _with_limits(name, five_hour, seven_day, resets=1792800000, weekly_resets=1793000000):
    msgs = json.loads(fx(name))
    msgs.insert(-1, {"type": "rate_limit_event", "rate_limit_info": {
        "status": "allowed", "overageStatus": "rejected", "isUsingOverage": False,
        "unifiedWindows": {"five_hour": {"utilization": five_hour, "resetsAt": resets},
                           "seven_day": {"utilization": seven_day, "resetsAt": weekly_resets}}}})
    return json.dumps(msgs)


def _fake_raw(*outputs):
    return FakeInvoker(auth_status=fx("auth_status_claude_ai.json"), version=fx("version.txt"), runs=list(outputs))


def test_a_five_hour_budget_cap_stops_after_the_run_that_crosses_it(tmp_path):
    invoker = _fake_raw(_with_limits("success.json", 0.79, 0.20), _with_limits("success.json", 0.81, 0.21),
                        _with_limits("success.json", 0.82, 0.21))
    result = run([job(), job(post_id="p2"), job(post_id="p3")], invoker, tmp_path, max_five_hour=0.8)
    assert [r.post_id for r in result.records] == ["p1", "p2"]  # p2 succeeded and is kept
    assert result.stop.reason == "budget" and result.stop.resets_at == 1792800000
    assert "five_hour" in result.stop.detail
    assert len(invoker.run_calls) == 2
    # resuming before the window resets is refused without a model call
    with pytest.raises(ResumeTooEarlyError):
        run([job(post_id="p3")], _fake_raw(), tmp_path, max_five_hour=0.8)


def test_a_weekly_budget_cap_stops_with_the_weekly_reset_time(tmp_path):
    invoker = _fake_raw(_with_limits("success.json", 0.10, 0.71), _with_limits("success.json", 0.11, 0.72))
    result = run([job(), job(post_id="p2")], invoker, tmp_path, max_seven_day=0.70)
    assert [r.post_id for r in result.records] == ["p1"]
    assert result.stop.reason == "budget" and result.stop.resets_at == 1793000000
    assert "seven_day" in result.stop.detail


def test_no_caps_means_no_budget_stop(tmp_path):
    invoker = _fake_raw(_with_limits("success.json", 0.95, 0.95))
    assert run([job()], invoker, tmp_path).stop is None


# Recorded 2026-10-27 22:10 UTC: 107 calls in one second exited 3221225794 (0xC0000142,
# STATUS_DLL_INIT_FAILED) with no output. Claude never started, so no model answered.
LAUNCH_FAILED = CliCall(3221225794, "", "")


def test_a_launch_failure_is_not_recorded_so_the_run_is_redone(tmp_path):
    invoker = FakeInvoker(auth_status=fx("auth_status_claude_ai.json"), version=fx("version.txt"),
                          runs=[fx("success.json"), LAUNCH_FAILED, fx("success.json")])
    result = run([job(), job(post_id="p2"), job(post_id="p3")], invoker, tmp_path)
    assert [r.post_id for r in result.records] == ["p1", "p3"]
    assert result.stop is None
    assert result.launch_failures == [("p2", "haiku-5-5", 1)]
    assert ("p2", "haiku-5-5", 1) not in read_run_log(tmp_path / "runs.jsonl").completed_keys()


def test_three_launch_failures_in_a_row_pause_the_batch(tmp_path):
    invoker = FakeInvoker(auth_status=fx("auth_status_claude_ai.json"), version=fx("version.txt"),
                          runs=[LAUNCH_FAILED] * 3 + [fx("success.json")])
    result = run([job(post_id=f"p{i}") for i in range(5)], invoker, tmp_path)
    assert result.stop.reason == "launch" and result.stop.resets_at is None
    assert len(invoker.run_calls) == 3 and result.records == []
    # no reset time: the next batch may start at once
    assert run([job(post_id="p4")], FakeInvoker(auth_status=fx("auth_status_claude_ai.json"),
               version=fx("version.txt"), runs=[fx("success.json")]), tmp_path).records


def test_a_model_error_result_is_still_a_recorded_failed_run(tmp_path):
    msgs = json.loads(fx("success.json"))
    msgs[-1].update({"subtype": "error_max_turns", "is_error": True})
    msgs[-1].pop("structured_output", None)
    invoker = FakeInvoker(auth_status=fx("auth_status_claude_ai.json"), version=fx("version.txt"),
                          runs=[CliCall(1, json.dumps(msgs), "")])
    result = run([job()], invoker, tmp_path)
    assert result.records[0].failure_reason.startswith("error result (subtype error_max_turns)")
