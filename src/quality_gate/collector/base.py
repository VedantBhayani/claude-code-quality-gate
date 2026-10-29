"""The one Collector interface: a Board in, normalised Posts plus the collection date out.

Each ATS adapter module exposes:
  list_url(board) -> str              the one documented list endpoint
  jobs(payload) -> list[dict]         the job records in a saved list response
  to_post(job, board, collection_date) -> Post | None   (None = drop, e.g. Ashby isListed=false)
  company_names(payload) -> set[str]  company names the response itself states (may be empty)
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html.parser import HTMLParser

from ..types import Ats


@dataclass(frozen=True)
class Board:
    """One company's public job board on one ATS. eu=True selects Lever's EU host."""

    ats: Ats
    token: str
    company: str
    domain: str
    eu: bool = False


_BLOCK_TAGS = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(markup: str) -> str:
    """Strip tags from HTML, decode entities, and collapse whitespace into tidy lines."""
    parser = _TextExtractor()
    parser.feed(markup or "")
    parser.close()
    lines = (re.sub(r"[ \t ]+", " ", line).strip() for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line)


def unescape_then_text(escaped_markup: str) -> str:
    """For entity-escaped HTML (Greenhouse `content`): unescape once, then strip tags."""
    return html_to_text(html.unescape(escaped_markup or ""))


def iso_date(value: str) -> date:
    """Calendar date of an ISO-8601 timestamp, in the timestamp's own offset."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def epoch_ms_date(value: int | float) -> date:
    """UTC calendar date of a millisecond Unix timestamp (Lever `createdAt`)."""
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date()
