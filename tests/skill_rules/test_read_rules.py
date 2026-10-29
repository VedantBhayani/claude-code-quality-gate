"""read_rules: the rules a run is judged by, read from that run's own SKILL.md."""
from pathlib import Path

import pytest

from quality_gate.skill_rules import SkillRulesError, read_freshness_windows, read_rules

ROOT = Path(__file__).resolve().parents[2]
INTENT_SIGNALS = ROOT / "evals" / "skills" / "intent-signals" / "SKILL.md"
TRIGGER_MAPPING = ROOT / "evals" / "skills" / "trigger-mapping" / "SKILL.md"
MODIFIED = ROOT / "tests" / "fixtures" / "skills" / "modified-intent-signals" / "SKILL.md"
NO_RULES = ROOT / "tests" / "fixtures" / "skills" / "with-model-frontmatter" / "SKILL.md"


# --- intent-signals equals the spec -------------------------------------------------

def test_factor_weights_are_3_3_2_1_1():
    assert read_rules(INTENT_SIGNALS).weights == {
        "recency": 3, "directness": 3, "frequency": 2, "specificity": 1, "source": 1,
    }


def test_tier_cutoffs_are_40_30_20_10_then_noise():
    tiers = read_rules(INTENT_SIGNALS).tiers
    assert [(t.name, t.min_score) for t in tiers] == [
        ("Critical", 40), ("High", 30), ("Medium", 20), ("Low", 10), ("Noise", 0),
    ]
    assert tiers[0].action == "Contact within 24 hours"


def test_recency_bands_are_7_30_90_days():
    bands = read_rules(INTENT_SIGNALS).recency_bands
    assert [(b.rating, b.max_days) for b in bands] == [("High", 7), ("Medium", 30), ("Low", 90)]


def test_freshness_window_is_two_weeks():
    windows = read_rules(INTENT_SIGNALS).freshness_windows
    assert [w.days for w in windows] == [14]
    assert "After 2 weeks, the signal is stale" in windows[0].quote
    assert windows[0].line == next(
        i for i, ln in enumerate(INTENT_SIGNALS.read_text(encoding="utf-8").splitlines(), 1)
        if "After 2 weeks" in ln
    )


@pytest.mark.parametrize("score,tier", [
    (50, "Critical"), (40, "Critical"), (39, "High"), (30, "High"), (29, "Medium"),
    (20, "Medium"), (19, "Low"), (10, "Low"), (9, "Noise"), (0, "Noise"),
])
def test_tier_for_score(score, tier):
    assert read_rules(INTENT_SIGNALS).tier_for(score) == tier


@pytest.mark.parametrize("age,rating", [
    (0, "High"), (7, "High"), (8, "Medium"), (30, "Medium"), (31, "Low"), (90, "Low"), (91, None),
])
def test_recency_rating_for_age(age, rating):
    assert read_rules(INTENT_SIGNALS).recency_rating_for(age) == rating


def test_rules_carry_the_hash_of_the_injected_text():
    from quality_gate.skill_rules import prepare_skill
    assert read_rules(INTENT_SIGNALS).skill_sha256 == prepare_skill(INTENT_SIGNALS).sha256


# --- a modified file yields modified rules ------------------------------------------

def test_modified_file_yields_modified_rules():
    rules = read_rules(MODIFIED)
    assert rules.weights == {"recency": 4, "directness": 2, "frequency": 2, "specificity": 1, "source": 1}
    assert [(t.name, t.min_score) for t in rules.tiers] == [
        ("Critical", 45), ("High", 35), ("Medium", 25), ("Low", 15), ("Noise", 0),
    ]
    assert [(b.rating, b.max_days) for b in rules.recency_bands] == [("High", 14), ("Medium", 45), ("Low", 120)]
    assert [w.days for w in rules.freshness_windows] == [21]
    assert rules.tier_for(44) == "High"
    assert rules.recency_rating_for(14) == "High"
    assert rules.skill_sha256 != read_rules(INTENT_SIGNALS).skill_sha256


def test_file_without_scoring_rules_fails_loudly():
    with pytest.raises(SkillRulesError, match="Scoring Formula"):
        read_rules(NO_RULES)


# --- freshness windows from any vendored file ---------------------------------------

def test_trigger_mapping_freshness_windows():
    windows = read_freshness_windows(TRIGGER_MAPPING)
    assert [w.days for w in windows] == [30, 28]
    assert "After 4 weeks, the role may be filled or paused" in windows[1].quote
