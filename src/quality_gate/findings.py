"""Documentation findings about the vendored skill files.

freshness_finding(skills) lists every freshness window the given SKILL.md files
state, each with its file, line number and the line quoted verbatim, and
proposes one window to pin. The framing is "the windows differ across files,
so here's a single one to pin", never "the skills are wrong".
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

_UNIT_DAYS = {"hour": 1 / 24, "day": 1, "week": 7, "month": 30}

# "After 2 weeks, the signal is stale": the age past which a signal is not used.
_STALE_AFTER = re.compile(r"\bAfter (\d+) (day|week)s?\b", re.IGNORECASE)
# "Contact within 1 week of posting": how soon after the event to reach out.
_CONTACT_WITHIN = re.compile(r"\bwithin (\d+) (hour|day|week)s? of\b", re.IGNORECASE)
# "| **Recency** | Last 7 days | Last 30 days | 30-90 days |": the scoring bands.
_RECENCY_ROW = re.compile(r"^\|\s*\*\*Recency\*\*\s*\|(.+)\|\s*$")
_BAND_DAYS = re.compile(r"(\d+)\s*days")
_MATRIX_HEADER = re.compile(r"^\|\s*Factor\s*\|(.+)\|\s*$")
# "| Hiring for target role | 15 | ... | -3/week |": points lost per period.
_DECAY = re.compile(r"-(\d+)/(day|week|month)\b")
_TRIGGER_HEADING =re.compile(r"^#+ Trigger \d+: (.+?)\s*$")
_HEADING = re.compile(r"^#+ ")


@dataclass(frozen=True)
class Window:
    skill: str  # skill name, e.g. "trigger-mapping"
    line: int  # 1-based line number in that skill's SKILL.md
    kind: str  # "stale_after" | "contact_within" | "recency_band" | "decay"
    days: float  # window length in days (48 hours = 2); for "decay", the period length
    scope: str  # the signal the window is stated for ("all signals"), or the band name
    quote: str  # the source line, verbatim (stripped)
    points: int | None = None  # "decay" only: points lost per period


@dataclass(frozen=True)
class Pin:
    """The single window proposed for every file: stale after, and contact within."""
    stale: Window
    contact: Window | None
    reason: str


@dataclass(frozen=True)
class FreshnessFinding:
    windows: tuple[Window, ...]
    pin: Pin | None

    @property
    def stale_after_days(self) -> tuple[float, ...]:
        """The distinct stale-after windows stated, shortest first."""
        return tuple(sorted({w.days for w in self.windows if w.kind == "stale_after"}))


_JOB_POSTING = re.compile(r"\bhiring\b|\bjob\b|\bposting\b", re.IGNORECASE)


def _pin(windows: list[Window]) -> Pin | None:
    stale = [w for w in windows if w.kind == "stale_after"]
    if not stale:
        return None
    for_posts = [w for w in stale if _JOB_POSTING.search(w.scope) or _JOB_POSTING.search(w.quote)]
    if for_posts:
        chosen = for_posts[0]
        reason = (
            "it is the only window stated for job postings, and job posts are the "
            "signals this gate scores"
        )
    else:
        chosen = min(stale, key=lambda w: w.days)
        reason = "it is the shortest stale window stated, so pinning it never keeps a signal one file calls stale"
    contact = next(
        (w for w in windows if w.kind == "contact_within" and (w.skill, w.line) == (chosen.skill, chosen.line)),
        None,
    )
    return Pin(stale=chosen, contact=contact, reason=reason)


def _days(amount: str, unit: str) -> float:
    days = int(amount) * _UNIT_DAYS[unit.lower()]
    return int(days) if days == int(days) else days


def _windows(skill: str, path: Path) -> list[Window]:
    text = Path(path).read_bytes().decode("utf-8").replace("\r\n", "\n")
    found: list[Window] = []
    scope = "all signals"
    bands: list[str] = []
    for n, line in enumerate(text.split("\n"), 1):
        header = _MATRIX_HEADER.match(line)
        if header:
            # "High Score" / "High (5)" -> "High"
            bands = [c.split("(")[0].split()[0] for c in header.group(1).split("|") if c.strip()]
            continue
        recency = _RECENCY_ROW.match(line)
        if recency:
            cells = [c.strip() for c in recency.group(1).split("|")]
            for i, cell in enumerate(cells):
                numbers = _BAND_DAYS.findall(cell) or re.findall(r"(\d+)", cell)
                if numbers:
                    found.append(Window(
                        skill=skill, line=n, kind="recency_band", days=int(numbers[-1]),
                        scope=bands[i] if i < len(bands) else f"band {i + 1}", quote=line.strip(),
                    ))
            continue
        decay = _DECAY.search(line)
        if decay and line.lstrip().startswith("|"):
            found.append(Window(
                skill=skill, line=n, kind="decay", days=_days("1", decay.group(2)),
                scope=line.strip().strip("|").split("|")[0].strip(), quote=line.strip(),
                points=int(decay.group(1)),
            ))
            continue
        heading = _TRIGGER_HEADING.match(line)
        if heading:
            scope = heading.group(1)
            continue
        if _HEADING.match(line):
            scope = "all signals"
            continue
        hits = [(m.start(), "contact_within", m) for m in _CONTACT_WITHIN.finditer(line)]
        hits += [(m.start(), "stale_after", m) for m in _STALE_AFTER.finditer(line)]
        for _, kind, m in sorted(hits, key=lambda h: h[0]):
            found.append(Window(
                skill=skill, line=n, kind=kind, days=_days(m.group(1), m.group(2)),
                scope=scope, quote=line.strip(),
            ))
    return found


def _span(days: float) -> str:
    if days < 1:
        return f"{round(days * 24)} hours"
    return "1 day" if days == 1 else f"{days:g} days"


def _says(w: Window) -> str:
    if w.kind == "stale_after":
        return f"stale after {_span(w.days)}"
    if w.kind == "contact_within":
        return f"contact within {_span(w.days)}"
    if w.kind == "recency_band":
        return f"recency band {w.scope}: up to {_span(w.days)}"
    period = {1: "day", 7: "week", 30: "month"}.get(w.days, _span(w.days))
    points = "1 point" if w.points == 1 else f"{w.points} points"
    return f"loses {points} per {period} (no fixed cutoff)"


def render_freshness_finding(finding: FreshnessFinding) -> str:
    """The finding as markdown: every window with its quoted line, then the one window to pin."""
    out = [
        "# Documentation finding: freshness windows",
        "",
        "The windows differ across files, so here's a single one to pin.",
        "",
        "Which window a run applies depends on which file it was given. Each file is "
        "self-consistent for the job it describes; pinning one window just makes runs comparable.",
        "",
        f"Distinct stale-after windows stated: {', '.join(_span(d) for d in finding.stale_after_days) or 'none'}.",
        "",
        "## Every window stated",
        "",
        "Paths are relative to `evals/skills/`. Quotes are the source line verbatim.",
        "",
        "| Source | Applies to | Says | Quoted line |",
        "|---|---|---|---|",
    ]
    for w in finding.windows:
        scope = "all signals" if w.kind == "recency_band" else w.scope
        out.append(
            f"| `{w.skill}/SKILL.md:{w.line}` | {scope} | {_says(w)} | {w.quote.replace('|', chr(92) + '|')} |"
        )
    out += ["", "## Proposed pin", ""]
    pin = finding.pin
    if pin is None:
        out.append("No stale-after window is stated, so there is nothing to pin.")
    else:
        contact = f", contact within {_span(pin.contact.days)}" if pin.contact else ""
        out += [
            f"**Pin: stale after {_span(pin.stale.days)}{contact}**, from "
            f"`{pin.stale.skill}/SKILL.md:{pin.stale.line}`, because {pin.reason}.",
            "",
            "Stating this one window in every file (or passing it to every run) means the "
            "freshness call no longer depends on which file was loaded.",
        ]
    return "\n".join(out) + "\n"


def freshness_finding(skills: Mapping[str, Path]) -> FreshnessFinding:
    """Every freshness window stated in the given skills ({name: SKILL.md path}), in order."""
    windows: list[Window] = []
    for skill, path in skills.items():
        windows += _windows(skill, path)
    return FreshnessFinding(windows=tuple(windows), pin=_pin(windows))
