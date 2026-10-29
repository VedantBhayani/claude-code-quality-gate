"""The signal-scoring output schema passed inline to `claude -p --json-schema`."""
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from quality_gate.types import SIGNAL_TYPES

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "src" / "quality_gate" / "schemas" / "signal_output.schema.json"

GOOD = {
    "signal": True,
    "signal_type": "sdr_bdr_hiring",
    "evidence": ["We are hiring two SDRs to build our outbound motion."],
    "factors": {"recency": 5, "directness": 3, "frequency": 3, "specificity": 4, "source": 3},
    "total": 37,
    "recency_band": "High",
    "tier": "High",
    "action": "Contact within 3 days",
}


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_is_a_valid_draft07_schema(schema):
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    Draft7Validator.check_schema(schema)


def test_usable_inline_as_one_argv_string(schema):
    inline = json.dumps(schema, separators=(",", ":"), ensure_ascii=False)
    assert "\n" not in inline
    assert json.loads(inline) == schema


def test_accepts_a_complete_output(schema):
    Draft7Validator(schema).validate(GOOD)


def test_accepts_a_not_signal_output_with_no_quotes(schema):
    out = dict(GOOD, signal=False, signal_type="not_signal", evidence=[], tier="Noise")
    Draft7Validator(schema).validate(out)


def test_signal_types_match_the_shared_vocabulary(schema):
    assert tuple(schema["properties"]["signal_type"]["enum"]) == SIGNAL_TYPES


def test_inconsistent_arithmetic_and_tier_still_validate(schema):
    # The checkers, not the schema, catch score/tier errors: the output must reach them.
    out = dict(GOOD, total=12, tier="Critical")
    Draft7Validator(schema).validate(out)


@pytest.mark.parametrize("mutate", [
    lambda o: o.pop("factors"),
    lambda o: o.pop("evidence"),
    lambda o: o["factors"].pop("source"),
    lambda o: o["factors"].update(recency=6),
    lambda o: o["factors"].update(directness=0),
    lambda o: o.update(total=51),
    lambda o: o.update(signal="yes"),
    lambda o: o.update(signal_type="funding"),
    lambda o: o.update(tier="Urgent"),
    lambda o: o.update(recency_band="Stale"),
    lambda o: o.update(extra="field"),
], ids=["no-factors", "no-evidence", "no-source-factor", "rating-6", "rating-0", "total-51",
        "signal-not-bool", "unknown-type", "unknown-tier", "unknown-band", "extra-field"])
def test_rejects_malformed_outputs(schema, mutate):
    out = copy.deepcopy(GOOD)
    mutate(out)
    assert list(Draft7Validator(schema).iter_errors(out))
