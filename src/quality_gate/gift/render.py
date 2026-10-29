"""Render the gift as a CSV and as one self-contained HTML page.

The page has inline CSS only: no scripts, stylesheets, fonts or images are
loaded. Every piece of text is HTML-escaped, and only http(s) post URLs become
links.
"""
from __future__ import annotations

import csv
import html
import io
from typing import Sequence

from quality_gate.gift.select import GIFT_FIELDS, GiftRow

TOP_N = 50

_HEADINGS = {
    "company": "Company",
    "domain": "Domain",
    "role_title": "Role",
    "post_url": "Post",
    "posted_date": "Posted",
    "collection_date": "Collected",
    "signal_type": "Signal type",
    "why_now": "Why now",
    "score": "Score /50",
    "tier": "Tier",
    "check_results": "Our checks",
}

_CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a64;--line:#e4e1d8;--head:#f1eee6;--link:#1f5fa8}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--fg:#ecebe6;--muted:#a3a19a;--line:#33322e;--head:#21201d;--link:#8cb8ec}}
*{box-sizing:border-box}
body{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1200px;margin:0 auto}
h1{font-size:1.5rem;margin:0 0 4px}
p{color:var(--muted);margin:0 0 16px;max-width:70ch}
.wrap{overflow-x:auto;border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;min-width:900px}
th,td{padding:8px 10px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}
th{background:var(--head);font-weight:600;font-size:.85rem;white-space:nowrap}
td.num{text-align:right;font-variant-numeric:tabular-nums}
a{color:var(--link)}
.empty{padding:16px;color:var(--muted)}
"""


def render_csv(rows: Sequence[GiftRow]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(GIFT_FIELDS), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row.as_dict())
    return out.getvalue()


def _cell(field: str, value: object) -> str:
    text = html.escape(str(value), quote=True)
    if field == "post_url":
        url = str(value)
        if url.lower().startswith(("https://", "http://")):
            return f'<td><a href="{text}" rel="noopener noreferrer">open post</a></td>'
        return f"<td>{text}</td>"
    if field == "score":
        return f'<td class="num">{text}</td>'
    return f"<td>{text}</td>"


def render_html(rows: Sequence[GiftRow], top_n: int = TOP_N) -> str:
    head = "".join(f"<th>{html.escape(_HEADINGS[f])}</th>" for f in GIFT_FIELDS)
    body = "".join("<tr>" + "".join(_cell(f, getattr(r, f)) for f in GIFT_FIELDS) + "</tr>" for r in rows)
    if not rows:
        body = f'<tr class="none"><td class="empty" colspan="{len(GIFT_FIELDS)}">No accounts qualified.</td></tr>'
    summary = (
        f"{len(rows)} of {top_n} accounts. Each is a company whose open sales role we labelled as a buying "
        "signal, posted 14 days or less before collection, ranked by the skill's Sonnet 5.5 score. "
        "The why-now line quotes the post's own evidence. No person names or contact data."
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Accounts to email</title>"
        f"<style>{_CSS}</style></head>"
        "<body><main>"
        "<h1>Accounts to email this week</h1>"
        f"<p>{html.escape(summary)}</p>"
        f'<div class="wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'
        "</main></body></html>\n"
    )
