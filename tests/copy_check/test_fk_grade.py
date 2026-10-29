"""Flesch-Kincaid grade level, implemented in-repo (Resolution 14).

Reference values:
- Formula and coefficients: Kincaid, Fishburne, Rogers & Chissom (1975), "Derivation of New
  Readability Formulas ... for Navy Enlisted Personnel", Research Branch Report 8-75:
  grade = 0.39 * (words / sentences) + 11.8 * (syllables / words) - 15.59.
- Worked example: Wikipedia, "Flesch-Kincaid readability tests", section "Flesch-Kincaid grade
  level": the sentence "The Australian platypus is seemingly a hybrid of a mammal and reptilian
  creature." has 13 words and 24 syllables and scores grade 11.3.
"""
import pytest

from quality_gate.copy_check.fk_grade import fk_grade, grade_from_counts, text_stats

PLATYPUS = "The Australian platypus is seemingly a hybrid of a mammal and reptilian creature."


def test_formula_matches_published_worked_example_counts():
    # Wikipedia: 13 words, 1 sentence, 24 syllables -> 11.3
    assert round(grade_from_counts(words=13, sentences=1, syllables=24), 1) == 11.3


def test_formula_coefficients_from_kincaid_1975():
    # one word per sentence, one syllable per word: 0.39 + 11.8 - 15.59
    assert grade_from_counts(words=1, sentences=1, syllables=1) == pytest.approx(-3.4)


def test_platypus_sentence_counts_match_wikipedia():
    stats = text_stats(PLATYPUS)
    assert (stats.words, stats.sentences, stats.syllables) == (13, 1, 24)


def test_platypus_sentence_scores_grade_11_3():
    assert round(fk_grade(PLATYPUS), 1) == 11.3


@pytest.mark.parametrize(
    "word, syllables",
    [
        ("cat", 1), ("the", 1), ("make", 1), ("table", 2), ("hiring", 2),
        ("team", 1), ("quickly", 2), ("question", 2), ("revenue", 3), ("seemingly", 3),
        ("creature", 2), ("Australian", 3), ("I", 1),
    ],
)
def test_syllable_counts_for_common_words(word, syllables):
    assert text_stats(word).syllables == syllables


def test_sentences_split_on_terminal_punctuation_and_line_breaks():
    # A greeting line with no full stop still ends a sentence, as Hemingway treats paragraphs.
    stats = text_stats("Hi Sam,\nYou are hiring. Is that right?\n\nThanks")
    assert stats.sentences == 4
    assert stats.words == 9


def test_empty_text_has_no_grade():
    with pytest.raises(ValueError):
        fk_grade("   ")
