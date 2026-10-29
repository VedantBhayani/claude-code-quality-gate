"""Kenny's copy QA checklist, checked in code (Part B, Resolution 14).

Source: evals/skills/copy-frameworks/SKILL.md, "Copy QA Checklist", plus its subject rule
"Never use brackets, exclamation marks, or emojis in subjects". One CheckResult per item that
code can check, in CHECK_NAMES order. The tone, "so what" and mobile-preview items need a human
and are not checked here.

All checks are exact except first_line_signal, which is a heuristic (heuristic=True): the first
line after any greeting must contain the role title or a key term from the signal's evidence.

Self-contained: depends only on the standard library, fk_grade, and quality_gate.types.CheckResult.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from quality_gate.copy_check.fk_grade import fk_grade
from quality_gate.types import CheckResult

CHECK_NAMES: tuple[str, ...] = (
    "subject",
    "first_line_signal",
    "length",
    "reading_level",
    "cta",
    "variables",
    "spam_words",
)

# Higher = worse when failed. Used by rank.rank_worst_first as the tie-break after failed count.
SEVERITY: dict[str, int] = {
    "variables": 3,  # a broken merge field reaches the prospect
    "spam_words": 3,  # deliverability risk
    "length": 2,
    "cta": 2,
    "first_line_signal": 2,
    "subject": 2,
    "reading_level": 1,
}

SUBJECT_WORDS = (3, 5)
LENGTH_WARN_FROM = 120  # "Under 120 words"
LENGTH_MAX = 150  # "150 absolute max"
GRADE_BAND = (5.0, 8.0)  # "Grade 5-7": grade levels 5, 6 and 7, i.e. 5.0 <= grade < 8.0
SPAM_PATTERNS: dict[str, re.Pattern[str]] = {
    "free": re.compile(r"\bfree\b", re.I),
    "guarantee": re.compile(r"\bguarantee[sd]?\b", re.I),
    "act now": re.compile(r"\bact\s+now\b", re.I),
    "limited time": re.compile(r"\blimited[\s-]+time\b", re.I),
}
BOOK_A_CALL = re.compile(r"\bbook\s+a\s+call\b", re.I)

_VARIABLE = re.compile(r"\{\{[^{}]*\}\}")
_PLACEHOLDER = re.compile(r"\[[A-Za-z][A-Za-z ]{0,40}\]")
_WORD = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")
_BRACKETS = re.compile(r"[\[\](){}<>]")
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U00002B00-\U00002BFF️]"
)
_GREETING = re.compile(r"^(hi|hey|hello|dear|good (morning|afternoon|evening))\b", re.I)
_QUESTION = re.compile(r"[^.!?\n]*\?")
# Words too generic to count as "a key term from the evidence".
_STOPWORDS = frozenset(
    """a an and are as at be been but by for from has have in is it its of on or our that the
    their this to was we were will with you your they them who what when where which how
    team teams role roles work working join company help looking new about all also can do
    more most into over than then there these those such very just like make get""".split()
)


@dataclass(frozen=True)
class Draft:
    draft_id: str
    subject: str
    body: str


@dataclass(frozen=True)
class SignalContext:
    """The signal the draft was written from: the post's role title and evidence quotes."""

    role_title: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class CopyCheckResult(CheckResult):
    """A CheckResult plus its severity and a warning flag (passed, but over a soft limit)."""

    severity: int = 1
    warning: bool = False


def _result(name: str, passed: bool, reason: str, *, warning: bool = False, heuristic: bool = False) -> CopyCheckResult:
    return CopyCheckResult(
        name=name, passed=passed, reason=reason, heuristic=heuristic,
        severity=SEVERITY[name], warning=warning,
    )


def _lines(body: str) -> list[str]:
    return [line.strip() for line in body.splitlines() if line.strip()]


def _is_greeting(line: str) -> bool:
    return bool(_GREETING.match(line)) or (line.endswith(",") and len(_WORD.findall(line)) <= 3)


def _prose(body: str) -> str:
    """Body lines that end a sentence; drops greeting and sign-off lines like "Hi Sam," / "Alex"."""
    return "\n".join(line for line in _lines(body) if re.search(r"[.!?][\"')”’]*$", line))


def check_subject(draft: Draft) -> CopyCheckResult:
    s = draft.subject.strip()
    problems = []
    n = len(s.split())
    if not SUBJECT_WORDS[0] <= n <= SUBJECT_WORDS[1]:
        problems.append(f"{n} words (needs {SUBJECT_WORDS[0]}-{SUBJECT_WORDS[1]})")
    if s != s.lower():
        problems.append("not lowercase")
    if _BRACKETS.search(s):
        problems.append("contains brackets")
    if "!" in s:
        problems.append("contains '!'")
    if _EMOJI.search(s):
        problems.append("contains an emoji")
    if problems:
        return _result("subject", False, f"subject {s!r}: " + "; ".join(problems))
    return _result("subject", True, f"subject {s!r}: {n} words, lowercase, no brackets/!/emoji")


def evidence_terms(context: SignalContext) -> set[str]:
    words = (w.lower() for quote in context.evidence for w in _WORD.findall(quote))
    return {w for w in words if len(w) >= 3 and w not in _STOPWORDS}


def check_first_line(draft: Draft, context: SignalContext) -> CopyCheckResult:
    lines = [line for line in _lines(draft.body) if not _is_greeting(line)]
    first = lines[0] if lines else ""
    if context.role_title.strip() and context.role_title.strip().lower() in first.lower():
        return _result("first_line_signal", True, f"first line names the role {context.role_title!r}", heuristic=True)
    found = sorted({w.lower() for w in _WORD.findall(first)} & evidence_terms(context))
    if found:
        return _result("first_line_signal", True, f"first line uses evidence term(s) {found}", heuristic=True)
    return _result(
        "first_line_signal", False,
        f"first line {first!r} has neither the role title nor a key evidence term (heuristic)",
        heuristic=True,
    )


def check_length(draft: Draft) -> CopyCheckResult:
    n = len(_WORD.findall(draft.body))
    if n > LENGTH_MAX:
        return _result("length", False, f"{n} words (max {LENGTH_MAX})")
    if n >= LENGTH_WARN_FROM:
        return _result("length", True, f"{n} words: within {LENGTH_MAX} max but not under {LENGTH_WARN_FROM}", warning=True)
    return _result("length", True, f"{n} words (under {LENGTH_WARN_FROM})")


def check_reading_level(draft: Draft) -> CopyCheckResult:
    prose = _prose(draft.body)
    if not _WORD.search(prose):
        return _result("reading_level", False, "no full sentences to grade")
    grade = fk_grade(prose)
    lo, hi = GRADE_BAND
    ok = lo <= grade < hi
    return _result("reading_level", ok, f"Flesch-Kincaid grade {grade:.1f} ({'within' if ok else 'outside'} grade 5-7)")


def check_cta(draft: Draft) -> CopyCheckResult:
    questions = [q.strip() for q in _QUESTION.findall(draft.body)]
    if BOOK_A_CALL.search(draft.body):
        return _result("cta", False, 'CTA asks to "book a call"')
    if len(questions) != 1:
        return _result("cta", False, f"{len(questions)} questions in the body (needs exactly one question CTA)")
    return _result("cta", True, f"one question CTA: {questions[0]!r}")


def check_variables(draft: Draft, merge_fields: frozenset[str] = frozenset()) -> CopyCheckResult:
    """'All {{variables}} resolve correctly for every lead in the list': merge_fields are the ones
    the lead list fills at send time. A bracket placeholder in the body never resolves."""
    found = _VARIABLE.findall(draft.subject) + _VARIABLE.findall(draft.body)
    unresolved = [v for v in found if v not in merge_fields] + _PLACEHOLDER.findall(draft.body)
    if unresolved:
        return _result("variables", False, f"unresolved variables: {', '.join(unresolved)}")
    filled = sorted(set(found))
    if filled:
        return _result("variables", True, f"merge fields filled at send: {', '.join(filled)}")
    return _result("variables", True, "no unresolved {{variables}}")


def check_spam_words(draft: Draft) -> CopyCheckResult:
    text = f"{draft.subject}\n{draft.body}"
    hits = [word for word, pattern in SPAM_PATTERNS.items() if pattern.search(text)]
    if hits:
        return _result("spam_words", False, f"spam trigger words: {', '.join(hits)}")
    return _result("spam_words", True, "no spam trigger words")


def check_draft(draft: Draft, context: SignalContext, merge_fields: frozenset[str] = frozenset()) -> list[CopyCheckResult]:
    """One result per checklist item, in CHECK_NAMES order."""
    return [
        check_subject(draft),
        check_first_line(draft, context),
        check_length(draft),
        check_reading_level(draft),
        check_cta(draft),
        check_variables(draft, merge_fields),
        check_spam_words(draft),
    ]
