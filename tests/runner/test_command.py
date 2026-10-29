"""The argv for one isolated, cheap `claude -p` call ."""
import json
from pathlib import Path

import pytest

from quality_gate.config import Config, MissingFactError
from quality_gate.runner import RunSettings, build_command

SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}


def _flag(argv, name):
    return argv[argv.index(name) + 1]


def test_command_pins_model_injects_skill_file_and_inlines_schema(tmp_path):
    skill_file = tmp_path / "skill.md"
    argv = build_command(
        model="claude-haiku-5-5",
        prompt="one post",
        skill_file=skill_file,
        schema=SCHEMA,
        settings=RunSettings(effort="cli-default", tools="", max_turns=1),
    )
    assert argv[0] == "-p"
    assert _flag(argv, "--model") == "claude-haiku-5-5"
    assert _flag(argv, "--append-system-prompt-file") == str(skill_file)
    assert _flag(argv, "--json-schema") == '{"type":"object","properties":{"a":{"type":"string"}},"required":["a"]}'
    assert json.loads(_flag(argv, "--json-schema")) == SCHEMA
    assert _flag(argv, "--output-format") == "json"
    assert "--verbose" in argv  # so system/init and rate_limit_event reach the output (assumed, see fixtures/cli)
    assert "--no-session-persistence" in argv
    assert _flag(argv, "--tools") == ""
    assert _flag(argv, "--max-turns") == "1"
    assert argv[-1] == "one post"


def test_command_never_uses_bare_fallback_model_or_default_effort_flag(tmp_path):
    argv = build_command(
        model="claude-sonnet-5-5",
        prompt="p",
        skill_file=tmp_path / "s.md",
        schema=SCHEMA,
        settings=RunSettings(effort="cli-default", tools=None, max_turns=None),
    )
    for banned in ("--bare", "--fallback-model", "--effort", "--tools", "--max-turns"):
        assert banned not in argv


def test_explicit_effort_is_passed_the_same_way_for_every_model(tmp_path):
    settings = RunSettings(effort="low", tools="", max_turns=2)
    for model in ("claude-haiku-5-5", "claude-sonnet-5-5"):
        argv = build_command(model=model, prompt="p", skill_file=tmp_path / "s.md", schema=SCHEMA, settings=settings)
        assert _flag(argv, "--effort") == "low"


def test_settings_from_config_read_tool_and_turn_flags_from_pilot_facts():
    cfg = Config(gate={"run": {"effort": "cli-default"}}, facts={"pilot": {"tools_flag": "", "max_turns": 2}})
    assert RunSettings.from_config(cfg) == RunSettings(effort="cli-default", tools="", max_turns=2)


def test_settings_from_config_refuse_when_pilot_has_not_decided_the_flags():
    cfg = Config(gate={"run": {"effort": "cli-default"}}, facts={})
    with pytest.raises(MissingFactError, match="pilot.tools_flag"):
        RunSettings.from_config(cfg)
