"""Redact personal data (recruiter names, emails, phone numbers, profile links) from post text.

Names are only redacted where a recruiting/contact cue sits next to them, so ordinary
post text (team names, titles) is left alone. Placeholders: [name] [email] [phone] [profile].
"""
from __future__ import annotations

import re

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PROFILE = re.compile(r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9_%-]+/?", re.IGNORECASE)
_PHONE = re.compile(
    r"(?<![\w$])(?:\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b"
    r"|(?<![\w$])\+\d{1,3}(?:[\s.-]\d{2,4}){2,4}\b"
)

_WORD = r"[A-Z](?:[a-z]+|['’][A-Z][a-z]+)(?:-[A-Z][a-z]+)?"  # Jane, O'Neil, Lopez-Garcia
_NAME = rf"{_WORD}(?:\s+{_WORD}){{1,2}}"
_ROLE = (
    r"(?:recruiter|recruiting\s+(?:lead|partner|coordinator|manager)|sourcer"
    r"|talent\s+(?:acquisition\s+)?(?:partner|lead|manager|team)|hiring\s+manager)"
)
_CUE = rf"(?:{_ROLE}|reach\s+out\s+to|contact|questions\s+go\s+to|ask\s+for|email)"
_FILLER = r"(?:(?:our|the|your|is|at|with)\s+){0,3}"
# Cue then name: "Contact our recruiter Jane Doe", "Recruiter: Jane Doe", "talent partner is Priya Raman"
_CUE_THEN_NAME = re.compile(rf"((?i:{_CUE})(?:\s*[:,–-]\s*|\s+){_FILLER}(?i:{_ROLE}\s+)?)({_NAME})")
# Name then role: "Tom Baker, Senior Technical Recruiter"
_NAME_THEN_ROLE = re.compile(rf"({_NAME})(,\s*(?:[A-Z][a-z]+\s+){{0,3}}(?i:{_ROLE}))")

# Capitalised words that are teams or functions, not people.
_NOT_NAMES = {
    "sales", "revenue", "marketing", "operations", "team", "teams", "success", "customer",
    "engineering", "support", "partner", "partners", "account", "people", "talent", "us",
    "hr", "recruiting", "growth", "business", "development", "product", "finance", "legal",
}


def _is_name(candidate: str) -> bool:
    return not any(w.lower() in _NOT_NAMES for w in candidate.split())


def redact(text: str) -> str:
    text = _PROFILE.sub("[profile]", text)
    text = _EMAIL.sub("[email]", text)
    text = _PHONE.sub("[phone]", text)
    text = _CUE_THEN_NAME.sub(lambda m: m[1] + "[name]" if _is_name(m[2]) else m[0], text)
    text = _NAME_THEN_ROLE.sub(lambda m: "[name]" + m[2] if _is_name(m[1]) else m[0], text)
    return text
