"""Greenhouse Job Board API adapter. Post date is `first_published`, never `updated_at`;
`content` arrives HTML-entity-escaped and is unescaped before tags are stripped."""
from __future__ import annotations

from datetime import date

from ..types import Post
from .base import Board, iso_date, unescape_then_text

ATS = "greenhouse"


def list_url(board: Board) -> str:
    return f"https://boards-api.greenhouse.io/v1/boards/{board.token}/jobs?content=true"


def jobs(payload) -> list[dict]:
    return payload.get("jobs", []) if isinstance(payload, dict) else []


def company_names(payload) -> set[str]:
    return {j["company_name"] for j in jobs(payload) if j.get("company_name")}


def to_post(job: dict, board: Board, collection_date: date) -> Post | None:
    if not job.get("first_published"):
        return None
    return Post(
        post_id=f"{ATS}:{board.token}:{job['id']}",
        company=board.company,
        domain=board.domain,
        title=job.get("title", "").strip(),
        url=job.get("absolute_url", ""),
        post_date=iso_date(job["first_published"]),
        collection_date=collection_date,
        ats=ATS,
        text=unescape_then_text(job.get("content", "")),
    )
