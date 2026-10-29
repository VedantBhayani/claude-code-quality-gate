"""Hand-written fixtures for the gift builder: Posts, HandLabels, Sonnet run-1 RunRecords."""
from datetime import date, timedelta

from quality_gate.types import CheckResult, HandLabel, Post, RunRecord

COLLECTED = date(2026, 10, 20)

GIFT_RULES = {
    "window_days": 14,
    "rank_by_arm": "sonnet-5-5",
    "rank_by_repeat": 1,
    "top_n": 50,
    "why_now_quote_max_words": 12,
    "why_now_max_words": 20,
}


def make_post(post_id, company, days_ago, title="Sales Development Representative", text=None, domain=None):
    return Post(
        post_id=post_id,
        company=company,
        domain=domain or f"{company.lower().replace(' ', '')}.com",
        title=title,
        url=f"https://boards.greenhouse.io/{company.lower().replace(' ', '')}/jobs/{post_id}",
        post_date=COLLECTED - timedelta(days=days_ago),
        collection_date=COLLECTED,
        ats="greenhouse",
        text=text
        or (
            "About us. We are building our first outbound team to open new markets. "
            "Recruiter: Priya Ramanathan, priya@example.com, +1 415 555 0134."
        ),
    )


def make_run(post_id, total, tier="High", arm="sonnet-5-5", repeat=1, model="claude-sonnet-5-5", evidence=None):
    return RunRecord(
        post_id=post_id,
        arm=arm,
        model=model,
        repeat=repeat,
        structured_output={
            "signal": True,
            "signal_type": "sdr_bdr_hiring",
            "evidence": evidence or ["We are building our first outbound team to open new markets."],
            "total": total,
            "tier": tier,
        },
        failure_reason=None,
        model_usage_keys=(model,),
        cli_version="2.5.0",
        skill_hash="abc",
        effort="cli-default",
    )


def yes(post_id, signal_type="sdr_bdr_hiring"):
    return HandLabel(post_id=post_id, signal=True, signal_type=signal_type)


def no(post_id):
    return HandLabel(post_id=post_id, signal=False, signal_type="not_signal")


def passing_checks():
    return [
        CheckResult(name="evidence", passed=True, reason="quote found"),
        CheckResult(name="tier", passed=False, reason="tier High but score 41"),
        CheckResult(name="first_line_signal", passed=True, reason="ok", heuristic=True),
    ]

