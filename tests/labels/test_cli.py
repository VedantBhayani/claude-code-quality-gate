"""CLI: python -m quality_gate.labels <export|label|validate|draw-relabel>. Posts come from a local JSONL cache."""
import json
from dataclasses import asdict

from quality_gate.labels import main

from test_sheet import fill, make_post


def write_posts(path, posts):
    path.write_text(
        "".join(json.dumps(asdict(p), default=str) + "\n" for p in posts), encoding="utf-8"
    )


def test_export_then_validate(tmp_path, capsys):
    posts = tmp_path / "posts.jsonl"
    write_posts(posts, [make_post("p1"), make_post("p2")])
    sheet = tmp_path / "sheet.csv"
    assert main(["export", "--posts", str(posts), "--out", str(sheet)]) == 0
    assert main(["validate", "--posts", str(posts), "--sheet", str(sheet)]) == 1
    assert "p1" in capsys.readouterr().err
    fill(sheet, {"p1": ("yes", "ae_hiring"), "p2": ("no", "not_signal")})
    assert main(["validate", "--posts", str(posts), "--sheet", str(sheet)]) == 0
    assert "2 labels" in capsys.readouterr().out


def test_draw_relabel_refuses_too_soon(tmp_path, capsys):
    posts = tmp_path / "posts.jsonl"
    ids = [f"p{i}" for i in range(60)]
    write_posts(posts, [make_post(pid) for pid in ids])
    sheet = tmp_path / "pass1.csv"
    main(["export", "--posts", str(posts), "--out", str(sheet)])
    fill(sheet, {pid: ("no", "not_signal") for pid in ids}, labelled_on="2026-10-22")
    out = tmp_path / "relabel.csv"
    args = ["draw-relabel", "--posts", str(posts), "--pass1", str(sheet), "--out", str(out)]
    assert main(args + ["--today", "2026-10-24"]) == 1
    assert "3 days" in capsys.readouterr().err
    assert main(args + ["--today", "2026-10-25"]) == 0
    assert main(["validate", "--expected", str(out), "--sheet", str(out)]) == 1  # blank: unlabelled


def test_blind_label_refuses_a_prior_sheet(tmp_path, capsys):
    posts = tmp_path / "posts.jsonl"
    write_posts(posts, [make_post("p1")])
    sheet = tmp_path / "sheet.csv"
    main(["export", "--posts", str(posts), "--out", str(sheet)])
    rc = main(["label", "--posts", str(posts), "--sheet", str(sheet), "--blind", "--prior", str(sheet)])
    assert rc == 2
    assert "blind" in capsys.readouterr().err


def test_label_survives_emoji_on_a_non_utf8_terminal(tmp_path, monkeypatch):
    """Git Bash pipes stdout as cp1252 on Windows; 57 real posts carry emoji."""
    import dataclasses
    import io
    import sys

    posts = tmp_path / "posts.jsonl"
    post = dataclasses.replace(make_post("p1"), title="APPLY FOR SALES JOBS \U0001f680",
                               text="We are hiring → SDRs ✅")
    write_posts(posts, [post])
    sheet = tmp_path / "sheet.csv"
    main(["export", "--posts", str(posts), "--out", str(sheet)])
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(raw, encoding="cp1252"))
    monkeypatch.setattr(sys, "stdin", io.StringIO("q\n"))
    assert main(["label", "--posts", str(posts), "--sheet", str(sheet)]) == 0
    sys.stdout.flush()
    assert "\U0001f680" in raw.getvalue().decode("utf-8")
