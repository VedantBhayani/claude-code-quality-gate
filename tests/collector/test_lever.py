from datetime import date

from quality_gate.collector import Board, list_url, parse_board

from .ats_fixtures import COLLECTED, load


def test_lever_bare_array_is_normalised_with_created_at_date():
    board = Board(ats="lever", token="globex", company="Globex", domain="globex.de", eu=True)
    [post] = parse_board(board, load("lever_globex.json"), collection_date=COLLECTED)

    assert post.post_id == "lever:globex:a1b2c3d4-0000-4000-8000-000000000001"
    assert post.title == "Account Executive, DACH"
    assert post.url == "https://jobs.eu.lever.co/globex/a1b2c3d4-0000-4000-8000-000000000001"
    assert post.post_date == date(2025, 10, 8)  # createdAt 1759924800000 ms = 2025-10-08T12:00Z
    assert post.ats == "lever"
    assert "Globex is hiring its first Account Executive." in post.text
    assert "What you'll do" in post.text
    assert "Run discovery & demos" in post.text
    assert "We offer equity & benefits." in post.text
    assert "<" not in post.text


def test_lever_list_url_uses_eu_host_only_for_eu_boards():
    assert list_url(Board("lever", "globex", "Globex", "globex.de", eu=True)) == (
        "https://api.eu.lever.co/v0/postings/globex?mode=json"
    )
    assert list_url(Board("lever", "initech", "Initech", "initech.com")) == (
        "https://api.lever.co/v0/postings/initech?mode=json"
    )
