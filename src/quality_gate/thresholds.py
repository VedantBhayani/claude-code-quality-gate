"""Gate thresholds derived from measured repeat noise (spec Resolution 5).

Thresholds are never picked in advance: each is computed from the repeat noise
measured in the pilot and repeat runs, using the multiples and margins in the
[thresholds] section of config/gate.toml, and carries its derivation as text so
the report and the config can show how the number was reached.

Inputs are fractions (0.025 = 2.5 points); thresholds are in points.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from quality_gate.metrics import Rate
from quality_gate.types import CheckResult


@dataclass(frozen=True)
class Threshold:
    name: str
    points: float
    derivation: str


def _pts(fraction: float) -> float:
    return round(fraction * 100, 6)


def _largest(noise_by_arm: Mapping[str, float]) -> tuple[str, float]:
    if not noise_by_arm:
        raise ValueError("a threshold needs the measured repeat noise of at least one arm")
    arm = max(noise_by_arm, key=lambda a: noise_by_arm[a])
    return arm, _pts(noise_by_arm[arm])


def f1_drop_threshold(repeat_noise_f1_by_arm: Mapping[str, float], rules: Mapping[str, Any]) -> Threshold:
    """Fail if macro-F1 drops by more than max(multiple x repeat noise in F1, floor).

    Repeat noise in F1 is |F1(run 1) - F1(run 2)| for one arm; the largest arm's
    value is used so the threshold is not tighter than any arm's own noise.
    """
    multiple = rules["macro_f1_noise_multiple"]
    floor = rules["macro_f1_min_margin_points"]
    arm, noise = _largest(repeat_noise_f1_by_arm)
    points = round(max(multiple * noise, floor), 6)
    measured = ", ".join(f"{a} {_pts(v):.1f}" for a, v in repeat_noise_f1_by_arm.items())
    derivation = (
        f"{rules['macro_f1_drop']} Measured repeat noise in F1 (points): {measured}; "
        f"largest is {arm}. Threshold = max({multiple} x {noise:.1f}, {floor}) = {points:.1f} points."
    )
    return Threshold(name="macro-F1 drop", points=points, derivation=derivation)


def flip_rate_threshold(repeat_noise_by_arm: Mapping[str, float], rules: Mapping[str, Any]) -> Threshold:
    """Fail if the flip rate between arms exceeds repeat noise + margin.

    Pass the repeat noise of the arms being compared; the largest is used.
    """
    margin = rules["flip_rate_margin_points"]
    arm, noise = _largest(repeat_noise_by_arm)
    points = round(noise + margin, 6)
    measured = ", ".join(f"{a} {_pts(v):.1f}" for a, v in repeat_noise_by_arm.items())
    derivation = (
        f"{rules['flip_rate']} Measured repeat noise (points): {measured}; "
        f"largest is {arm}. Threshold = {noise:.1f} + {margin} = {points:.1f} points."
    )
    return Threshold(name="flip rate", points=points, derivation=derivation)


def check_f1_drop(baseline_f1: float, candidate_f1: float, threshold: Threshold) -> CheckResult:
    drop = round((baseline_f1 - candidate_f1) * 100, 6)
    passed = drop <= threshold.points
    reason = (
        f"macro-F1 {baseline_f1:.3f} -> {candidate_f1:.3f}: drop of {drop:.1f} points "
        f"{'within' if passed else 'exceeds'} the {threshold.points:.1f}-point threshold. {threshold.derivation}"
    )
    return CheckResult(name="macro_f1_drop", passed=passed, reason=reason)


def check_flip_rate(rate: Rate, threshold: Threshold) -> CheckResult:
    points = _pts(rate.rate)
    passed = points <= threshold.points
    reason = (
        f"{rate.describe()}; {'within' if passed else 'exceeds'} the "
        f"{threshold.points:.1f}-point threshold. {threshold.derivation}"
    )
    return CheckResult(name="flip_rate", passed=passed, reason=reason)


def check_kappa(kappa: float, agreement: Mapping[str, Any]) -> CheckResult:
    """Resolution 6: gate on Cohen's kappa for the yes/no label (>= min_kappa)."""
    bar = agreement["min_kappa"]
    passed = kappa >= bar
    reason = (
        f"Cohen's kappa on {agreement['gate_on']} = {kappa:.2f}, "
        f"{'meets' if passed else 'below'} the {bar:.2f} bar."
    )
    return CheckResult(name="label_agreement_kappa", passed=passed, reason=reason)
