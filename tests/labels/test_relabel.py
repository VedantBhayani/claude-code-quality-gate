"""Blind re-label draw: 50 posts, pass-1 labels hidden, at least 3 days after pass 1."""
import csv
from datetime import date

import pytest

from quality_gate.labels import RelabelError, draw_relabel, export_sheet, validate_sheet

from test_sheet import fill, make_post

IDS = [f"p{i:03d}" for i in range(80)]


@pytest.fixture
def pass1(tmp_path):
    sheet = tmp_path / "pass1.csv"
    export_sheet([make_post(pid) for pid in IDS], sheet)
    fill(sheet, {pid: ("yes", "ae_hiring") for pid in IDS[:40]}, labelled_on="2026-10-20")
    fill(sheet, {pid: ("no", "not_signal") for pid in IDS[40:]}, labelled_on="2026-10-22")
    return sheet


def test_refuses_before_three_days_after_the_last_pass1_label(pass1, tmp_path):
    with pytest.raises(RelabelError, match="3 days"):
        draw_relabel(pass1, IDS, tmp_path / "relabel.csv", today=date(2026, 10, 24))
    assert not (tmp_path / "relabel.csv").exists()


def test_draws_50_blank_rows_three_days_after_pass1(pass1, tmp_path):
    out = tmp_path / "relabel.csv"
    drawn = draw_relabel(pass1, IDS, out, today=date(2026, 10, 25))
    assert len(drawn) == 50 and len(set(drawn)) == 50 and set(drawn) <= set(IDS)
    with out.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["post_id"] for r in rows] == drawn
    assert all(r["signal"] == r["signal_type"] == r["labelled_on"] == "" for r in rows)
    assert all(r["url"] == f"https://boards.example/{r['post_id']}" for r in rows)


def test_draw_is_reproducible_for_a_seed_and_not_in_sheet_order(pass1, tmp_path):
    a = draw_relabel(pass1, IDS, tmp_path / "a.csv", today=date(2026, 10, 25), seed=7)
    b = draw_relabel(pass1, IDS, tmp_path / "b.csv", today=date(2026, 10, 25), seed=7)
    assert a == b
    assert a != sorted(a)


def test_refuses_an_invalid_pass1_sheet(tmp_path):
    sheet = tmp_path / "pass1.csv"
    export_sheet([make_post(pid) for pid in IDS], sheet)
    with pytest.raises(RelabelError, match="pass-1"):
        draw_relabel(sheet, IDS, tmp_path / "relabel.csv", today=date(2026, 12, 1))


def test_refuses_when_fewer_posts_than_the_draw(pass1, tmp_path):
    with pytest.raises(RelabelError, match="100"):
        draw_relabel(pass1, IDS, tmp_path / "r.csv", today=date(2026, 10, 25), n=100)


def test_filled_relabel_sheet_validates_against_the_drawn_ids(pass1, tmp_path):
    out = tmp_path / "relabel.csv"
    drawn = draw_relabel(pass1, IDS, out, today=date(2026, 10, 25))
    fill(out, {pid: ("no", "not_signal") for pid in drawn}, labelled_on="2026-10-25")
    assert len(validate_sheet(out, drawn)) == 50
