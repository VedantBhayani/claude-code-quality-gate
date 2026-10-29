"""Prompts: one post + collection date + offer (signal); account + signal + offer (draft)."""
from datetime import date

from quality_gate.runner import draft_prompt, read_offer_wording, signal_prompt
from quality_gate.types import Post

POST = Post(
    post_id="gh-1",
    company="Acme",
    domain="acme.com",
    title="Founding SDR",
    url="https://boards.greenhouse.io/acme/jobs/1",
    post_date=date(2026, 10, 15),
    collection_date=date(2026, 10, 20),
    ats="greenhouse",
    text="We are building our first outbound team.",
)
OFFER = "GTM engineering for B2B tech companies."


def test_signal_prompt_holds_exactly_one_post_its_dates_and_the_offer():
    prompt = signal_prompt(POST, OFFER)
    for part in ("Acme", "Founding SDR", "2026-10-15", "2026-10-20", POST.text, OFFER, POST.url):
        assert part in prompt
    assert prompt.count("We are building our first outbound team.") == 1


def test_draft_prompt_holds_account_signal_and_offer():
    prompt = draft_prompt(company="Acme", domain="acme.com", role_title="Founding SDR",
                          evidence=["first outbound team"], offer=OFFER)
    for part in ("Acme", "acme.com", "Founding SDR", "first outbound team", OFFER):
        assert part in prompt


def test_offer_wording_is_read_verbatim_from_the_offer_fact_file(package_root):
    offer = read_offer_wording(package_root / "config" / "facts" / "offer.md")
    assert offer.startswith("Source: https://frontal.so/services/gtm-engineering")
    assert "Senior GTM engineers, embedded in your team." in offer
    assert "Use this exact text" not in offer
    assert "captured:" not in offer


def test_draft_prompt_fixes_greeting_and_sign_off_merge_fields():
    from quality_gate.runner.prompts import DRAFT_MERGE_FIELDS
    prompt = draft_prompt(company="Acme", domain="acme.com", role_title="Founding SDR",
                          evidence=["first outbound team"], offer=OFFER)
    assert DRAFT_MERGE_FIELDS == frozenset({"{{firstName}}", "{{senderName}}"})
    for field in DRAFT_MERGE_FIELDS:
        assert field in prompt
    assert "no other name" in prompt
