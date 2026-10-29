"""Part A checkers: pure functions over one run, its post, the rules of that run's own
skill file, and an optional hand label. Each returns a CheckResult with a reason."""
from quality_gate.checks.arm_model import MetricsSplit, check_arm_model, split_for_metrics
from quality_gate.checks.part_a import (
    check_evidence,
    check_label_signal,
    check_label_type,
    check_recency,
    check_run,
    check_score,
    check_structured_output,
    check_tier,
    normalise_for_match,
)

__all__ = [
    "MetricsSplit",
    "check_arm_model",
    "check_evidence",
    "check_label_signal",
    "check_label_type",
    "check_recency",
    "check_run",
    "check_score",
    "check_structured_output",
    "check_tier",
    "normalise_for_match",
    "split_for_metrics",
]
