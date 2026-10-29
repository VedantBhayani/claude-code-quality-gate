"""signal_jobs: one job per (post, arm, repeat), arms taken from config/gate.toml."""
from datetime import date
from pathlib import Path

import pytest

from quality_gate.config import load_config
from quality_gate.runner import signal_jobs
from quality_gate.skill_rules import PreparedSkill
from quality_gate.types import Post

SKILL = PreparedSkill(source=Path("s.md"), text="x", sha256="h")


def post(pid):
    return Post(pid, "Acme", "acme.com", "SDR", f"https://x/{pid}", date(2026, 10, 1), date(2026, 10, 2), "lever", "t")


def test_pinned_arms_repeat_and_opus_runs_only_on_its_subset(config_root):
    arms = load_config(config_root).arms()
    jobs = signal_jobs([post("a"), post("b")], arms, repeats=2, skill=SKILL, schema={}, prompt_for=lambda p: p.post_id,
                       subsets={"opus": {"b"}})
    keys = {(j.post_id, j.arm, j.repeat): j.model for j in jobs}
    assert keys == {
        ("a", "haiku-5-5", 1): "claude-haiku-5-5", ("a", "haiku-5-5", 2): "claude-haiku-5-5",
        ("b", "haiku-5-5", 1): "claude-haiku-5-5", ("b", "haiku-5-5", 2): "claude-haiku-5-5",
        ("a", "sonnet-5-5", 1): "claude-sonnet-5-5", ("a", "sonnet-5-5", 2): "claude-sonnet-5-5",
        ("b", "sonnet-5-5", 1): "claude-sonnet-5-5", ("b", "sonnet-5-5", 2): "claude-sonnet-5-5",
        ("b", "opus-5-5", 1): "claude-opus-5-5", ("b", "opus-5-5", 2): "claude-opus-5-5",
    }


def test_subset_arm_without_its_subset_is_refused(config_root):
    with pytest.raises(ValueError, match="opus"):
        signal_jobs([post("a")], load_config(config_root).arms(), repeats=1, skill=SKILL, schema={},
                    prompt_for=str)
