"""This eval's own Part B rule (not in Kenny's checklist): a sample draft signs off with the
{{senderName}} merge field, never a real name, so no draft reads as written by a real person."""
import pytest

from quality_gate.copy_check.checklist import Draft
from quality_gate.gate import check_sign_off


@pytest.mark.parametrize("closing", ["Best,\n{{senderName}}", "{{senderName}}", "Cheers,\n{{senderName}}\n"])
def test_merge_field_sign_off_passes(closing):
    assert check_sign_off(Draft("d", "s", "Hi {{firstName}},\n\nBody?\n\n" + closing)).passed


@pytest.mark.parametrize("closing", ["Best,\nVedant", "Best,\nFrontal", "The Frontal team", "[Sender name]"])
def test_any_other_sign_off_fails_and_names_it(closing):
    r = check_sign_off(Draft("d", "s", "Hi {{firstName}},\n\nBody?\n\n" + closing))
    assert not r.passed and closing.splitlines()[-1] in r.reason and r.name == "sign_off"
