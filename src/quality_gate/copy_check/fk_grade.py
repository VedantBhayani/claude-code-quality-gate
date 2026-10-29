"""Flesch-Kincaid grade level, implemented in-repo (Resolution 14). No dependencies.

grade = 0.39 * (words / sentences) + 11.8 * (syllables / words) - 15.59
(Kincaid et al. 1975, Navy Research Branch Report 8-75.)

Counting rules, kept deliberately simple and deterministic:
- A word is a run of letters/digits (apostrophes and hyphens inside it are kept).
- A sentence ends at . ! ? or at a line break, so a greeting or sign-off line without a full
  stop still counts as its own sentence (as Hemingway App treats paragraphs).
- Syllables are vowel groups (a e i o u y), minus a silent final "e" or "-ed"/"-es" ending,
  never fewer than one per word. This is an estimate, as every FK tool's syllable count is.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_WORD = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")
_SENTENCE_BREAK = re.compile(r"[.!?]+|\n")
_VOWEL_GROUP = re.compile(r"[aeiouy]+")


@dataclass(frozen=True)
class TextStats:
    words: int
    sentences: int
    syllables: int


def count_syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 1
    count = len(_VOWEL_GROUP.findall(w))
    if count > 1:
        if w.endswith("e") and not w.endswith("le") and w[-2] not in "aeiouy":
            count -= 1  # silent e: make, creature
        elif w.endswith("ed") and w[-3] not in "aeiouytd":
            count -= 1  # hired, posted keeps its syllable
        elif w.endswith("es") and w[-3] not in "aeiouysxzh":
            count -= 1  # makes, roles; boxes keeps its syllable
    return max(count, 1)


def text_stats(text: str) -> TextStats:
    words = _WORD.findall(text)
    sentences = sum(1 for part in _SENTENCE_BREAK.split(text) if _WORD.search(part))
    return TextStats(
        words=len(words),
        sentences=sentences,
        syllables=sum(count_syllables(w) for w in words),
    )


def grade_from_counts(*, words: int, sentences: int, syllables: int) -> float:
    if words <= 0 or sentences <= 0:
        raise ValueError("Flesch-Kincaid needs at least one word and one sentence")
    return 0.39 * (words / sentences) + 11.8 * (syllables / words) - 15.59


def fk_grade(text: str) -> float:
    """Flesch-Kincaid grade level of text. Raises ValueError for text with no words."""
    s = text_stats(text)
    return grade_from_counts(words=s.words, sentences=s.sentences, syllables=s.syllables)
