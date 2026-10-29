"""Labelling sheet: export blank, validate filled. Hand-written fixtures only."""
import csv
from datetime import date
from pathlib import Path

import pytest

from quality_gate.labels import SheetError, export_sheet, validate_sheet
from quality_gate.types import HandLabel, Post


def make_post(post_id: str, title: str = "Account Executive", text: str = "We are hiring.") -> Post:
    return Post(
        post_id=post_id,
        company=f"Co {post_id}",
        domain=f"{post_id}.example",
        title=title,
        url=f"https://boards.example/{post_id}",
        post_date=date(2026, 10, 1),
        collection_date=date(2026, 10, 20),
        ats="greenhouse",
        text=text,
    )


def fill(path: Path, labels: dict[str, tuple[str, str]], labelled_on: str = "2026-10-21") -> None:
    """Fill a sheet as a human would in a spreadsheet: signal, signal_type, labelled_on."""
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        rows = list(reader)
    for row in rows:
        if row["post_id"] in labels:
            row["signal"], row["signal_type"] = labels[row["post_id"]]
            row["labelled_on"] = labelled_on
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def test_blank_sheet_has_metadata_but_no_post_text(tmp_path):
    sheet = tmp_path / "sheet.csv"
    export_sheet([make_post("p1", text="SECRET BODY TEXT")], sheet)
    content = sheet.read_text(encoding="utf-8")
    assert "https://boards.example/p1" in content
    assert "Co p1" in content and "Account Executive" in content and "2026-10-01" in content
    assert "SECRET BODY TEXT" not in content


def test_filled_sheet_validates_to_hand_labels(tmp_path):
    sheet = tmp_path / "sheet.csv"
    export_sheet([make_post("p1"), make_post("p2", title="Office Manager")], sheet)
    fill(sheet, {"p1": ("yes", "ae_hiring"), "p2": ("no", "not_signal")})
    labels = validate_sheet(sheet, expected_post_ids=["p1", "p2"])
    assert labels == [
        HandLabel(post_id="p1", signal=True, signal_type="ae_hiring"),
        HandLabel(post_id="p2", signal=False, signal_type="not_signal"),
    ]


def problems_for(sheet: Path, expected: list[str]) -> list[str]:
    with pytest.raises(SheetError) as exc:
        validate_sheet(sheet, expected_post_ids=expected)
    return exc.value.problems


def test_bad_signal_type_is_rejected(tmp_path):
    sheet = tmp_path / "sheet.csv"
    export_sheet([make_post("p1")], sheet)
    fill(sheet, {"p1": ("yes", "account_manager_hiring")})
    [problem] = problems_for(sheet, ["p1"])
    assert "p1" in problem and "account_manager_hiring" in problem


def test_signal_and_type_must_agree(tmp_path):
    sheet = tmp_path / "sheet.csv"
    export_sheet([make_post("p1"), make_post("p2")], sheet)
    fill(sheet, {"p1": ("yes", "not_signal"), "p2": ("no", "ae_hiring")})
    problems = problems_for(sheet, ["p1", "p2"])
    assert [p.split(":")[0] for p in problems] == ["p1", "p2"]


def test_missing_rows_are_reported_by_post_id(tmp_path):
    sheet = tmp_path / "sheet.csv"
    export_sheet([make_post("p1")], sheet)
    fill(sheet, {"p1": ("yes", "ae_hiring")})
    problems = problems_for(sheet, ["p1", "p2", "p3"])
    assert any("missing" in p and "p2" in p and "p3" in p for p in problems)


def test_unlabelled_row_is_reported(tmp_path):
    sheet = tmp_path / "sheet.csv"
    export_sheet([make_post("p1"), make_post("p2")], sheet)
    fill(sheet, {"p1": ("yes", "ae_hiring")})
    [problem] = problems_for(sheet, ["p1", "p2"])
    assert problem.startswith("p2:")


def test_duplicate_and_unexpected_rows_are_reported(tmp_path):
    sheet = tmp_path / "sheet.csv"
    export_sheet([make_post("p1"), make_post("p1"), make_post("zz")], sheet)
    fill(sheet, {"p1": ("yes", "ae_hiring"), "zz": ("no", "not_signal")})
    problems = problems_for(sheet, ["p1"])
    assert any("duplicate" in p and "p1" in p for p in problems)
    assert any("unexpected" in p and "zz" in p for p in problems)


def test_labelled_row_needs_an_iso_labelled_on_date(tmp_path):
    sheet = tmp_path / "sheet.csv"
    export_sheet([make_post("p1")], sheet)
    fill(sheet, {"p1": ("yes", "ae_hiring")}, labelled_on="21/10/2026")
    [problem] = problems_for(sheet, ["p1"])
    assert "labelled_on" in problem


def test_wrong_header_is_rejected(tmp_path):
    sheet = tmp_path / "sheet.csv"
    sheet.write_text("post_id,label\np1,yes\n", encoding="utf-8")
    [problem] = problems_for(sheet, ["p1"])
    assert "header" in problem
