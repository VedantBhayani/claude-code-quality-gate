"""prepare_skill: the exact text injected into a run, plus its SHA-256 hash."""
from pathlib import Path

from quality_gate.skill_rules import prepare_skill

ROOT = Path(__file__).resolve().parents[2]
VENDORED = ROOT / "evals" / "skills"
FIXTURES = ROOT / "tests" / "fixtures" / "skills"

# sha256 of the upstream blob signal-scoring/intent-signals/SKILL.md at
# kenny589/gtm-flywheel@ba67446 (LF endings, no model: frontmatter to strip).
UPSTREAM_INTENT_SIGNALS_SHA256 = "3623351d927c50d3d0cca711f52ba80cafc7f088de0582ba33a625ee1bbd8dd4"


def test_vendored_skill_without_model_frontmatter_is_injected_unchanged():
    skill = prepare_skill(VENDORED / "intent-signals" / "SKILL.md")
    assert skill.sha256 == UPSTREAM_INTENT_SIGNALS_SHA256
    assert skill.text.startswith("---\nname: intent-signals\n")


def test_model_frontmatter_line_is_stripped_and_nothing_else():
    skill = prepare_skill(FIXTURES / "with-model-frontmatter" / "SKILL.md")
    assert skill.text == (
        "---\n"
        "name: tiny-skill\n"
        'description: "A tiny skill used to test frontmatter stripping."\n'
        "---\n"
        "\n"
        "# Tiny skill\n"
        "\n"
        "Keep this body line, including model: inside the body.\n"
    )


def test_model_in_body_is_kept():
    skill = prepare_skill(FIXTURES / "with-model-frontmatter" / "SKILL.md")
    assert "including model: inside the body." in skill.text


def test_hash_ignores_crlf_checkout(tmp_path):
    lf = (VENDORED / "intent-signals" / "SKILL.md").read_bytes().replace(b"\r\n", b"\n")
    crlf_copy = tmp_path / "SKILL.md"
    crlf_copy.write_bytes(lf.replace(b"\n", b"\r\n"))
    assert prepare_skill(crlf_copy).sha256 == UPSTREAM_INTENT_SIGNALS_SHA256
    assert "\r" not in prepare_skill(crlf_copy).text


def test_hash_is_stable_and_changes_with_content(tmp_path):
    a = prepare_skill(VENDORED / "intent-signals" / "SKILL.md")
    assert prepare_skill(VENDORED / "intent-signals" / "SKILL.md") == a
    edited = tmp_path / "SKILL.md"
    edited.write_text(a.text + "\nOne more line.\n", encoding="utf-8")
    assert prepare_skill(edited).sha256 != a.sha256


def test_write_to_produces_the_file_passed_to_append_system_prompt_file(tmp_path):
    skill = prepare_skill(FIXTURES / "with-model-frontmatter" / "SKILL.md")
    out = skill.write_to(tmp_path / "skill.md")
    assert out.read_bytes() == skill.text.encode("utf-8")
