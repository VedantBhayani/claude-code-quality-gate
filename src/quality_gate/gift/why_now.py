"""The gift's "why now" line (Resolution 11): a deterministic template, no model.

    <role title> posted <N> days ago: "<evidence quote of 12 words or fewer>"

The quote is the skill's own evidence, trimmed; nothing is rewritten or made up.
Contact data (emails, phone numbers, links) is removed from the quote, and the
whole line is kept to 20 words or fewer.
"""
from __future__ import annotations

import re

QUOTE_MAX_WORDS = 12
LINE_MAX_WORDS = 20
ELLIPSIS = "…"

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_PHONE_CANDIDATE = re.compile(r"\+?\(?\d[\d\s().-]{5,}\d")


def _strip_contact_data(text: str) -> str:
    text = _EMAIL.sub(ELLIPSIS, text)
    text = _URL.sub(ELLIPSIS, text)
    return _PHONE_CANDIDATE.sub(
        lambda m: ELLIPSIS if sum(c.isdigit() for c in m.group()) >= 7 else m.group(), text
    )


def _trim(words: list[str], limit: int) -> str:
    if len(words) <= limit:
        return " ".join(words)
    return " ".join(words[:limit]) + ELLIPSIS


def why_now(
    role_title: str,
    days_ago: int,
    evidence_quote: str,
    quote_max_words: int = QUOTE_MAX_WORDS,
    line_max_words: int = LINE_MAX_WORDS,
) -> str:
    title_words = role_title.split()
    unit = "day" if days_ago == 1 else "days"
    fixed = ["posted", str(days_ago), unit, "ago:"]
    # A title so long it leaves no room for one quote word is itself trimmed.
    title_budget = line_max_words - len(fixed) - 1
    title = _trim(title_words, title_budget)
    quote_budget = min(quote_max_words, line_max_words - len(fixed) - min(len(title_words), title_budget))

    quote = _strip_contact_data(evidence_quote).strip().strip("\"'“”‘’").strip()
    quote = _trim(quote.split(), quote_budget)
    return f'{title} posted {days_ago} {unit} ago: "{quote}"'
