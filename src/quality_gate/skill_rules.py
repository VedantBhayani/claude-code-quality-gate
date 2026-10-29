"""Vendored SKILL.md files: the text injected into a run, and the rules it is judged by.

prepare_skill(path) gives the exact text passed to --append-system-prompt-file:
line endings normalised to LF (so a CRLF checkout hashes the same) and any
`model:` key removed from the YAML frontmatter (the gate picks the model, not
the file). Its sha256 is the skill hash recorded on every RunRecord.

read_rules(path) reads the rules a run is judged by out of that same file, so
each run is checked only against the file it was given.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PreparedSkill:
    source: Path
    text: str
    sha256: str

    def write_to(self, path: Path) -> Path:
        """Write the injected text byte-for-byte (UTF-8, LF) and return the path."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.text.encode("utf-8"))
        return path


_FRONTMATTER = re.compile(r"\A---\n(.*?\n)---\n", re.DOTALL)
_MODEL_KEY = re.compile(r"^model\s*:.*\n", re.MULTILINE)


def _read_lf(path: Path) -> str:
    return Path(path).read_bytes().decode("utf-8").replace("\r\n", "\n")


def strip_model_frontmatter(text: str) -> str:
    m = _FRONTMATTER.match(text)
    if not m:
        return text
    return "---\n" + _MODEL_KEY.sub("", m.group(1)) + "---\n" + text[m.end():]


def prepare_skill(path: Path) -> PreparedSkill:
    text = strip_model_frontmatter(_read_lf(path))
    return PreparedSkill(source=Path(path), text=text, sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())


# --- rules -------------------------------------------------------------------------

class SkillRulesError(ValueError):
    """A rule the gate judges by could not be read from the given SKILL.md."""


FACTORS: tuple[str, ...] = ("recency", "directness", "frequency", "specificity", "source")


@dataclass(frozen=True)
class Tier:
    name: str
    min_score: int  # inclusive; the lowest tier starts at 0
    action: str


@dataclass(frozen=True)
class RecencyBand:
    rating: str  # "High" | "Medium" | "Low"
    max_days: int  # inclusive upper bound on signal age in days


@dataclass(frozen=True)
class FreshnessWindow:
    days: int  # the signal is stale after this many days
    quote: str  # the source line, verbatim (stripped)
    line: int  # 1-based line number in the source file


@dataclass(frozen=True)
class SkillRules:
    source: Path
    skill_sha256: str
    weights: dict[str, int]  # factor -> multiplier, keys in FACTORS order
    tiers: tuple[Tier, ...]  # highest first
    recency_bands: tuple[RecencyBand, ...]  # freshest first
    freshness_windows: tuple[FreshnessWindow, ...]

    def tier_for(self, score: int) -> str:
        for tier in self.tiers:
            if score >= tier.min_score:
                return tier.name
        raise SkillRulesError(f"score {score} is below every tier in {self.source}")

    def recency_rating_for(self, age_days: int) -> str | None:
        """Band for a signal age in days; None if older than the last band."""
        for band in self.recency_bands:
            if age_days <= band.max_days:
                return band.rating
        return None


_UNIT_DAYS = {"day": 1, "week": 7}
_STALE_AFTER = re.compile(r"\bAfter (\d+) (day|week)s?\b", re.IGNORECASE)
_WEIGHT = re.compile(r"\((\w+) × (\d+)\)")
_TIER_ROW = re.compile(r"^\|\s*(?:(\d+)\s*-\s*\d+|Below \d+)\s*\|\s*(\w+)\s*\|\s*(.+?)\s*\|$")
_RECENCY_ROW = re.compile(r"^\|\s*\*\*Recency\*\*\s*\|(.+)\|\s*$", re.MULTILINE)
_MATRIX_HEADER = re.compile(r"^\|\s*Factor\s*\|(.+)\|\s*$", re.MULTILINE)


def _section(text: str, heading: str, source: Path) -> str:
    m = re.search(rf"^#+ {re.escape(heading)}\s*$", text, re.MULTILINE)
    if not m:
        raise SkillRulesError(f"no '{heading}' section in {source}")
    end = re.search(r"^(#+ |---\s*$)", text[m.end():], re.MULTILINE)
    return text[m.end(): m.end() + end.start()] if end else text[m.end():]


def _weights(section: str, source: Path) -> dict[str, int]:
    found = {name.lower(): int(w) for name, w in _WEIGHT.findall(section)}
    if set(found) != set(FACTORS):
        raise SkillRulesError(f"Scoring Formula in {source} names {sorted(found)}, expected {list(FACTORS)}")
    return {f: found[f] for f in FACTORS}


def _tiers(section: str, source: Path) -> tuple[Tier, ...]:
    tiers = []
    for line in section.splitlines():
        m = _TIER_ROW.match(line.strip())
        if m:
            tiers.append(Tier(name=m.group(2), min_score=int(m.group(1) or 0), action=m.group(3)))
    if not tiers:
        raise SkillRulesError(f"no tier table under Scoring Formula in {source}")
    return tuple(sorted(tiers, key=lambda t: t.min_score, reverse=True))


def _recency_bands(section: str, source: Path) -> tuple[RecencyBand, ...]:
    header, row = _MATRIX_HEADER.search(section), _RECENCY_ROW.search(section)
    if not header or not row:
        raise SkillRulesError(f"no Recency row in the Signal Strength Matrix in {source}")
    ratings = [c.strip().removesuffix(" Score") for c in header.group(1).split("|")]
    cells = [c.strip() for c in row.group(1).split("|")]
    if len(ratings) != len(cells):
        raise SkillRulesError(f"Recency row in {source} does not match the matrix header")
    bands = []
    for rating, cell in zip(ratings, cells):
        days = re.findall(r"(\d+) days", cell)
        if not days:
            raise SkillRulesError(f"Recency cell {cell!r} in {source} states no day count")
        bands.append(RecencyBand(rating=rating, max_days=int(days[-1])))
    return tuple(bands)


def read_freshness_windows(path: Path) -> tuple[FreshnessWindow, ...]:
    """Every 'After N days/weeks' staleness statement in the file, with its source line."""
    windows = []
    for n, line in enumerate(_read_lf(path).split("\n"), 1):
        for m in _STALE_AFTER.finditer(line):
            days = int(m.group(1)) * _UNIT_DAYS[m.group(2).lower()]
            windows.append(FreshnessWindow(days=days, quote=line.strip(), line=n))
    return tuple(windows)


def read_rules(path: Path) -> SkillRules:
    """Factor weights, tiers, recency bands and freshness windows from one SKILL.md."""
    path = Path(path)
    skill = prepare_skill(path)
    formula = _section(skill.text, "Scoring Formula", path)
    matrix = _section(skill.text, "Signal Strength Matrix", path)
    return SkillRules(
        source=path,
        skill_sha256=skill.sha256,
        weights=_weights(formula, path),
        tiers=_tiers(formula, path),
        recency_bands=_recency_bands(matrix, path),
        freshness_windows=read_freshness_windows(path),
    )
