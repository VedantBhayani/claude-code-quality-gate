"""Gate thresholds (Resolution 5) and the kappa gate (Resolution 6), on hand-worked numbers."""
import pytest

from quality_gate.config import load_config
from quality_gate.metrics import flip_rate
from quality_gate.thresholds import (
    check_f1_drop,
    check_flip_rate,
    check_kappa,
    f1_drop_threshold,
    flip_rate_threshold,
)


@pytest.fixture
def rules(package_root):
    return load_config(package_root).gate["thresholds"]


def test_f1_drop_threshold_is_twice_the_largest_repeat_noise_when_that_beats_3_points(rules):
    # Largest repeat noise in F1 is Sonnet's 2.5 points -> 2 x 2.5 = 5 points > 3.
    t = f1_drop_threshold({"haiku-5-5": 0.010, "sonnet-5-5": 0.025}, rules)
    assert t.points == pytest.approx(5.0)
    assert "max(2 x 2.5, 3) = 5.0 points" in t.derivation
    assert "sonnet-5-5" in t.derivation


def test_f1_drop_threshold_floors_at_3_points(rules):
    t = f1_drop_threshold({"haiku-5-5": 0.01, "sonnet-5-5": 0.0}, rules)
    assert t.points == pytest.approx(3.0)
    assert "max(2 x 1.0, 3) = 3.0 points" in t.derivation


def test_flip_rate_threshold_is_largest_repeat_noise_plus_5_points(rules):
    t = flip_rate_threshold({"haiku-5-5": 0.06, "sonnet-5-5": 0.04}, rules)
    assert t.points == pytest.approx(11.0)
    assert "6.0 + 5 = 11.0 points" in t.derivation
    assert "drift" not in t.derivation


def test_f1_drop_check_fails_only_when_the_drop_exceeds_the_threshold(rules):
    t = f1_drop_threshold({"haiku-5-5": 0.025}, rules)  # 5 points
    exact = check_f1_drop(baseline_f1=0.80, candidate_f1=0.75, threshold=t)
    over = check_f1_drop(baseline_f1=0.80, candidate_f1=0.749, threshold=t)
    assert exact.passed is True
    assert over.passed is False
    assert "5.1 points" in over.reason and t.derivation in over.reason


def test_flip_rate_check_reads_the_measured_flip_rate(rules):
    t = flip_rate_threshold({"haiku-5-5": 0.05}, rules)  # 10 points
    pass_rate = flip_rate("claude-haiku-5-5", {f"p{i}": True for i in range(10)},
                          "claude-sonnet-5-5", {f"p{i}": i != 0 for i in range(10)})  # 1/10 = 10%
    fail_rate = flip_rate("claude-haiku-5-5", {f"p{i}": True for i in range(10)},
                          "claude-sonnet-5-5", {f"p{i}": i > 1 for i in range(10)})  # 2/10 = 20%
    assert check_flip_rate(pass_rate, t).passed is True
    result = check_flip_rate(fail_rate, t)
    assert result.passed is False
    assert "model switch" in result.reason and "20.0%" in result.reason


def test_kappa_gate_on_yes_no_at_0_80(package_root):
    agreement = load_config(package_root).gate["agreement"]
    assert check_kappa(0.80, agreement).passed is True
    low = check_kappa(0.79, agreement)
    assert low.passed is False
    assert "0.79" in low.reason and "0.80" in low.reason
