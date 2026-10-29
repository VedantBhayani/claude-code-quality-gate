"""Collector: Greenhouse, Lever and Ashby adapters behind one interface.

  list_url(board)                       the one documented list endpoint
  parse_board(board, payload, ...)      saved list response -> redacted Posts
  probe(board, fetch)                   200/404 token probe + company-name check
  collect(board, PoliteFetcher(cache_dir))  probe + parse, stamped with the fetch date
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import date
from typing import Any, Callable, Literal

from ..types import Post
from . import ashby, greenhouse, lever
from .base import Board
from .cache import PoliteFetcher
from .redact import redact

ADAPTERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}

# fetch(url) -> (HTTP status, body bytes or None)
Fetch = Callable[[str], "tuple[int | str, bytes | None]"]


class FetchError(RuntimeError):
    """A list call answered with something other than 200 or 404."""


def list_url(board: Board) -> str:
    """The one documented list endpoint for `board`."""
    return ADAPTERS[board.ats].list_url(board)


def parse_board(board: Board, payload, *, collection_date: date) -> list[Post]:
    """Normalise one saved list response for `board` into Posts stamped with collection_date."""
    adapter = ADAPTERS[board.ats]
    posts = (adapter.to_post(job, board, collection_date) for job in adapter.jobs(payload))
    return [replace(p, text=redact(p.text)) for p in posts if p is not None]


@dataclass(frozen=True)
class Probe:
    status: Literal["hit", "miss", "wrong_company"]
    payload: Any = None


_LEGAL_SUFFIXES = {"inc", "llc", "ltd", "corp", "co", "gmbh", "sa", "ag", "bv", "plc", "hq", "limited"}


def _name_tokens(name: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", name.lower())
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return tokens


def _same_company(expected: str, stated: str) -> bool:
    a, b = _name_tokens(expected), _name_tokens(stated)
    short, long_ = sorted((a, b), key=len)
    return bool(short) and long_[: len(short)] == short


def belongs_to(board: Board, payload) -> bool:
    """Does this list response belong to board.company (not a same-slug different company)?

    Uses the company name the response states (Greenhouse `company_name`) when present;
    otherwise requires the company's domain or name as a whole word in the post text.
    """
    adapter = ADAPTERS[board.ats]
    stated = adapter.company_names(payload)
    if stated:
        return any(_same_company(board.company, s) for s in stated)
    posts = parse_board(board, payload, collection_date=date.min)
    blob = " ".join(f"{p.title} {p.text}" for p in posts).lower()  # not URLs: they hold the slug
    if board.domain.lower() in blob:
        return True
    return re.search(r"\b" + re.escape(board.company.lower()) + r"\b", blob) is not None


def probe(board: Board, fetch: Fetch) -> Probe:
    """One list call: 404 = miss, 200 = hit if the board belongs to board.company."""
    status, body = fetch(list_url(board))
    if status == 404:
        return Probe("miss")
    if status != 200 or body is None:
        raise FetchError(f"{list_url(board)} answered {status}")
    payload = json.loads(body)
    return Probe("hit" if belongs_to(board, payload) else "wrong_company", payload)


@dataclass(frozen=True)
class Collection:
    """One board's normalised posts plus the date its list response was fetched."""

    status: Literal["hit", "miss", "wrong_company"]
    posts: list[Post]
    collection_date: date | None


def collect(board: Board, fetcher: PoliteFetcher) -> Collection:
    """Probe the board with one (cached) list call and return its posts if it is the company's."""
    result = probe(board, fetcher)
    if result.status != "hit":
        return Collection(result.status, [], None)
    collected = fetcher.fetched_on(list_url(board))
    return Collection("hit", parse_board(board, result.payload, collection_date=collected), collected)


__all__ = [
    "Board", "Collection", "FetchError", "PoliteFetcher", "Probe",
    "belongs_to", "collect", "list_url", "parse_board", "probe",
]
