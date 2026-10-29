from datetime import date

from quality_gate.collector import Board, parse_board

from .ats_fixtures import COLLECTED, load


def test_greenhouse_post_is_normalised_with_first_published_date_and_plain_text():
    board = Board(ats="greenhouse", token="acme", company="Acme Robotics", domain="acme-robotics.example")
    [post] = parse_board(board, load("greenhouse_acme.json"), collection_date=COLLECTED)

    assert post.post_id == "greenhouse:acme:4012345"
    assert post.company == "Acme Robotics"
    assert post.domain == "acme-robotics.example"
    assert post.title == "Sales Development Representative"
    assert post.url == "https://job-boards.greenhouse.io/acme/jobs/4012345"
    assert post.post_date == date(2026, 10, 1)  # first_published, not updated_at (Oct 20)
    assert post.collection_date == COLLECTED
    assert post.ats == "greenhouse"
    assert "<" not in post.text and "&lt;" not in post.text and "&amp;" not in post.text
    assert "Acme Robotics builds warehouse automation." in post.text
    assert "What you'll do" in post.text
    assert "Sales & marketing alignment" in post.text
