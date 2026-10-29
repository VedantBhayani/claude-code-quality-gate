"""The gate end to end on recorded outputs (spec Resolution 1, the confirmed seam).

Recorded RunRecords + hand-written fixtures go in through `python -m quality_gate`;
results files come out. No model call anywhere.

Fixture set (tests/fixtures/e2e/, collection date 2026-10-20):
- natural sample: Acme (SDR, yes), Globex (AE, yes), Initech (VP Sales, yes, 20 days old),
  Hooli (retail, no); ambiguous subset: Initrode (Account Manager, yes), Vandelay (CSM, no).
- arms haiku-5-5 and sonnet-5-5, two repeats each (24 runs).
- one failed run: haiku run 2 on Initech (error_max_structured_output_retries).
- one silent model switch: sonnet run 1 on Hooli (modelUsage also has claude-opus-5-5).
- haiku run 1 says no on Globex and Initrode, gives Initech the wrong type and misstates
  Acme's total (40 for factors that sum to 38); haiku run 2 invents Globex's evidence.
- the blind re-label flips Initrode to no.

Expected values below are worked by hand from that design, not recomputed by the gate's code.
"""
import csv
import json
from pathlib import Path

import pytest

from quality_gate.cli import main

E2E = Path(__file__).resolve().parents[1] / "fixtures" / "e2e"


def rows(path):
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def part_a(tmp_path):
    out = tmp_path / "part-a"
    code = main([
        "gate",
        "--posts", str(E2E / "posts.jsonl"),
        "--samples", str(E2E / "samples.json"),
        "--labels", str(E2E / "labels_pass1.csv"),
        "--relabel", str(E2E / "labels_relabel.csv"),
        "--runs", str(E2E / "runs.jsonl"),
        "--out", str(out),
    ])
    assert code == 0
    return out


def test_gate_writes_the_part_a_results_files(part_a):
    assert sorted(p.name for p in part_a.iterdir()) == ["checks.csv", "excluded_runs.csv", "metrics.json", "summary.md"]


def test_silent_model_switch_run_is_excluded_and_flagged(part_a):
    [row] = rows(part_a / "excluded_runs.csv")
    assert (row["post_id"], row["arm"], row["repeat"]) == ("gh-hooli-1", "sonnet-5-5", "1")
    assert "silent model switch" in row["reason"] and "claude-opus-5-5" in row["reason"]
    metrics = json.loads((part_a / "metrics.json").read_text(encoding="utf-8"))
    [excluded] = metrics["excluded_runs"]
    assert excluded["post_id"] == "gh-hooli-1"
    natural = metrics["populations"]["natural sample"]["arms"]["sonnet-5-5"]["repeats"]
    assert natural["1"]["excluded_runs"] == 1 and natural["1"]["runs"] == 3
    summary = (part_a / "summary.md").read_text(encoding="utf-8")
    assert "silent model switch" in summary and "gh-hooli-1" in summary


def test_failed_run_is_kept_and_counted_as_a_failure(part_a):
    metrics = json.loads((part_a / "metrics.json").read_text(encoding="utf-8"))
    [failed] = metrics["failed_runs"]
    assert (failed["post_id"], failed["arm"], failed["repeat"]) == ("ab-initech-1", "haiku-5-5", 2)
    assert failed["failure_reason"] == "error_max_structured_output_retries"
    haiku = metrics["populations"]["natural sample"]["arms"]["haiku-5-5"]["repeats"]["2"]
    assert (haiku["runs"], haiku["failed_runs"]) == (4, 1)


def test_metrics_are_split_natural_and_ambiguous(part_a):
    pops = json.loads((part_a / "metrics.json").read_text(encoding="utf-8"))["populations"]
    assert sorted(pops) == ["ambiguous subset", "natural sample"]
    nat, amb = pops["natural sample"]["arms"], pops["ambiguous subset"]["arms"]
    # natural, yes/no: haiku run 1 = Y N Y N vs gold Y Y Y N -> (0.8 + 2/3) / 2
    assert nat["haiku-5-5"]["repeats"]["1"]["macro_f1_signal"] == pytest.approx(0.73333, abs=1e-4)
    assert nat["haiku-5-5"]["repeats"]["2"]["macro_f1_signal"] == pytest.approx(1.0)
    assert nat["sonnet-5-5"]["repeats"]["1"]["macro_f1_signal"] == pytest.approx(1.0)
    # repeat noise: haiku changes Globex between runs (Initech run 2 failed): 1 of 3
    assert nat["haiku-5-5"]["repeat_noise"]["signal"]["changed"] == 1
    assert nat["haiku-5-5"]["repeat_noise"]["signal"]["n"] == 3
    assert nat["sonnet-5-5"]["repeat_noise"]["signal"]["rate"] == 0
    assert nat["haiku-5-5"]["repeat_noise"]["macro_f1_signal_points"] == pytest.approx(26.6667, abs=1e-3)
    # ambiguous: haiku run 1 = N N vs gold Y N -> (0 + 2/3) / 2
    assert amb["haiku-5-5"]["repeats"]["1"]["macro_f1_signal"] == pytest.approx(0.33333, abs=1e-4)
    assert amb["haiku-5-5"]["repeat_noise"]["signal"]["rate"] == pytest.approx(0.5)


def test_threshold_verdicts_per_population(part_a):
    pops = json.loads((part_a / "metrics.json").read_text(encoding="utf-8"))["populations"]
    [nat] = pops["natural sample"]["comparisons"]
    assert (nat["baseline"], nat["candidate"], nat["kind"]) == ("sonnet-5-5", "haiku-5-5", "model switch")
    # Common posts with a kept run 1 on both arms: Acme, Globex, Initech (Hooli's sonnet run is excluded).
    assert nat["post_count"] == 3
    assert nat["macro_f1_signal"] == {"baseline": pytest.approx(1.0), "candidate": pytest.approx(0.4)}
    # F1 threshold = max(2 x 26.7, 3) = 53.3 points; drop is 60 points -> fail.
    assert nat["thresholds"]["macro_f1_drop"]["points"] == pytest.approx(53.3333, abs=1e-3)
    # flip threshold = largest noise 33.3 + 5 = 38.3 points; flip is 1 of 3 = 33.3 -> pass.
    assert nat["thresholds"]["flip_rate"]["points"] == pytest.approx(38.3333, abs=1e-3)
    verdicts = {v["name"]: v["passed"] for v in nat["verdicts"]}
    assert verdicts == {"macro_f1_drop": False, "flip_rate": True}
    assert nat["passed"] is False
    [amb] = pops["ambiguous subset"]["comparisons"]
    # drop 66.7 within max(2 x 66.7, 3) = 133.3; flip 50 within 50 + 5
    assert {v["name"]: v["passed"] for v in amb["verdicts"]} == {"macro_f1_drop": True, "flip_rate": True}


def test_rule_check_failures_are_reported_per_arm(part_a):
    nat = json.loads((part_a / "metrics.json").read_text(encoding="utf-8"))["populations"]["natural sample"]["arms"]
    fails = nat["haiku-5-5"]["check_failures"]
    assert fails["score"] == 1 and fails["evidence"] == 1 and fails["tier"] == 0
    assert fails["label_signal"] == 1 and fails["label_type"] == 2
    assert nat["sonnet-5-5"]["check_failures"] == {name: 0 for name in fails}
    checks = rows(part_a / "checks.csv")
    assert len(checks) == 24 * 8  # 5 rule checks + 2 label checks + arm model per run
    [arith] = [r for r in checks if r["check"] == "score" and r["passed"] == "false"
               and r["arm"] == "haiku-5-5" and r["repeat"] == "1"]
    assert arith["post_id"] == "gh-acme-1" and arith["population"] == "natural sample"


def test_label_agreement_kappa_is_gated_on_yes_no(part_a):
    agreement = json.loads((part_a / "metrics.json").read_text(encoding="utf-8"))["label_agreement"]
    # pass 1 Y Y Y N Y N vs re-label Y Y Y N N N: p_o 5/6, p_e 1/2 -> kappa 2/3
    assert agreement["signal_yes_no"]["kappa"] == pytest.approx(2 / 3)
    assert agreement["signal_yes_no"]["verdict"]["passed"] is False
    assert "verdict" not in agreement["signal_type"]


def test_summary_headlines_verdicts_and_uses_precise_terms(part_a):
    summary = (part_a / "summary.md").read_text(encoding="utf-8")
    assert "model switch" in summary
    assert "drift" not in summary.lower()
    headline = summary.split("## ")[1]
    assert "FAIL" in headline and "sonnet-5-5" in headline and "haiku-5-5" in headline


def test_gift_ranks_qualifying_accounts_by_sonnet_run_1(tmp_path):
    out = tmp_path / "gift"
    assert main([
        "gift",
        "--posts", str(E2E / "posts.jsonl"),
        "--labels", str(E2E / "labels_pass1.csv"),
        "--runs", str(E2E / "runs.jsonl"),
        "--out", str(out),
    ]) == 0
    gift = rows(out / "gift.csv")
    # Initech is 20 days old (outside 14); Hooli and Vandelay are labelled no.
    assert [(r["company"], r["score"], r["tier"]) for r in gift] == [
        ("Globex", "42", "Critical"), ("Acme", "38", "High"), ("Initrode", "30", "High"),
    ]
    assert gift[0]["why_now"] == 'Account Executive posted 10 days ago: "Join our first sales team in Austin as an Account Executive."'
    assert "score: pass" in gift[0]["check_results"] and "arm_model: pass" in gift[0]["check_results"]
    assert "3 of 50" in (out / "gift.html").read_text(encoding="utf-8")


def test_part_b_writes_failure_rates_and_worst_first(tmp_path):
    out = tmp_path / "part-b"
    assert main([
        "gate", "--part", "b",
        "--posts", str(E2E / "posts.jsonl"),
        "--runs", str(E2E / "runs.jsonl"),
        "--drafts", str(E2E / "drafts.jsonl"),
        "--out", str(out),
    ]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["checks.csv", "failure_rates.csv", "summary.md", "worst_first.csv"]
    worst = rows(out / "worst_first.csv")
    assert [r["post_id"] for r in worst] == ["lv-initrode-1", "lv-globex-1", "gh-acme-1"]
    assert worst[0]["failed_checks"].startswith("run failed")
    assert worst[1]["failed_checks"] == "spam_words"
    assert all(r["label"] == "sample" for r in worst)
    rates = {r["check"]: r for r in rows(out / "failure_rates.csv")}
    assert (rates["spam_words"]["failed"], rates["spam_words"]["checked"]) == ("1", "2")
    assert rates["first_line_signal"]["heuristic"] == "true"
    assert (rates["sign_off"]["failed"], rates["sign_off"]["checked"]) == ("0", "2")
    assert "sample" in (out / "summary.md").read_text(encoding="utf-8").lower()


def test_old_posts_get_a_fresh_only_population_beside_the_full_one(tmp_path):
    # The skill scores recency only up to 90 days; hand labels ignore age. Hooli is made
    # 141 days old, so the natural sample also gets a version without it.
    posts = tmp_path / "posts.jsonl"
    lines = []
    for line in (E2E / "posts.jsonl").read_text(encoding="utf-8").splitlines():
        post = json.loads(line)
        if post["post_id"] == "gh-hooli-1":
            post["post_date"] = "2026-06-01"
        lines.append(json.dumps(post))
    posts.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = tmp_path / "part-a"
    assert main(["gate", "--posts", str(posts), "--samples", str(E2E / "samples.json"),
                 "--labels", str(E2E / "labels_pass1.csv"), "--runs", str(E2E / "runs.jsonl"),
                 "--out", str(out)]) == 0
    pops = json.loads((out / "metrics.json").read_text(encoding="utf-8"))["populations"]
    assert sorted(pops) == ["ambiguous subset", "natural sample", "natural sample, posted within 90 days"]
    fresh = pops["natural sample, posted within 90 days"]["arms"]["haiku-5-5"]["repeats"]["1"]
    assert fresh["runs"] == 3
    assert pops["natural sample"]["arms"]["haiku-5-5"]["repeats"]["1"]["runs"] == 4
    assert "posted within 90 days" in (out / "summary.md").read_text(encoding="utf-8")
