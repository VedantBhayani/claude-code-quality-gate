"""The model-calling subcommands (pilot, run, drafts) and `sample`, through `python -m quality_gate`.

pilot/run/drafts call the model only through the runner's invocation interface; here that is
FakeInvoker replaying tests/fixtures/cli/*. No real `claude` call, no network, nothing under data/.
"""
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from quality_gate.cli import main
from quality_gate.runner import FakeInvoker, read_run_log

TESTS = Path(__file__).resolve().parents[1]
E2E = TESTS / "fixtures" / "e2e"
CLI = TESTS / "fixtures" / "cli"
PACKAGE = TESTS.parent
BEFORE_RESET = datetime(2026, 10, 22, tzinfo=timezone.utc)  # fixtures' resetsAt is 2026-10-24
PILOT_FACTS = 'tools_flag = ""\nmax_turns = 2\nhaiku_4_5_probe_passed = false\n'


def fx(name):
    return (CLI / name).read_text(encoding="utf-8")


def fake(*outputs):
    return FakeInvoker(auth_status=fx("auth_status_claude_ai.json"), version=fx("version.txt"), runs=list(outputs))


def draft_output(subject, body):
    """success.json with the structured output swapped for a draft."""
    msgs = json.loads(fx("success.json"))
    msgs[-1]["structured_output"] = {"subject": subject, "body": body}
    msgs[1]["message"]["content"][0]["input"] = {"subject": subject, "body": body}
    msgs[-1]["modelUsage"] = {"claude-sonnet-5-5": msgs[-1]["modelUsage"]["claude-haiku-5-5"]}
    return json.dumps(msgs)


@pytest.fixture
def config(config_root):
    (config_root / "config" / "title_filter.toml").write_bytes((PACKAGE / "config" / "title_filter.toml").read_bytes())
    return config_root


@pytest.fixture
def with_pilot_facts(config):
    (config / "config" / "facts" / "pilot.toml").write_text(PILOT_FACTS, encoding="utf-8")
    return config


def samples_with(tmp_path, **extra):
    d = json.loads((E2E / "samples.json").read_text(encoding="utf-8"))
    d.update(extra)
    path = tmp_path / "samples.json"
    path.write_text(json.dumps(d), encoding="utf-8")
    return path


def cli(config, *argv, invoker=None, ask=None):
    out = io.StringIO()
    kw = {"invoker": invoker, "out": out, "now": BEFORE_RESET}
    if ask is not None:
        kw["ask"] = ask
    code = main(["--config", str(config), *argv], **kw)
    return code, out.getvalue()


def prompt_of(call):
    return call.argv[-1]


# ---------------------------------------------------------------- sample


def test_sample_draws_reproducible_samples_and_a_pilot_set(config, tmp_path):
    out = tmp_path / "s.json"
    args = ("sample", "--posts", str(E2E / "posts.jsonl"), "--out", str(out),
            "--natural", "3", "--ambiguous", "2", "--opus", "2", "--pilot", "2")
    assert cli(config, *args)[0] == 0
    first = json.loads(out.read_text(encoding="utf-8"))
    assert (len(first["natural"]), len(first["ambiguous"]), len(first["opus"]), len(first["pilot"])) == (3, 2, 2, 2)
    assert sorted(first["ambiguous"]) == ["ab-vandelay-1", "lv-initrode-1"]  # Account Manager, CSM
    assert set(first["opus"]) <= set(first["natural"]) and set(first["pilot"]) <= set(first["natural"])
    assert cli(config, *args)[0] == 0
    assert json.loads(out.read_text(encoding="utf-8")) == first


def test_sample_fresh_per_company_writes_one_fresh_post_per_company(config, tmp_path):
    out = tmp_path / "fresh.json"
    code, text = cli(config, "sample", "--posts", str(E2E / "posts.jsonl"), "--out", str(out),
                     "--fresh-per-company", "14")
    assert code == 0
    d = json.loads(out.read_text(encoding="utf-8"))
    # Initech's VP of Sales is 20 days old: outside the window. Retail Sales Associate passes the
    # title filter (the hand label is what rejects it).
    assert d["natural"] == ["gh-acme-1", "gh-hooli-1", "lv-globex-1"]
    assert d["ambiguous"] == ["ab-vandelay-1", "lv-initrode-1"]
    assert d["opus"] == [] and d["pilot"] == []
    assert d["sizes"]["window_days"] == 14
    assert "natural 3, ambiguous 2" in text


def test_sample_sizes_are_facts_and_fail_loudly_when_missing(config, tmp_path):
    code, text = cli(config, "sample", "--posts", str(E2E / "posts.jsonl"), "--out", str(tmp_path / "s.json"))
    assert code == 2 and "pilot.natural_sample_size" in text
    assert not (tmp_path / "s.json").exists()


# ---------------------------------------------------------------- pilot


def test_pilot_probes_find_the_flags_and_try_old_haiku(config, tmp_path):
    samples = samples_with(tmp_path, pilot=["gh-acme-1", "lv-globex-1"])
    invoker = fake(fx("success_without_output.json"), fx("success.json"), fx("retries_error.json"))
    code, text = cli(config, "pilot", "--probes", "--posts", str(E2E / "posts.jsonl"), "--samples", str(samples),
                     "--log-dir", str(tmp_path / "pilot"), invoker=invoker)
    assert code == 0
    turns = [c.argv[c.argv.index("--max-turns") + 1] for c in invoker.run_calls]
    assert turns == ["1", "2", "2"]
    assert all(c.argv[c.argv.index("--tools") + 1] == "" for c in invoker.run_calls)
    assert invoker.run_calls[2].argv[invoker.run_calls[2].argv.index("--model") + 1] == "claude-haiku-4-5-20251001"
    probes = json.loads((tmp_path / "pilot" / "probes.json").read_text(encoding="utf-8"))
    assert probes["chosen"] == {"tools_flag": "", "max_turns": 2}
    assert probes["haiku_4_5_probe"]["passed"] is False
    assert "haiku_4_5_probe_passed = false" in text and "max_turns = 2" in text


def test_pilot_model_runs_ten_posts_twice_and_records_usage_readings(with_pilot_facts, tmp_path):
    ids = ["gh-acme-1", "lv-globex-1", "ab-initech-1"]
    samples = samples_with(tmp_path, pilot=ids)
    invoker = fake(*[fx("success.json")] * 6)
    answers = iter(["10", "12.5%", "3", "3.4"])
    code, _ = cli(with_pilot_facts, "pilot", "--model", "haiku", "--posts", str(E2E / "posts.jsonl"),
                  "--samples", str(samples), "--log-dir", str(tmp_path / "pilot"), invoker=invoker,
                  ask=lambda _prompt: next(answers))
    assert code == 0
    records = read_run_log(tmp_path / "pilot" / "runs.jsonl").records
    assert sorted((r.post_id, r.repeat) for r in records) == sorted((i, r) for i in ids for r in (1, 2))
    assert {r.arm for r in records} == {"haiku-5-5"}
    [reading] = [json.loads(line) for line in (tmp_path / "pilot" / "usage.jsonl").read_text().splitlines()]
    assert (reading["five_hour_before"], reading["five_hour_after"], reading["weekly_after"]) == (10, 12.5, 3.4)
    assert reading["runs_this_batch"] == 6


def test_pilot_model_refuses_to_start_until_the_flag_facts_exist(config, tmp_path):
    samples = samples_with(tmp_path, pilot=["gh-acme-1"])
    invoker = fake(fx("success.json"))
    code, text = cli(config, "pilot", "--model", "sonnet", "--posts", str(E2E / "posts.jsonl"),
                     "--samples", str(samples), "--log-dir", str(tmp_path / "pilot"), "--no-usage-prompt",
                     invoker=invoker)
    assert code == 2 and "pilot.tools_flag" in text
    assert invoker.run_calls == []


# ---------------------------------------------------------------- run


def test_run_plans_every_post_arm_repeat_and_caps_a_batch(with_pilot_facts, tmp_path):
    samples = samples_with(tmp_path, opus=["gh-acme-1", "lv-globex-1"])
    invoker = fake(*[fx("success.json")] * 3)
    code, text = cli(with_pilot_facts, "run", "--posts", str(E2E / "posts.jsonl"), "--samples", str(samples),
                     "--log", str(tmp_path / "runs.jsonl"), "--max-runs", "3", invoker=invoker)
    assert code == 0
    assert len(read_run_log(tmp_path / "runs.jsonl").records) == 3
    # haiku 6 posts x 2 + sonnet 6 x 2 + opus 2-post subset x 1 = 26 planned; Haiku 4.5 is off (probe failed)
    assert "23 of 26 planned runs still to do" in text
    offer_line = "Source: https://frontal.so/services/gtm-engineering"
    assert all(offer_line in prompt_of(c) for c in invoker.run_calls)


def test_run_can_be_limited_to_named_arms_and_the_first_repeats(with_pilot_facts, tmp_path):
    samples = samples_with(tmp_path, opus=["gh-acme-1"])
    log = tmp_path / "runs.jsonl"
    invoker = fake(*[fx("success.json")] * 6)
    code, text = cli(with_pilot_facts, "run", "--posts", str(E2E / "posts.jsonl"), "--samples", str(samples),
                     "--log", str(log), "--arm", "sonnet-5-5", "--repeats", "1", invoker=invoker)
    assert code == 0
    records = read_run_log(log).records
    assert {(r.arm, r.repeat) for r in records} == {("sonnet-5-5", 1)}
    assert len(records) == 6 and "0 of 6 planned runs still to do" in text
    # A later full run sees these as done: same (post, arm, repeat) keys.
    invoker = fake(*[fx("success.json")] * 1)
    code, text = cli(with_pilot_facts, "run", "--posts", str(E2E / "posts.jsonl"), "--samples", str(samples),
                     "--log", str(log), "--arm", "sonnet-5-5", "--arm", "haiku-5-5", "--max-runs", "1",
                     invoker=invoker)
    assert code == 0 and "17 of 24 planned runs still to do" in text


def test_run_rejects_an_unknown_arm_before_any_model_call(with_pilot_facts, tmp_path):
    invoker = fake()
    code, text = cli(with_pilot_facts, "run", "--posts", str(E2E / "posts.jsonl"),
                     "--samples", str(samples_with(tmp_path)), "--log", str(tmp_path / "runs.jsonl"),
                     "--arm", "gpt-9", invoker=invoker)
    assert code == 1 and "gpt-9" in text
    assert invoker.run_calls == []


def test_run_stops_on_a_rate_limit_and_will_not_resume_before_the_reset(with_pilot_facts, tmp_path):
    args = ("run", "--posts", str(E2E / "posts.jsonl"), "--samples", str(samples_with(tmp_path)),
            "--log", str(tmp_path / "runs.jsonl"))
    code, text = cli(with_pilot_facts, *args, invoker=fake(fx("success.json"), fx("rate_limit_stop.json")))
    assert code == 3 and "STOPPED on a rate limit" in text and "Resets at 2026-10-24" in text
    again = fake(fx("success.json"))
    code, text = cli(with_pilot_facts, *args, invoker=again)
    assert code == 3 and "not yet" in text
    assert again.run_calls == []


def test_run_flags_a_silent_model_switch(with_pilot_facts, tmp_path):
    code, text = cli(with_pilot_facts, "run", "--posts", str(E2E / "posts.jsonl"), "--samples",
                     str(samples_with(tmp_path)), "--log", str(tmp_path / "runs.jsonl"), "--max-runs", "1",
                     invoker=fake(fx("model_switch.json")))
    assert code == 0 and "FLAG model mismatch" in text


# ---------------------------------------------------------------- drafts


def test_drafts_writes_one_sample_draft_per_gift_account_then_part_b_checks_them(with_pilot_facts, tmp_path):
    ok = json.loads((TESTS / "fixtures" / "drafts" / "pass.json").read_text(encoding="utf-8"))
    invoker = fake(*[draft_output(ok["subject"], ok["body"])] * 3)
    log = tmp_path / "drafts.jsonl"
    code, text = cli(with_pilot_facts, "drafts", "--posts", str(E2E / "posts.jsonl"),
                     "--labels", str(E2E / "labels_pass1.csv"), "--runs", str(E2E / "runs.jsonl"),
                     "--log", str(log), invoker=invoker)
    assert code == 0 and "sample" in text
    records = read_run_log(log).records
    # gift order: Globex, Acme, Initrode (Resolution 10); all three qualify, nothing beyond.
    assert [r.post_id for r in records] == ["lv-globex-1", "gh-acme-1", "lv-initrode-1"]
    assert all(r.structured_output == {"subject": ok["subject"], "body": ok["body"]} for r in records)
    first = invoker.run_calls[0]
    assert '"Join our first sales team in Austin as an Account Executive."' in prompt_of(first)
    assert "Source: https://frontal.so/services/gtm-engineering" in prompt_of(first)
    skill_file = first.argv[first.argv.index("--append-system-prompt-file") + 1]
    copy_skill = (PACKAGE / "evals" / "skills" / "copy-frameworks" / "SKILL.md").read_text(encoding="utf-8")
    assert first.files[skill_file].strip() == copy_skill.replace("\r\n", "\n").strip()
    assert json.loads(first.argv[first.argv.index("--json-schema") + 1])["required"] == ["subject", "body"]

    out = tmp_path / "part-b"
    code, _ = cli(with_pilot_facts, "gate", "--part", "b", "--posts", str(E2E / "posts.jsonl"),
                  "--runs", str(E2E / "runs.jsonl"), "--drafts", str(log), "--out", str(out))
    assert code == 0 and (out / "worst_first.csv").exists()


def test_run_does_not_flag_claude_codes_background_haiku_call_as_a_switch(with_pilot_facts, tmp_path):
    """Recorded on 2.1.302: every run also bills a small call to claude-haiku-5-5."""
    real = fx("real_sonnet_with_haiku_helper.json")
    invoker = fake(real)
    code, text = cli(with_pilot_facts, "run", "--posts", str(E2E / "posts.jsonl"),
                     "--samples", str(samples_with(tmp_path)), "--log", str(tmp_path / "runs.jsonl"),
                     "--arm", "sonnet-5-5", "--max-runs", "1", invoker=invoker)
    assert code == 0
    assert "FLAG" not in text
    rec = read_run_log(tmp_path / "runs.jsonl").records[0]
    assert rec.answer_models == ("claude-sonnet-5-5",)
    assert rec.model_usage_keys == ("claude-haiku-5-5", "claude-sonnet-5-5")


def test_run_pauses_at_the_default_five_hour_cap_and_says_when_to_resume(with_pilot_facts, tmp_path):
    msgs = json.loads(fx("success.json"))
    msgs.insert(-1, {"type": "rate_limit_event", "rate_limit_info": {
        "status": "allowed", "overageStatus": "rejected", "isUsingOverage": False,
        "unifiedWindows": {"five_hour": {"utilization": 0.80, "resetsAt": 1792800000},
                           "seven_day": {"utilization": 0.30, "resetsAt": 1793000000}}}})
    invoker = fake(json.dumps(msgs), json.dumps(msgs))
    code, text = cli(with_pilot_facts, "run", "--posts", str(E2E / "posts.jsonl"),
                     "--samples", str(samples_with(tmp_path)), "--log", str(tmp_path / "runs.jsonl"), invoker=invoker)
    assert code == 3
    assert "PAUSED at the budget cap" in text and "five_hour" in text
    assert len(invoker.run_calls) == 1
