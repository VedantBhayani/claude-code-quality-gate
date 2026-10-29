"""Shapes shared across the gate's seam. Vocabulary follows GLOSSARY.md."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

Ats = Literal["greenhouse", "lever", "ashby"]
SignalType = Literal["sdr_bdr_hiring", "ae_hiring", "sales_leadership", "revops_gtm_eng", "not_signal"]
SIGNAL_TYPES: tuple[str, ...] = ("sdr_bdr_hiring", "ae_hiring", "sales_leadership", "revops_gtm_eng", "not_signal")


@dataclass(frozen=True)
class Post:
    """One collected job post. A signal's age is measured from collection_date."""

    post_id: str
    company: str
    domain: str
    title: str
    url: str
    post_date: date
    collection_date: date
    ats: Ats
    text: str  # plain text, HTML already stripped


@dataclass(frozen=True)
class HandLabel:
    """A human label for one post: signal yes/no plus its signal type."""

    post_id: str
    signal: bool
    signal_type: SignalType

    def __post_init__(self) -> None:
        if self.signal_type not in SIGNAL_TYPES:
            raise ValueError(f"unknown signal type {self.signal_type!r}; expected one of {SIGNAL_TYPES}")
        if (not self.signal) != (self.signal_type == "not_signal"):
            raise ValueError("signal=False must go with signal type 'not_signal', and only then")


@dataclass(frozen=True)
class RunRecord:
    """One headless skill run on one post. Exactly one of structured_output / failure_reason is set."""

    post_id: str
    arm: str
    model: str  # pinned model ID passed to --model
    repeat: int
    structured_output: dict[str, Any] | None
    failure_reason: str | None
    model_usage_keys: tuple[str, ...]  # every key of modelUsage, incl. Claude Code's background helper calls
    cli_version: str
    skill_hash: str
    effort: str
    usage: dict[str, Any] = field(default_factory=dict)
    cost_usd: float | None = None  # client-side estimate at list price; a proxy only (02a section 4)
    # Model(s) that wrote the answer: the modelUsage entries whose tokens match the main turn
    # (runner.output.answering_models). None = not recorded (older logs; falls back to the keys).
    answer_models: tuple[str, ...] | None = None
    model_usage: dict[str, Any] = field(default_factory=dict)  # the full modelUsage, for audit


def answering_models_of(run: RunRecord) -> tuple[str, ...]:
    """The model(s) that wrote this run's answer; older records fall back to every modelUsage key."""
    return run.answer_models if run.answer_models is not None else run.model_usage_keys


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one check. heuristic=True marks checks reported as heuristics (Resolution 14)."""

    name: str
    passed: bool
    reason: str
    heuristic: bool = False
