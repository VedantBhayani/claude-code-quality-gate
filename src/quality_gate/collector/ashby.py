"""Ashby public job posting API adapter. Post date is `publishedAt`; jobs with
`isListed=false` are direct-link only and are dropped."""
from __future__ import annotations

from datetime import date

from ..types import Post
from .base import Board, html_to_text, iso_date

ATS = "ashby"


def list_url(board: Board) -> str:
    return f"https://api.ashbyhq.com/posting-api/job-board/{board.token}?includeCompensation=true"


def jobs(payload) -> list[dict]:
    return payload.get("jobs", []) if isinstance(payload, dict) else []


def company_names(payload) -> set[str]:
    return set()  # the job-board response carries no organisation name


def to_post(job: dict, board: Board, collection_date: date) -> Post | None:
    if job.get("isListed") is False or not job.get("publishedAt"):
        return None
    text = job.get("descriptionPlain") or html_to_text(job.get("descriptionHtml", ""))
    return Post(
        post_id=f"{ATS}:{board.token}:{job['id']}",
        company=board.company,
        domain=board.domain,
        title=job.get("title", "").strip(),
        url=job.get("jobUrl", ""),
        post_date=iso_date(job["publishedAt"]),
        collection_date=collection_date,
        ats=ATS,
        text=text.strip(),
    )
