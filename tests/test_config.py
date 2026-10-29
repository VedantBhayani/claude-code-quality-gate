import pytest

from quality_gate.config import MissingFactError, load_config


def test_pinned_arms_are_the_5_5_models(package_root):
    cfg = load_config(package_root)
    assert [a["model"] for a in cfg.arms()] == [
        "claude-haiku-5-5",
        "claude-sonnet-5-5",
        "claude-opus-5-5",
    ]


def test_fact_is_read_from_its_facts_file(config_root):
    (config_root / "config" / "facts" / "pilot.toml").write_text(
        "natural_sample_size = 180\n", encoding="utf-8"
    )
    assert load_config(config_root).fact("pilot.natural_sample_size") == 180


def test_fact_file_not_yet_written_fails_loudly(config_root):
    with pytest.raises(MissingFactError, match="pilot.natural_sample_size.*config/facts/pilot.toml"):
        load_config(config_root).fact("pilot.natural_sample_size")


def test_fact_key_absent_from_existing_file_fails_loudly(config_root):
    (config_root / "config" / "facts" / "pilot.toml").write_text("other = 1\n", encoding="utf-8")
    with pytest.raises(MissingFactError, match="pilot.natural_sample_size"):
        load_config(config_root).fact("pilot.natural_sample_size")


def _write_pilot(root, body):
    (root / "config" / "facts" / "pilot.toml").write_text(body, encoding="utf-8")


def test_haiku_4_5_arm_joins_only_when_pilot_probe_passed(config_root):
    _write_pilot(config_root, "haiku_4_5_probe_passed = true\n")
    models = [a["model"] for a in load_config(config_root).arms(include_candidates=True)]
    assert models[-1] == "claude-haiku-4-5-20251001"
    assert len(models) == 4


def test_haiku_4_5_arm_is_dropped_when_pilot_probe_failed(config_root):
    _write_pilot(config_root, "haiku_4_5_probe_passed = false\n")
    models = [a["model"] for a in load_config(config_root).arms(include_candidates=True)]
    assert "claude-haiku-4-5-20251001" not in models


def test_asking_for_candidate_arms_before_the_probe_fails_loudly(config_root):
    with pytest.raises(MissingFactError, match="haiku_4_5_probe_passed"):
        load_config(config_root).arms(include_candidates=True)


def test_title_filter_is_loaded_when_present(config_root):
    (config_root / "config" / "title_filter.toml").write_text(
        'include = ["\\bSDR\\b"]\nexclude = ["Software Engineer"]\n', encoding="utf-8"
    )
    assert load_config(config_root).title_filter()["exclude"] == ["Software Engineer"]


def test_title_filter_missing_fails_loudly(config_root):
    with pytest.raises(MissingFactError, match="config/title_filter.toml"):
        load_config(config_root).title_filter()


def test_gift_rules_match_resolution_10(package_root):
    gift = load_config(package_root).gate["gift"]
    assert (gift["window_days"], gift["top_n"], gift["rank_by_arm"], gift["rank_by_repeat"]) == (
        14, 50, "sonnet-5-5", 1,
    )
    assert gift["one_row_per_company"] is True


# Shared types (types.py) carry no logic beyond refusing shapes the spec rules out.

def test_hand_label_rejects_unknown_signal_type():
    from quality_gate.types import HandLabel

    with pytest.raises(ValueError, match="signal type"):
        HandLabel(post_id="p1", signal=True, signal_type="marketing_hiring")


def test_hand_label_signal_no_must_be_not_signal():
    from quality_gate.types import HandLabel

    with pytest.raises(ValueError, match="not_signal"):
        HandLabel(post_id="p1", signal=False, signal_type="ae_hiring")
    assert HandLabel(post_id="p1", signal=True, signal_type="ae_hiring").signal_type == "ae_hiring"
