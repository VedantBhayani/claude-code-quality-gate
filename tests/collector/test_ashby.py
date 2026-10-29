from datetime import date

from quality_gate.collector import Board, parse_board

from .ats_fixtures import COLLECTED, load

BOARD = Board(ats="ashby", token="initech", company="Initech", domain="initech.com")


def test_ashby_listed_post_is_normalised_with_published_at_date():
    [post] = parse_board(BOARD, load("ashby_initech.json"), collection_date=COLLECTED)

    assert post.post_id == "ashby:initech:0f9e8d7c-1111-4222-8333-444455556666"
    assert post.title == "Head of Revenue Operations"
    assert post.url == "https://jobs.ashbyhq.com/initech/0f9e8d7c-1111-4222-8333-444455556666"
    assert post.post_date == date(2026, 10, 15)
    assert post.ats == "ashby"
    assert "You will own Salesforce & our GTM data." in post.text


def test_ashby_unlisted_post_is_dropped():
    posts = parse_board(BOARD, load("ashby_initech.json"), collection_date=COLLECTED)

    assert [p.title for p in posts] == ["Head of Revenue Operations"]
