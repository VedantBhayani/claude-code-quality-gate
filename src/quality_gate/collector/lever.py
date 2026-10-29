"""Lever Postings API adapter (global and EU hosts). The list response is a bare JSON
array; post date is `createdAt` (ms epoch). Text = description + lists + additional."""
from __future__ import annotations

from datetime import date

from ..types import Post
from .base import Board, epoch_ms_date, html_to_text

ATS = "lever"


def list_url(board: Board) -> str:
    host = "api.eu.lever.co" if board.eu else "api.lever.co"
    return f"https://{host}/v0/postings/{board.token}?mode=json"


def jobs(payload) -> list[dict]:
    return payload if isinstance(payload, list) else []


def company_names(payload) -> set[str]:
    return set()  # Lever postings carry no company name field


def _text(job: dict) -> str:
    parts = [job.get("descriptionPlain") or html_to_text(job.get("description", ""))]
    for section in job.get("lists") or []:
        parts.append(section.get("text", ""))
        parts.append(html_to_text(section.get("content", "")))
    parts.append(job.get("additionalPlain") or html_to_text(job.get("additional", "")))
    return "\n".join(p.strip() for p in parts if p and p.strip())


def to_post(job: dict, board: Board, collection_date: date) -> Post | None:
    if job.get("createdAt") is None:
        return None
    return Post(
        post_id=f"{ATS}:{board.token}:{job['id']}",
        company=board.company,
        domain=board.domain,
        title=job.get("text", "").strip(),
        url=job.get("hostedUrl", ""),
        post_date=epoch_ms_date(job["createdAt"]),
        collection_date=collection_date,
        ats=ATS,
        text=_text(job),
    )
