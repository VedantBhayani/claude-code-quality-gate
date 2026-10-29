"""The argv for one isolated, cheap `claude -p` call.

Sources: research 02 ("make runs cheap") and 02a sections 3, 5 and 6.
- `--json-schema` is documented inline only, so the schema is passed as one
  compact JSON argv element (never a path, never a shell string).
- `--append-system-prompt-file` carries the stripped SKILL.md.
- Never `--bare` (it ignores the Pro login and needs an API key), never
  `--fallback-model` (the arm must stay one model).
- `--tools` / `--max-turns` come from the pilot (FACT pilot.tools_flag /
  pilot.max_turns) because 02a leaves open whether structured output survives
  them. A FACT value of `false` means "do not pass the flag at all".
- Effort "cli-default" (Resolution 16) passes no `--effort` flag; any other
  value is passed identically on every arm.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quality_gate.config import Config

CLI_DEFAULT_EFFORT = "cli-default"


@dataclass(frozen=True)
class RunSettings:
    effort: str
    tools: str | None  # None: no --tools flag; "" : --tools "" (no tools)
    max_turns: int | None  # None: no --max-turns flag

    @classmethod
    def from_config(cls, cfg: Config) -> "RunSettings":
        tools = cfg.fact("pilot.tools_flag")
        max_turns = cfg.fact("pilot.max_turns")
        return cls(
            effort=cfg.gate["run"]["effort"],
            tools=None if tools is False else str(tools),
            max_turns=None if max_turns is False else int(max_turns),
        )


def inline_schema(schema: dict[str, Any]) -> str:
    return json.dumps(schema, separators=(",", ":"))


def build_command(*, model: str, prompt: str, skill_file: Path, schema: dict[str, Any], settings: RunSettings) -> list[str]:
    """argv after the executable name. The prompt is the last element."""
    argv = [
        "-p",
        "--model", model,
        "--append-system-prompt-file", str(skill_file),
        "--json-schema", inline_schema(schema),
        "--output-format", "json",
        # ASSUMED: with --verbose the json output is the full message list, so the
        # system/init model and any rate_limit_event are visible. The output parser
        # also accepts a bare result object in case it is not (fixtures/cli/PROVENANCE.toml).
        "--verbose",
        "--no-session-persistence",
    ]
    if settings.tools is not None:
        argv += ["--tools", settings.tools]
    if settings.max_turns is not None:
        argv += ["--max-turns", str(settings.max_turns)]
    if settings.effort != CLI_DEFAULT_EFFORT:
        argv += ["--effort", settings.effort]
    argv.append(prompt)
    return argv
