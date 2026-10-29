"""Kenny's copy QA checklist (evals/skills/copy-frameworks/SKILL.md, "Copy QA Checklist"), checked in code.

Rules come from that text: subject 3-5 words, lowercase, and "Never use brackets, exclamation marks,
or emojis in subjects"; first line references a real signal (heuristic, Resolution 14); under 120
words (150 absolute max); grade 5-7; one question CTA, not "book a call"; all {{variables}} resolve;
no spam trigger words (free, guarantee, act now, limited time).
"""
import json
from pathlib import Path

import pytest

from quality_gate.copy_check.checklist import CHECK_NAMES, Draft, SignalContext, check_draft

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "drafts"
CONTEXT = SignalContext(role_title="Senior SDR", evidence=("We are building our first outbound SDR team in Austin.",))


def load(name: str) -> tuple[Draft, SignalContext, dict]:
    raw = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    draft = Draft(draft_id=raw["draft_id"], subject=raw["subject"], body=raw["body"])
    return draft, SignalContext(role_title=raw["role_title"], evidence=tuple(raw["evidence"])), raw


ALL_FIXTURES = sorted(p.stem for p in FIXTURES.glob("*.json"))


def results_by_name(draft: Draft, context: SignalContext = CONTEXT):
    results = check_draft(draft, context)
    return {r.name: r for r in results}


def test_one_result_per_checklist_item_in_order():
    draft, ctx, _ = load("pass")
    assert [r.name for r in check_draft(draft, ctx)] == list(CHECK_NAMES)


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_fixture_draft_fails_and_warns_exactly_as_expected(name):
    draft, ctx, raw = load(name)
    results = check_draft(draft, ctx)
    failed = {r.name for r in results if not r.passed}
    warned = {r.name for r in results if r.warning}
    assert failed == set(raw["expected_fails"]), [r.reason for r in results if not r.passed]
    assert warned == set(raw["expected_warns"])


@pytest.mark.parametrize("check", CHECK_NAMES)
def test_every_checklist_item_has_a_passing_and_a_failing_fixture(check):
    raws = [load(n)[2] for n in ALL_FIXTURES]
    assert any(check not in r["expected_fails"] for r in raws)
    assert any(r["expected_fails"] == [check] for r in raws), f"no fixture fails only {check}"


def test_every_failure_gives_a_reason():
    draft, ctx, _ = load("fail_many")
    for r in check_draft(draft, ctx):
        assert r.reason


def test_first_line_check_is_flagged_heuristic_and_others_are_exact():
    draft, ctx, _ = load("pass")
    flags = {r.name: r.heuristic for r in check_draft(draft, ctx)}
    assert flags.pop("first_line_signal") is True
    assert not any(flags.values())


@pytest.mark.parametrize(
    "subject, ok",
    [
        ("your new sdr team", True),
        ("sdr hiring", False),  # 2 words
        ("three to five words max now", False),  # 6 words
        ("Your new sdr team", False),  # not lowercase
        ("your [new] sdr team", False),  # brackets
        ("your (new) sdr team", False),
        ("your new sdr team!", False),
        ("your new sdr team \U0001F680", False),  # emoji
        ("outbound in austin", True),
    ],
)
def test_subject_rules(subject, ok):
    draft, _, _ = load("pass")
    r = results_by_name(Draft(draft.draft_id, subject, draft.body))["subject"]
    assert r.passed is ok, r.reason


@pytest.mark.parametrize(
    "extra, ok",
    [
        ("We are happy to help.", True),
        ("Feel free to ignore this.", False),
        ("We guarantee results.", False),
        ("It is guaranteed.", False),
        ("Act now to get it.", False),
        ("This is for a limited time.", False),
        ("Freedom to sell is key.", True),  # word boundary: "free" only as a word
    ],
)
def test_spam_words_match_whole_words(extra, ok):
    draft, _, _ = load("pass")
    body = draft.body.replace("warm accounts.", "warm accounts. " + extra)
    assert results_by_name(Draft(draft.draft_id, draft.subject, body))["spam_words"].passed is ok


def test_spam_words_in_subject_fail():
    draft, _, _ = load("pass")
    assert not results_by_name(Draft(draft.draft_id, "free sdr list today", draft.body))["spam_words"].passed


def test_unresolved_variable_in_subject_fails():
    draft, _, _ = load("pass")
    r = results_by_name(Draft(draft.draft_id, "{{companyName}} sdr team", draft.body))["variables"]
    assert not r.passed and "{{companyName}}" in r.reason


def test_first_line_matches_role_title_or_evidence_term_case_insensitively():
    base = load("pass")[0]
    by_title = Draft("t", base.subject, "Hi Sam,\n\nNice to see a senior sdr role open up.\n\nAlex")
    by_evidence = Draft("e", base.subject, "Hi Sam,\n\nThe Austin office is growing fast.\n\nAlex")
    generic = Draft("g", base.subject, "Hi Sam,\n\nHope the team is having a good week.\n\nAlex")
    assert results_by_name(by_title)["first_line_signal"].passed
    assert results_by_name(by_evidence)["first_line_signal"].passed
    assert not results_by_name(generic)["first_line_signal"].passed


def test_length_boundaries_count_body_words():
    base = load("pass")[0]

    def length(n: int):
        return results_by_name(Draft("l", base.subject, " ".join(["word"] * n)))["length"]

    assert length(119).passed and not length(119).warning
    assert length(120).passed and length(120).warning
    assert length(150).passed and length(150).warning
    assert not length(151).passed


def test_declared_merge_fields_resolve_and_others_do_not():
    # Kenny's rule: all {{variables}} resolve for every lead in the list. Fields the lead
    # list provides at send time resolve; any other variable does not.
    base = load("pass")[0]
    draft = Draft("m", base.subject, "Hi {{firstName}},\n\n" + base.body + "\n\n{{senderName}} at {{companyName}}")
    r = check_draft(draft, CONTEXT, merge_fields=frozenset({"{{firstName}}", "{{senderName}}"}))
    [variables] = [c for c in r if c.name == "variables"]
    assert not variables.passed and "{{companyName}}" in variables.reason and "{{firstName}}" not in variables.reason
    ok = Draft("m", base.subject, "Hi {{firstName}},\n\n" + base.body + "\n\n{{senderName}}")
    [variables] = [c for c in check_draft(ok, CONTEXT, merge_fields=frozenset({"{{firstName}}", "{{senderName}}"}))
                   if c.name == "variables"]
    assert variables.passed and "{{firstName}}" in variables.reason


def test_bracket_placeholder_in_body_is_unresolved():
    base = load("pass")[0]
    r = results_by_name(Draft("b", base.subject, base.body + "\n\n[Sender name]"))["variables"]
    assert not r.passed and "[Sender name]" in r.reason
