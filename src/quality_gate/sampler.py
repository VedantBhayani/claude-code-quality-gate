"""Sampler: the sales-ish title filter and the seeded samples drawn from collected Posts.

The title rules live in config/title_filter.toml (spec Resolution 17); the order in
which they apply is documented there. Sample sizes are parameters (FACTs from the
pilot, Resolution 4); seeds come from gate.toml [seeds].
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Any

from .config import Config
from .types import Post


def _search(patterns: list[str], title: str) -> bool:
    return any(re.search(p, title, re.IGNORECASE) for p in patterns)


def classify_title(title: str, rules: dict[str, Any]) -> tuple[bool, str | None]:
    """Return (is_sales_ish, ambiguous_family_or_None) for one job title."""
    t = title or ""
    if _search(rules["hard_exclude"]["patterns"], t):
        return False, None
    for fam in rules.get("ambiguous", []):
        if _search(fam["patterns"], t):
            return True, fam["family"]
    if _search(rules["exclude"]["patterns"], t):
        return False, None
    if _search(rules["include"]["patterns"], t):
        return True, None
    return False, None


def fresh_per_company(
    posts: list[Post], rules: dict[str, Any], *, window_days: int
) -> tuple[list[Post], list[Post]]:
    """One post per company: its freshest sales-ish post aged 0..window_days
    (collection_date - post_date). A core sales role beats an ambiguous one at any age.
    Returns (natural, ambiguous): a company whose only fresh posts are ambiguous roles
    goes to the second list. Companies are keyed by domain (company name if empty);
    ties break on post_id; both lists are sorted by post_id."""
    best: dict[str, tuple[tuple[int, int, str], Post, bool]] = {}
    for p in posts:
        age = (p.collection_date - p.post_date).days
        if not 0 <= age <= window_days:
            continue
        sales_ish, family = classify_title(p.title, rules)
        if not sales_ish:
            continue
        key = (p.domain or p.company).lower()
        rank = (1 if family else 0, age, p.post_id)
        if key not in best or rank < best[key][0]:
            best[key] = (rank, p, family is not None)
    natural = sorted((p for _, p, amb in best.values() if not amb), key=lambda p: p.post_id)
    ambiguous = sorted((p for _, p, amb in best.values() if amb), key=lambda p: p.post_id)
    return natural, ambiguous


class SampleSizeError(ValueError):
    """A requested sample is larger than the pool it is drawn from."""


@dataclass(frozen=True)
class Samples:
    natural: list[Post]    # headline numbers; non-ambiguous sales-ish posts only
    ambiguous: list[Post]  # reported separately; ambiguous-role posts only
    opus: list[Post]       # uniform random subset of `natural` (Resolution 8)


def _draw(pool: list[Post], size: int, seed: int, name: str) -> list[Post]:
    if size > len(pool):
        raise SampleSizeError(f"{name} sample: asked for {size} posts but the pool has only {len(pool)}")
    ordered = sorted(pool, key=lambda p: p.post_id)  # input order must not change the draw
    return random.Random(seed).sample(ordered, size)


def draw_samples(
    posts: list[Post],
    cfg: Config,
    *,
    natural_size: int,
    ambiguous_size: int,
    opus_size: int | None = None,
    seeds: dict[str, int] | None = None,
) -> Samples:
    """Draw the natural sample, the ambiguous subset and the Opus subset.

    Sizes are FACTs from the pilot; opus_size defaults to gate.toml samples.opus_subset_size.
    Seeds default to gate.toml [seeds]; `seeds` overrides individual entries.
    """
    rules = cfg.title_filter()
    s = {**cfg.gate["seeds"], **(seeds or {})}
    if opus_size is None:
        opus_size = cfg.gate["samples"]["opus_subset_size"]
    natural_pool: list[Post] = []
    ambiguous_pool: list[Post] = []
    for p in posts:
        sales_ish, family = classify_title(p.title, rules)
        if sales_ish:
            (ambiguous_pool if family else natural_pool).append(p)
    natural = _draw(natural_pool, natural_size, s["natural_sample"], "natural")
    ambiguous = _draw(ambiguous_pool, ambiguous_size, s["ambiguous_subset"], "ambiguous")
    opus = _draw(natural, opus_size, s["opus_subset"], "opus")
    return Samples(natural=natural, ambiguous=ambiguous, opus=opus)
