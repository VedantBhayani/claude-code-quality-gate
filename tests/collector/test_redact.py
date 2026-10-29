import pytest

from quality_gate.collector import Board, parse_board
from quality_gate.collector.redact import redact

from .ats_fixtures import COLLECTED, load


def test_collected_post_text_has_recruiter_name_and_email_redacted():
    board = Board(ats="greenhouse", token="acme", company="Acme Robotics", domain="acme-robotics.example")
    [post] = parse_board(board, load("greenhouse_acme.json"), collection_date=COLLECTED)

    assert "Jane" not in post.text and "Doe" not in post.text
    assert "@" not in post.text
    assert "Contact our recruiter [name] at [email]." in post.text


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Email talent@globex.de to apply.", "Email [email] to apply."),
        ("Recruiter: Maria Lopez-Garcia", "Recruiter: [name]"),
        ("Reach out to Sam O'Neil with questions.", "Reach out to [name] with questions."),
        ("Your talent partner is Priya Raman.", "Your talent partner is [name]."),
        ("Questions go to Tom Baker, Senior Technical Recruiter.", "Questions go to [name], Senior Technical Recruiter."),
        ("Call +1 (415) 555-0134 today.", "Call [phone] today."),
        ("See linkedin.com/in/jane-doe-123 for more.", "See [profile] for more."),
    ],
)
def test_personal_data_is_redacted(raw, expected):
    assert redact(raw) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Contact Sales teams across EMEA and grow ARR 3x.",
        "You will report to the VP of Sales and work with Revenue Operations.",
        "Founded in 2019, we raised a $40M Series B in 2025.",
    ],
)
def test_ordinary_post_text_is_left_alone(text):
    assert redact(text) == text
