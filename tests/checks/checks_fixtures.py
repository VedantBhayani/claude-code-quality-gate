"""Hand-written fixtures for the Part A checkers: one Post, a well-formed run output, and helpers."""
import json
from datetime import date, timedelta
from pathlib import Path

from quality_gate.types import HandLabel, Post, RunRecord

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
INTENT_SIGNALS = PACKAGE_ROOT / "evals" / "skills" / "intent-signals" / "SKILL.md"
MODIFIED_SKILL = PACKAGE_ROOT / "tests" / "fixtures" / "skills" / "modified-intent-signals" / "SKILL.md"
RUNS_DIR = PACKAGE_ROOT / "tests" / "fixtures" / "runs"

COLLECTED = date(2026, 10, 20)
SONNET = "claude-sonnet-5-5"

POST_TEXT = (
    "About us\nWe’re building our first   outbound team — and we need help.\n"
    "You will book meetings for our Account Executives."
)


def make_post(days_ago=3, text=POST_TEXT, post_id="gh-1"):
    return Post(
        post_id=post_id,
        company="Acme",
        domain="acme.com",
        title="Sales Development Representative",
        url="https://boards.greenhouse.io/acme/jobs/1",
        post_date=COLLECTED - timedelta(days=days_ago),
        collection_date=COLLECTED,
        ats="greenhouse",
        text=text,
    )


def output(**overrides):
    """A well-formed, internally consistent intent-signals output (total 40 -> Critical, High recency)."""
    out = {
        "signal": True,
        "signal_type": "sdr_bdr_hiring",
        "evidence": ["We're building our first outbound team"],
        "factors": {"recency": 5, "directness": 4, "frequency": 3, "specificity": 3, "source": 4},
        "total": 40,
        "recency_band": "High",
        "tier": "Critical",
        "action": "Contact within 24 hours",
    }
    out.update(overrides)
    return out


def make_run(structured_output=None, failure_reason=None, model=SONNET, model_usage_keys=None, arm="sonnet-5-5",
             post_id="gh-1", repeat=1, ok=True, answer_models=None):
    if structured_output is None and failure_reason is None and ok:
        structured_output = output()
    return RunRecord(
        post_id=post_id,
        arm=arm,
        model=model,
        repeat=repeat,
        structured_output=structured_output,
        failure_reason=failure_reason,
        model_usage_keys=tuple(model_usage_keys) if model_usage_keys is not None else (model,),
        cli_version="2.5.0",
        skill_hash="abc",
        effort="cli-default",
        answer_models=tuple(answer_models) if answer_models is not None else None,
    )


def load_run(name):
    """A recorded-shape run fixture from tests/fixtures/runs/<name>.json (RunRecord fields)."""
    data = json.loads((RUNS_DIR / f"{name}.json").read_text(encoding="utf-8"))
    data["model_usage_keys"] = tuple(data["model_usage_keys"])
    return RunRecord(**data)


def label(signal=True, signal_type="sdr_bdr_hiring", post_id="gh-1"):
    return HandLabel(post_id=post_id, signal=signal, signal_type=signal_type)
