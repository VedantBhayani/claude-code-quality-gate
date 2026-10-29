"""Part A checks on one intent-signals run.

Every check is judged against the rules read from the run's own SKILL.md (read_rules), never
a shared copy. A failed run (CLI failure such as error_max_structured_output_retries, missing
structured_output, or output that breaks the schema) makes every check an explicit failure
whose reason starts "run failed:", never a skip.
"""
from __future__ import annotations

import functools
import json
import re
import unicodedata
from pathlib import Path

from jsonschema import Draft7Validator

from quality_gate.skill_rules import FACTORS, SkillRules
from quality_gate.types import CheckResult, HandLabel, Post, RunRecord

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "signal_output.schema.json"
_VALIDATOR = Draft7Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))

# Typographic variants a model may "straighten" when quoting: unify before matching.
_TYPOGRAPHY = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    "…": "...",
})
_WHITESPACE = re.compile(r"\s+")


def normalise_for_match(text: str) -> str:
    """NFKC, typographic quotes/dashes/ellipsis unified, whitespace runs collapsed, ends trimmed.
    Applied identically to the post text and to each quote; case is kept (quotes are verbatim)."""
    text = unicodedata.normalize("NFKC", text).translate(_TYPOGRAPHY)
    return _WHITESPACE.sub(" ", text).strip()


def _output_error(run: RunRecord) -> str | None:
    """Why this run has no usable structured_output, or None if it has one."""
    if run.failure_reason:
        return run.failure_reason
    out = run.structured_output
    if out is None:
        return "no structured_output"
    errors = sorted(_VALIDATOR.iter_errors(out), key=lambda e: list(e.path))
    if errors:
        e = errors[0]
        where = "/".join(str(p) for p in e.path) or "output"
        return f"structured_output breaks the schema at {where}: {e.message}"
    if (not out["signal"]) != (out["signal_type"] == "not_signal"):
        return f"structured_output has signal {out['signal']} with signal type {out['signal_type']}"
    return None


def _needs_output(name: str):
    def wrap(check):
        @functools.wraps(check)
        def guarded(run: RunRecord, *args, **kwargs) -> CheckResult:
            error = _output_error(run)
            if error:
                return CheckResult(name, False, f"run failed: {error}")
            return check(run, *args, **kwargs)
        return guarded
    return wrap


def check_structured_output(run: RunRecord) -> CheckResult:
    error = _output_error(run)
    if error:
        return CheckResult("structured_output", False, f"run failed: {error}")
    return CheckResult("structured_output", True, "structured_output present and valid against the schema")


@_needs_output("evidence")
def check_evidence(run: RunRecord, post: Post) -> CheckResult:
    """Every quote must appear in the post text after normalise_for_match on both sides."""
    out = run.structured_output
    if out["signal"] and not out["evidence"]:
        return CheckResult("evidence", False, "signal is yes but no evidence quote was given")
    haystack = normalise_for_match(post.text)
    missing = [q for q in out["evidence"] if not normalise_for_match(q) or normalise_for_match(q) not in haystack]
    if missing:
        return CheckResult("evidence", False, f"{len(missing)} quote(s) not in the post text: {missing!r}")
    return CheckResult("evidence", True, f"all {len(out['evidence'])} quote(s) found in the post text")


@_needs_output("score")
def check_score(run: RunRecord, rules: SkillRules) -> CheckResult:
    """total must equal the run's own factor ratings weighted by its own file's formula."""
    out = run.structured_output
    factors = out["factors"]
    expected = sum(rules.weights[f] * factors[f] for f in FACTORS)
    working = " + ".join(f"{f} {factors[f]}x{rules.weights[f]}" for f in FACTORS)
    if out["total"] != expected:
        return CheckResult("score", False, f"total {out['total']} but {working} = {expected}")
    return CheckResult("score", True, f"total {expected} = {working}")


@_needs_output("recency")
def check_recency(run: RunRecord, post: Post, rules: SkillRules) -> CheckResult:
    """recency_band must be the band of the run's own file for the post's age at collection."""
    band = run.structured_output["recency_band"]
    age = (post.collection_date - post.post_date).days
    if age < 0:
        return CheckResult("recency", False, f"post date {post.post_date} is after the collection date {post.collection_date}")
    expected = rules.recency_rating_for(age) or "None"
    if band != expected:
        return CheckResult("recency", False, f"recency band {band} but the post is {age} days old at collection: {expected}")
    return CheckResult("recency", True, f"post is {age} days old at collection: {expected}")


@_needs_output("tier")
def check_tier(run: RunRecord, rules: SkillRules) -> CheckResult:
    """tier must be the tier the run's own file gives for the run's own total."""
    out = run.structured_output
    expected = rules.tier_for(out["total"])
    if out["tier"] != expected:
        return CheckResult("tier", False, f"tier {out['tier']} but total {out['total']} is {expected}")
    return CheckResult("tier", True, f"total {out['total']} is {expected}")


def _yes_no(flag: bool) -> str:
    return "yes" if flag else "no"


@_needs_output("label_signal")
def check_label_signal(run: RunRecord, label: HandLabel) -> CheckResult:
    got, want = run.structured_output["signal"], label.signal
    return CheckResult("label_signal", got == want, f"run says signal {_yes_no(got)}, hand label says {_yes_no(want)}")


@_needs_output("label_type")
def check_label_type(run: RunRecord, label: HandLabel) -> CheckResult:
    got, want = run.structured_output["signal_type"], label.signal_type
    return CheckResult("label_type", got == want, f"run says {got}, hand label says {want}")


def check_run(run: RunRecord, post: Post, rules: SkillRules, label: HandLabel | None = None) -> list[CheckResult]:
    """All Part A checks for one run, in a fixed order. rules must be read_rules() of the file
    this run was given. Label checks are included only when a hand label exists. The arm model
    match is separate (split_for_metrics), since it needs the arms' pinned IDs."""
    results = [
        check_structured_output(run),
        check_evidence(run, post),
        check_score(run, rules),
        check_recency(run, post, rules),
        check_tier(run, rules),
    ]
    if label is not None:
        results += [check_label_signal(run, label), check_label_type(run, label)]
    return results
