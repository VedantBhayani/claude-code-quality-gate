"""freshness_finding: every freshness window stated in the skill files, with its source line."""
from pathlib import Path

from quality_gate.findings import freshness_finding, render_freshness_finding

TRIGGERS = """\
## Triggers

#### Trigger 1: New Funding Round

| Component | Detail |
|-----------|--------|
| **Urgency window** | Contact within 2 weeks of announcement. After 30 days, the signal is stale. |

#### Trigger 2: Hiring for Target Role

| Component | Detail |
|-----------|--------|
| **Urgency window** | Contact within 1 week of posting. After 4 weeks, the role may be filled or paused. |
"""

TIPS = """\
## Tips
- The best time to email someone is within 48 hours of a signal firing. After 2 weeks, the signal is stale.
- After 3 months, double down on the winners.
"""


MATRIX = """\
| Factor | High (5) | Medium (3) | Low (1) |
|--------|----------|------------|---------|
| **Recency** | Last 7 days | Last 30 days | 30-90 days |
"""

DECAY = """\
| Signal | Max Points | Scoring | Decay Rate |
|--------|-----------|---------|------------|
| Hiring for target role | 15 | Active posting = 15, Recently filled = 8 | -3/week |
| Recent funding | 15 | < 30 days = 15, 30-90 days = 10, 90-180 = 5 | -2/month |
"""


def _skill(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_lists_stale_and_contact_windows_with_their_source_lines(tmp_path):
    finding = freshness_finding({"trigger-mapping": _skill(tmp_path, "tm", TRIGGERS)})
    got = [(w.skill, w.line, w.kind, w.days, w.scope) for w in finding.windows]
    assert got == [
        ("trigger-mapping", 7, "contact_within", 14, "New Funding Round"),
        ("trigger-mapping", 7, "stale_after", 30, "New Funding Round"),
        ("trigger-mapping", 13, "contact_within", 7, "Hiring for Target Role"),
        ("trigger-mapping", 13, "stale_after", 28, "Hiring for Target Role"),
    ]
    assert finding.windows[2].quote == (
        "| **Urgency window** | Contact within 1 week of posting. "
        "After 4 weeks, the role may be filled or paused. |"
    )


def test_hours_convert_to_days_and_a_feedback_loop_period_is_not_a_window(tmp_path):
    finding = freshness_finding({"intent-signals": _skill(tmp_path, "is", TIPS)})
    got = [(w.line, w.kind, w.days, w.scope) for w in finding.windows]
    assert got == [
        (2, "contact_within", 2, "all signals"),
        (2, "stale_after", 14, "all signals"),
    ]


def test_recency_band_row_gives_one_window_per_band(tmp_path):
    finding = freshness_finding({"intent-signals": _skill(tmp_path, "is", MATRIX)})
    got = [(w.line, w.kind, w.days, w.scope) for w in finding.windows]
    assert got == [
        (3, "recency_band", 7, "High"),
        (3, "recency_band", 30, "Medium"),
        (3, "recency_band", 90, "Low"),
    ]


def test_pins_the_window_stated_for_job_postings_because_the_gate_scores_job_posts(tmp_path):
    finding = freshness_finding({
        "intent-signals": _skill(tmp_path, "is", TIPS),
        "trigger-mapping": _skill(tmp_path, "tm", TRIGGERS),
    })
    assert finding.stale_after_days == (14, 28, 30)  # they differ
    assert (finding.pin.stale.skill, finding.pin.stale.line, finding.pin.stale.days) == (
        "trigger-mapping", 13, 28,
    )
    assert (finding.pin.contact.line, finding.pin.contact.days) == (13, 7)


def test_without_a_job_posting_window_pins_the_shortest_stale_window(tmp_path):
    finding = freshness_finding({"intent-signals": _skill(tmp_path, "is", TIPS)})
    assert finding.pin.stale.days == 14
    assert finding.pin.contact.days == 2


def test_rendered_finding_quotes_each_window_and_frames_it_as_a_pin_not_a_fault(tmp_path):
    finding = freshness_finding({
        "intent-signals": _skill(tmp_path, "is", TIPS),
        "trigger-mapping": _skill(tmp_path, "tm", TRIGGERS),
    })
    md = render_freshness_finding(finding)
    assert "The windows differ across files, so here's a single one to pin." in md
    for w in finding.windows:
        assert f"`{w.skill}/SKILL.md:{w.line}`" in md
        assert w.quote.replace("|", "\\|") in md
    assert "**Pin: stale after 28 days, contact within 7 days**" in md
    assert "wrong" not in md.lower()


# --- the vendored files -------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
VENDORED = {
    name: ROOT / "evals" / "skills" / name / "SKILL.md"
    for name in ("intent-signals", "trigger-mapping", "lead-prioritization")
}
FINDING_DOC = ROOT / "evals" / "findings" / "freshness-windows.md"


def test_vendored_files_state_these_windows():
    finding = freshness_finding(VENDORED)
    got = [(w.skill, w.line, w.kind, w.days, w.scope) for w in finding.windows if w.kind != "decay"]
    assert got == [
        ("intent-signals", 98, "recency_band", 7, "High"),
        ("intent-signals", 98, "recency_band", 30, "Medium"),
        ("intent-signals", 98, "recency_band", 90, "Low"),
        ("intent-signals", 245, "contact_within", 2, "all signals"),
        ("intent-signals", 245, "stale_after", 14, "all signals"),
        ("trigger-mapping", 39, "contact_within", 14, "New Funding Round"),
        ("trigger-mapping", 39, "stale_after", 30, "New Funding Round"),
        ("trigger-mapping", 50, "contact_within", 7, "Hiring for Target Role"),
        ("trigger-mapping", 50, "stale_after", 28, "Hiring for Target Role"),
        ("trigger-mapping", 72, "contact_within", 14, "Tech Stack Change"),
        ("trigger-mapping", 127, "contact_within", 2, "Content Publication"),
    ]
    hiring_decay = [w for w in finding.windows if w.kind == "decay" and w.scope == "Hiring for target role"]
    assert [(w.skill, w.line, w.points, w.days) for w in hiring_decay] == [("lead-prioritization", 79, 3, 7)]
    assert finding.stale_after_days == (14, 28, 30)
    assert (finding.pin.stale.line, finding.pin.stale.days, finding.pin.contact.days) == (50, 28, 7)


def test_checked_in_finding_matches_the_vendored_files():
    assert FINDING_DOC.read_text(encoding="utf-8") == render_freshness_finding(freshness_finding(VENDORED))


def test_decay_rates_are_listed_as_points_lost_per_period(tmp_path):
    finding = freshness_finding({"lead-prioritization": _skill(tmp_path, "lp", DECAY)})
    got = [(w.line, w.kind, w.points, w.days, w.scope) for w in finding.windows]
    assert got == [
        (3, "decay", 3, 7, "Hiring for target role"),
        (4, "decay", 2, 30, "Recent funding"),
    ]
