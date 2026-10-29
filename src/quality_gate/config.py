"""Load the gate's settled config plus FACT files, failing loudly on missing FACTs.

Settled settings live in config/gate.toml. FACTs (values measured by research,
the data agent or the pilot) live in config/facts/<file>.toml and are read with
Config.fact("<file>.<key>[.<subkey>...]"). A FACT that has not been written yet
raises MissingFactError naming the key and the file it is expected in; it is
never defaulted or guessed.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[2]


class MissingFactError(LookupError):
    """A FACT a caller needs has not been filled in yet."""


@dataclass(frozen=True)
class Config:
    gate: dict[str, Any]
    facts: dict[str, dict[str, Any]]
    title_filter_rules: dict[str, Any] | None = None

    def arms(self, include_candidates: bool = False) -> list[dict[str, Any]]:
        """Pinned arms; with include_candidates, plus each candidate arm whose
        enabling FACT is true. Raises MissingFactError if that FACT is unset."""
        arms = list(self.gate["arms"])
        if include_candidates:
            arms += [a for a in self.gate.get("candidate_arms", []) if self.fact(a["enabled_by_fact"]) is True]
        return arms

    def title_filter(self) -> dict[str, Any]:
        if self.title_filter_rules is None:
            raise MissingFactError("Sales-ish title filter is missing: config/title_filter.toml has not been written yet")
        return self.title_filter_rules

    def fact(self, key: str) -> Any:
        file, _, path = key.partition(".")
        expected = f"config/facts/{file}.toml"
        if not path:
            raise MissingFactError(f"FACT key {key!r} must be '<file>.<key>' (file: {expected})")
        if file not in self.facts:
            raise MissingFactError(f"FACT {key} is missing: {expected} has not been written yet")
        node: Any = self.facts[file]
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                raise MissingFactError(f"FACT {key} is missing: no {path!r} in {expected}")
            node = node[part]
        return node


def _read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def load_config(root: Path | None = None) -> Config:
    root = Path(root) if root is not None else PACKAGE_ROOT
    cfg_dir = root / "config"
    gate = _read_toml(cfg_dir / "gate.toml")
    facts = {p.stem: _read_toml(p) for p in sorted((cfg_dir / "facts").glob("*.toml"))}
    tf_path = cfg_dir / "title_filter.toml"
    title_filter = _read_toml(tf_path) if tf_path.exists() else None
    return Config(gate=gate, facts=facts, title_filter_rules=title_filter)
