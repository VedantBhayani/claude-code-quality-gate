import csv
import html
import io
import re

from gift_fixtures import make_post, make_run, passing_checks, yes

from quality_gate.config import load_config
from quality_gate.gift.render import render_csv, render_html
from quality_gate.gift.select import GIFT_FIELDS, select_gift

CONTACT_EVIDENCE = [
    "Questions? Email priya@example.com or call +1 415 555 0134 to join our first outbound team."
]


def _gift(package_root, n=3, evidence=None):
    rules = load_config(package_root).gate["gift"]
    posts = [make_post(f"p{i}", f"Co {i} <b>&", i + 1, title='SDR "Founding" <Team>') for i in range(n)]
    runs = [make_run(p.post_id, 40 - i, evidence=evidence) for i, p in enumerate(posts)]
    checks = {p.post_id: passing_checks() for p in posts}
    return posts, select_gift(posts, [yes(p.post_id) for p in posts], runs, checks, rules)


def _cells(text):
    return [cell for row in csv.reader(io.StringIO(text)) for cell in row]


def test_csv_has_the_locked_header_and_one_line_per_row(package_root):
    _, rows = _gift(package_root)
    parsed = list(csv.DictReader(io.StringIO(render_csv(rows))))
    assert tuple(parsed[0].keys()) == GIFT_FIELDS
    assert [r["company"] for r in parsed] == ["Co 0 <b>&", "Co 1 <b>&", "Co 2 <b>&"]


def test_why_now_cells_respect_the_word_limits(package_root):
    _, rows = _gift(package_root, evidence=["word " * 40])
    for row in csv.DictReader(io.StringIO(render_csv(rows))):
        assert len(row["why_now"].split()) <= 20
        assert len(row["why_now"].split('"')[1].split()) <= 12


def test_no_person_names_contact_data_or_post_text_in_any_output(package_root):
    posts, rows = _gift(package_root, evidence=CONTACT_EVIDENCE)
    outputs = {"csv": render_csv(rows), "html": render_html(rows)}
    for name, text in outputs.items():
        for forbidden in ("Priya", "Ramanathan", "@example.com", "555", "About us.", posts[0].text):
            assert forbidden not in text, (name, forbidden)
    for cell in _cells(outputs["csv"]):
        assert not re.search(r"[\w.+-]+@[\w-]+\.\w+", cell)
    for row in csv.DictReader(io.StringIO(outputs["csv"])):
        assert not re.search(r"(?:\d[\s().-]*){7,}", row["why_now"])


def test_html_is_one_self_contained_page_with_all_text_escaped(package_root):
    _, rows = _gift(package_root)
    page = render_html(rows)
    assert page.lstrip().lower().startswith("<!doctype html>")
    assert "<style>" in page
    lowered = page.lower()
    for external in ("<script", "<link", "src=", "@import", "url("):
        assert external not in lowered
    # Only post links point anywhere, and they are plain anchors.
    assert [html.unescape(h) for h in re.findall(r'href="([^"]+)"', page)] == [r.post_url for r in rows]
    assert "<b>" not in page and "Co 0 &lt;b&gt;&amp;" in page
    assert "&lt;Team&gt;" in page and "<Team>" not in page


def test_html_says_when_fewer_than_fifty_accounts_qualified(package_root):
    _, rows = _gift(package_root, n=2)
    assert "2 of 50" in render_html(rows)
    _, none = _gift(package_root, n=0)
    page = render_html(none)
    assert "0 of 50" in page and "<tr>" not in page.split("</thead>")[-1]


def test_non_http_post_urls_are_not_linked(package_root):
    _, rows = _gift(package_root, n=1)
    from dataclasses import replace

    bad = [replace(rows[0], post_url="javascript:alert(1)")]
    page = render_html(bad)
    assert "href" not in page
