"""Gift selection (Resolution 10): the 50 accounts Frontal should email this week.

A post qualifies when its hand label says signal, it was posted 0..window_days
days before its collection date, and it has a usable Sonnet 5.5 run-1 record
(structured output present, modelUsage exactly the pinned model). Each company
keeps its freshest qualifying post. Rows are ranked by the Sonnet run-1 score,
ties broken by recency, and the top N are kept. The score and tier shown come
from that same run. Fewer qualifiers than N simply yields fewer rows.

Rows carry no person names or contact data and never the post text: only the
locked fields below, with the evidence reduced to the "why now" line.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from quality_gate.gift.why_now import why_now
from quality_gate.types import CheckResult, HandLabel, Post, RunRecord, answering_models_of

GIFT_FIELDS: tuple[str, ...] = (
    "company",
    "domain",
    "role_title",
    "post_url",
    "posted_date",
    "collection_date",
    "signal_type",
    "why_now",
    "score",
    "tier",
    "check_results",
)


@dataclass(frozen=True)
class GiftRow:
    company: str
    domain: str
    role_title: str
    post_url: str
    posted_date: str
    collection_date: str
    signal_type: str
    why_now: str
    score: int
    tier: str
    check_results: str
    post_id: str  # internal join key; not one of the published fields

    def as_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in GIFT_FIELDS}


def _score(output: Mapping[str, Any]) -> int:
    return int(output["total"] if "total" in output else output["score"])


def _first_quote(output: Mapping[str, Any]) -> str:
    evidence = output.get("evidence", "")
    if isinstance(evidence, str):
        return evidence
    return next((q for q in evidence if isinstance(q, str) and q.strip()), "")


def _summarise_checks(checks: Iterable[CheckResult]) -> str:
    # Names and pass/fail only: reasons can quote post text.
    return "; ".join(
        f"{c.name}: {'pass' if c.passed else 'fail'}{' (heuristic)' if c.heuristic else ''}" for c in checks
    )


def _usable(run: RunRecord) -> bool:
    return run.structured_output is not None and answering_models_of(run) == (run.model,)


def select_gift(
    posts: Sequence[Post],
    labels: Sequence[HandLabel],
    runs: Sequence[RunRecord],
    checks: Mapping[str, Sequence[CheckResult]],
    rules: Mapping[str, Any],
) -> list[GiftRow]:
    """rules is the [gift] table of config/gate.toml; checks maps post_id to the
    CheckResults of that post's Sonnet run-1 record."""
    window = int(rules["window_days"])
    signal_ids = {lbl.post_id: lbl for lbl in labels if lbl.signal}
    ranking_runs = {
        r.post_id: r
        for r in runs
        if r.arm == rules["rank_by_arm"] and r.repeat == int(rules["rank_by_repeat"]) and _usable(r)
    }

    freshest: dict[str, tuple[int, Post]] = {}
    for post in posts:
        age = (post.collection_date - post.post_date).days
        if post.post_id not in signal_ids or post.post_id not in ranking_runs or not 0 <= age <= window:
            continue
        key = (post.domain or post.company).strip().casefold()
        if key not in freshest or (age, post.post_id) < (freshest[key][0], freshest[key][1].post_id):
            freshest[key] = (age, post)

    rows = []
    for age, post in freshest.values():
        output = ranking_runs[post.post_id].structured_output
        assert output is not None
        rows.append(
            (
                age,
                GiftRow(
                    company=post.company,
                    domain=post.domain,
                    role_title=post.title,
                    post_url=post.url,
                    posted_date=post.post_date.isoformat(),
                    collection_date=post.collection_date.isoformat(),
                    signal_type=signal_ids[post.post_id].signal_type,
                    why_now=why_now(
                        post.title,
                        age,
                        _first_quote(output),
                        quote_max_words=int(rules.get("why_now_quote_max_words", 12)),
                        line_max_words=int(rules.get("why_now_max_words", 20)),
                    ),
                    score=_score(output),
                    tier=str(output.get("tier", "")),
                    check_results=_summarise_checks(checks.get(post.post_id, ())),
                    post_id=post.post_id,
                ),
            )
        )
    rows.sort(key=lambda pair: (-pair[1].score, pair[0], pair[1].company.casefold(), pair[1].post_id))
    return [row for _, row in rows[: int(rules["top_n"])]]
