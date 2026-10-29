"""Plan-limit readings from rate_limit_event (recorded: tests/fixtures/cli/real_haiku_verbose_with_limits.json).

Every run reports 5-hour and weekly utilization to two decimals, so a batch measures its
own usage. A run that reports overage in use stops the batch as billing: Pro limits only.
"""
import copy
import json
from pathlib import Path

from quality_gate.runner.output import interpret
from quality_gate.runner.runlog import LoggedRun, append_run, read_run_log
from quality_gate.types import RunRecord

def make_run():
    return RunRecord(post_id="p1", arm="sonnet-5-5", model="claude-sonnet-5-5", repeat=1, structured_output={},
                     failure_reason=None, model_usage_keys=("claude-sonnet-5-5",), cli_version="2.1.302",
                     skill_hash="h", effort="cli-default")


REAL = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "cli" /
                   "real_haiku_verbose_with_limits.json").read_text(encoding="utf-8"))


def test_utilization_and_overage_state_are_read_from_the_real_event():
    out = interpret(json.dumps(REAL), {"type": "object"})
    assert out.limits == {"five_hour": 0.07, "five_hour_resets_at": 1793115000, "seven_day": 0.13,
                          "seven_day_resets_at": 1793379600, "overage_status": "rejected",
                          "is_using_overage": False}
    assert out.stop is None


def test_overage_in_use_stops_the_batch_as_billing():
    msgs = copy.deepcopy(REAL)
    event = next(m for m in msgs if m["type"] == "rate_limit_event")
    event["rate_limit_info"]["isUsingOverage"] = True
    out = interpret(json.dumps(msgs), {"type": "object"})
    assert out.stop is not None and out.stop.reason == "billing"
    assert "overage" in out.stop.detail


def test_no_event_means_no_reading():
    msgs = [m for m in REAL if m["type"] != "rate_limit_event"]
    assert interpret(json.dumps(msgs), {"type": "object"}).limits is None


def test_limits_survive_the_run_log(tmp_path):
    log = tmp_path / "runs.jsonl"
    limits = {"five_hour": 0.07, "seven_day": 0.13, "overage_status": "rejected", "is_using_overage": False}
    append_run(log, LoggedRun(make_run(), "claude-sonnet-5-5", "success", "s1", "2026-10-27T00:00:00Z", limits))
    assert read_run_log(log).runs[0].limits == limits
