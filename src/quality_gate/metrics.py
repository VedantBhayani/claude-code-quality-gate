"""Comparison metrics for the gate. Vocabulary follows GLOSSARY.md.

Every metric takes label maps: {post_id: label}. A label of None means the run
failed for that post (no structured output). Pairwise metrics compare only the
posts both sides labelled, and count each side's failures separately so they
stay visible per model instead of silently shrinking the denominator.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Hashable, Iterable, Mapping, TypeVar

Labels = Mapping[str, Hashable | None]
T = TypeVar("T")


@dataclass(frozen=True)
class Kappa:
    """Cohen's kappa between two raters over the n posts both labelled."""

    kappa: float
    observed_agreement: float
    expected_agreement: float
    n: int


def _paired(a: Labels, b: Labels) -> list[tuple[Hashable, Hashable]]:
    return [(a[k], b[k]) for k in sorted(a.keys() & b.keys()) if a[k] is not None and b[k] is not None]


def cohens_kappa(a: Labels, b: Labels) -> Kappa:
    pairs = _paired(a, b)
    n = len(pairs)
    if n == 0:
        raise ValueError("cohens_kappa needs at least one post labelled by both raters")
    p_o = sum(x == y for x, y in pairs) / n
    count_a = Counter(x for x, _ in pairs)
    count_b = Counter(y for _, y in pairs)
    p_e = sum(count_a[c] * count_b[c] for c in count_a.keys() | count_b.keys()) / (n * n)
    # Both raters used one and the same category for every post: p_e = 1 and the
    # formula is 0/0. They agree perfectly, so report 1.0.
    kappa = 1.0 if p_e == 1 else (p_o - p_e) / (1 - p_e)
    return Kappa(kappa=kappa, observed_agreement=p_o, expected_agreement=p_e, n=n)


@dataclass(frozen=True)
class F1:
    """Macro-F1 of one run against hand labels.

    Only hand-labelled posts count. A hand-labelled post whose run failed is a
    failure, excluded from n. Classes are every label seen in the gold or the
    predictions; a class with no true positives scores 0.
    """

    macro_f1: float
    per_class: dict[Hashable, float]
    n: int
    failures: int


def macro_f1(predicted: Labels, gold: Labels) -> F1:
    labelled = [k for k in sorted(gold) if gold[k] is not None]
    pairs = [(predicted[k], gold[k]) for k in labelled if predicted.get(k) is not None]
    failures = len(labelled) - len(pairs)
    if not pairs:
        raise ValueError("macro_f1 needs at least one hand-labelled post with a successful run")
    classes = {p for p, _ in pairs} | {g for _, g in pairs}
    per_class: dict[Hashable, float] = {}
    for c in classes:
        tp = sum(p == c and g == c for p, g in pairs)
        fp = sum(p == c and g != c for p, g in pairs)
        fn = sum(p != c and g == c for p, g in pairs)
        per_class[c] = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
    return F1(macro_f1=sum(per_class.values()) / len(per_class), per_class=per_class, n=len(pairs), failures=failures)


@dataclass(frozen=True)
class Rate:
    """Share of posts whose label changed between two sides.

    kind is "model switch" (different models), "model upgrade" (two versions of
    one model) or "repeat noise" (two runs of the same model on the same input).
    failures maps each side to its failed or missing runs, which are excluded
    from n.
    """

    kind: str
    sides: tuple[str, str]
    changed: int
    n: int
    rate: float
    failures: dict[str, int]

    def describe(self) -> str:
        a, b = self.sides
        fails = ", ".join(f"{side} {count}" for side, count in self.failures.items())
        return (
            f"{self.kind} ({a} vs {b}): {self.changed}/{self.n} labels changed "
            f"= {self.rate * 100:.1f}%; failures excluded: {fails}"
        )


def _model_family(model: str) -> str:
    # Pinned IDs look like claude-<family>-<version...>, e.g. claude-haiku-4-5-20251001.
    parts = model.split("-")
    return parts[1] if len(parts) > 1 and parts[0] == "claude" else model


def _rate(kind: str, sides: tuple[str, str], keys: tuple[str, str], a: Labels, b: Labels) -> Rate:
    universe = a.keys() | b.keys()
    pairs = _paired(a, b)
    changed = sum(x != y for x, y in pairs)
    n = len(pairs)
    failures = {
        keys[0]: sum(a.get(k) is None for k in universe),
        keys[1]: sum(b.get(k) is None for k in universe),
    }
    return Rate(kind=kind, sides=sides, changed=changed, n=n, rate=changed / n if n else 0.0, failures=failures)


def flip_rate(model_a: str, a: Labels, model_b: str, b: Labels) -> Rate:
    """Flip rate between two arms: a model switch, or a model upgrade when both
    are versions of the same model family."""
    if model_a == model_b:
        raise ValueError("same model on both sides: use repeat_noise for two runs of one model")
    kind = "model upgrade" if _model_family(model_a) == _model_family(model_b) else "model switch"
    return _rate(kind, (model_a, model_b), (model_a, model_b), a, b)


def repeat_noise(model: str, run1: Labels, run2: Labels) -> Rate:
    """Repeat noise: share of posts whose label changed between two runs of one model."""
    return _rate("repeat noise", (f"{model} run 1", f"{model} run 2"), ("run 1", "run 2"), run1, run2)


def per_population(
    populations: Mapping[str, Iterable[str]], metric: Callable[..., T], *args: Any
) -> dict[str, T]:
    """Run metric once per population (e.g. natural sample, ambiguous subset).

    args are passed through to metric, with every label map restricted to the
    population's post ids. A post in the population with no entry in a label
    map is treated as None (a failed or missing run, or no hand label).
    """
    results: dict[str, T] = {}
    for name, post_ids in populations.items():
        ids = list(post_ids)
        restricted = [{k: arg.get(k) for k in ids} if isinstance(arg, Mapping) else arg for arg in args]
        results[name] = metric(*restricted)
    return results
