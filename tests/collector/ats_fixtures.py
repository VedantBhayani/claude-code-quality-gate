import json
from datetime import date
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "ats"
COLLECTED = date(2026, 10, 22)


def load(name):
    """A saved list response from tests/fixtures/ats/, parsed as JSON."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
