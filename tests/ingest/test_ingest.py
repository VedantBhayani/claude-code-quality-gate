"""Ingest: the data agent's seed + raw list responses -> Posts -> posts JSONL, samples, published fixture.

Fixtures are hand-written in tests/fixtures/ingest/ (no real companies or people).
"""
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from quality_gate.config import load_config
from quality_gate.gate import SampleIds
from quality_gate.ingest import IngestError, ingest, sales_ish, write_fixture, write_posts
from quality_gate.ingest import main as ingest_main
from quality_gate.labels import load_posts

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "ingest"


def test_posts_carry_seed_company_and_the_raw_files_collection_date():
    posts = {p.post_id: p for p in ingest(FIX / "seed.csv", FIX / "raw")}

    # Ashby isListed=false (init-0004) is dropped; _probe_cache/ is not read.
    assert sorted(posts) == ["ashby:initech:init-0001", "ashby:initech:init-0002",
                             "ashby:initech:init-0003", "lever:globex:glob-0001"]
    ae = posts["ashby:initech:init-0001"]
    assert (ae.company, ae.domain, ae.ats) == ("Initech", "initech.example", "ashby")
    assert ae.post_date == date(2026, 10, 20)
    assert ae.collection_date == date(2026, 10, 22)  # from ashby-initech-2026-10-22.json
    sdr = posts["lever:globex:glob-0001"]
    assert (sdr.company, sdr.domain) == ("Globex", "globex.example")
    assert sdr.post_date == date(2026, 10, 20)
    assert sdr.collection_date == date(2026, 10, 23)
    assert sdr.url == "https://jobs.lever.co/globex/glob-0001"
    assert "jobs@globex.example" not in sdr.text  # collector redaction applied


def test_the_posts_file_holds_the_sales_ish_posts_and_loads_back_unchanged(tmp_path, package_root):
    cfg = load_config(package_root)
    posts = sales_ish(ingest(FIX / "seed.csv", FIX / "raw"), cfg)
    assert [p.post_id for p in posts] == ["ashby:initech:init-0001", "ashby:initech:init-0002",
                                          "lever:globex:glob-0001"]  # Software Engineer is out

    out = tmp_path / "posts" / "posts.jsonl"
    write_posts(out, posts)
    assert load_posts(out) == posts


def test_post_text_with_unicode_line_separators_loads_back_as_one_post(tmp_path):
    # Real job text holds U+2028 / U+2029 / U+0085, which str.splitlines() treats as line breaks.
    [post] = [p for p in ingest(FIX / "seed.csv", FIX / "raw") if p.post_id == "lever:globex:glob-0001"]
    odd = replace(post, text="Line one line two para\x85next été")
    out = tmp_path / "posts.jsonl"
    write_posts(out, [odd])
    assert load_posts(out) == [odd]


def test_the_published_fixture_has_urls_and_metadata_but_no_post_text(tmp_path, package_root):
    cfg = load_config(package_root)
    posts = sales_ish(ingest(FIX / "seed.csv", FIX / "raw"), cfg)
    samples = SampleIds(natural=("lever:globex:glob-0001", "ashby:initech:init-0001"),
                        ambiguous=("ashby:initech:init-0002",), opus=("lever:globex:glob-0001",),
                        pilot=("ashby:initech:init-0001",))
    out = tmp_path / "fixtures" / "posts.csv"

    write_fixture(out, posts, samples, cfg)

    body = out.read_text(encoding="utf-8")
    assert body.splitlines() == [
        "post_id,company,domain,ats,title,url,post_date,collection_date,ambiguous_family,samples",
        "ashby:initech:init-0001,Initech,initech.example,ashby,\"Account Executive, Mid-Market\","
        "https://jobs.ashbyhq.com/initech/init-0001,2026-10-20,2026-10-22,,natural;pilot",
        "ashby:initech:init-0002,Initech,initech.example,ashby,Customer Success Manager,"
        "https://jobs.ashbyhq.com/initech/init-0002,2026-10-10,2026-10-22,csm,ambiguous",
        "lever:globex:glob-0001,Globex,globex.example,lever,Sales Development Representative,"
        "https://jobs.lever.co/globex/glob-0001,2026-10-20,2026-10-23,,natural;opus",
    ]
    assert "first SDR team" not in body and "new logos" not in body


def test_the_command_line_writes_posts_then_the_fixture_from_a_samples_file(tmp_path, capsys):
    posts_out = tmp_path / "posts.jsonl"
    code = ingest_main(["posts", "--seed", str(FIX / "seed.csv"), "--raw", str(FIX / "raw"),
                        "--out", str(posts_out)])
    assert code == 0
    assert "3 sales-ish posts (1 ambiguous) from 2 boards" in capsys.readouterr().out
    assert [p.post_id for p in load_posts(posts_out)] == [
        "ashby:initech:init-0001", "ashby:initech:init-0002", "lever:globex:glob-0001"]

    samples = tmp_path / "samples.json"
    samples.write_text('{"natural": ["ashby:initech:init-0001"], "ambiguous": ["ashby:initech:init-0002"], '
                       '"opus": [], "pilot": []}', encoding="utf-8")
    fixture = tmp_path / "posts.csv"
    code = ingest_main(["fixture", "--posts", str(posts_out), "--samples", str(samples), "--out", str(fixture)])
    assert code == 0
    rows = fixture.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 4 and rows[1].endswith(",natural") and rows[3].endswith(",,")


def test_the_command_line_reports_a_misaligned_collection_and_exits_1(tmp_path, capsys):
    seed, raw = _copy_fixture(tmp_path)
    (raw / "lever-globex-2026-10-23.json").unlink()
    code = ingest_main(["posts", "--seed", str(seed), "--raw", str(raw), "--out", str(tmp_path / "p.jsonl")])
    assert code == 1
    assert "no raw file for qualified board lever:globex" in capsys.readouterr().out
    assert not (tmp_path / "p.jsonl").exists()


def _copy_fixture(tmp_path: Path) -> tuple[Path, Path]:
    raw = tmp_path / "raw"
    raw.mkdir()
    for f in (FIX / "raw").glob("*.json"):
        (raw / f.name).write_bytes(f.read_bytes())
    seed = tmp_path / "seed.csv"
    seed.write_bytes((FIX / "seed.csv").read_bytes())
    return seed, raw


def test_a_raw_file_for_an_unqualified_board_is_an_error(tmp_path):
    seed, raw = _copy_fixture(tmp_path)
    (raw / "greenhouse-hooli-2026-10-22.json").write_text('{"jobs": []}', encoding="utf-8")
    with pytest.raises(IngestError, match="greenhouse-hooli-2026-10-22.json.*not a qualified board"):
        ingest(seed, raw)


def test_a_qualified_board_without_a_raw_file_is_an_error(tmp_path):
    seed, raw = _copy_fixture(tmp_path)
    (raw / "lever-globex-2026-10-23.json").unlink()
    with pytest.raises(IngestError, match="no raw file for qualified board lever:globex"):
        ingest(seed, raw)


def test_two_raw_files_for_one_board_is_an_error(tmp_path):
    seed, raw = _copy_fixture(tmp_path)
    (raw / "lever-globex-2026-10-24.json").write_text("[]", encoding="utf-8")
    with pytest.raises(IngestError, match="lever:globex has 2 raw files"):
        ingest(seed, raw)


def test_a_raw_file_name_without_ats_token_date_is_an_error(tmp_path):
    seed, raw = _copy_fixture(tmp_path)
    (raw / "initech.json").write_text("{}", encoding="utf-8")
    with pytest.raises(IngestError, match="initech.json.*<ats>-<token>-<YYYY-MM-DD>.json"):
        ingest(seed, raw)
