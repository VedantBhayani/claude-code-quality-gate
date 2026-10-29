"""Which model wrote the answer, from a real result whose modelUsage also holds a
Claude Code background call on Haiku 5.5 (tests/fixtures/cli/real_sonnet_with_haiku_helper.json).

The answering model is the modelUsage entry whose cache tokens equal the top-level
`usage` (the main turn); the background call has none. A run whose main turn is
billed to another model is still caught.
"""
import copy
import json
from pathlib import Path

from quality_gate.runner.output import answering_models, interpret

REAL = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "cli" /
                   "real_sonnet_with_haiku_helper.json").read_text(encoding="utf-8"))


def test_real_run_answer_is_sonnet_and_the_haiku_call_is_a_helper():
    assert answering_models(REAL["usage"], REAL["modelUsage"]) == ("claude-sonnet-5-5",)


def test_helper_merged_into_the_same_model_still_resolves():
    usage = REAL["modelUsage"]["claude-haiku-5-5"]
    merged = {"claude-haiku-5-5": {**usage, "inputTokens": 1176, "outputTokens": 18,
                                   "cacheReadInputTokens": 14302, "cacheCreationInputTokens": 14258}}
    assert answering_models(REAL["usage"], merged) == ("claude-haiku-5-5",)


def test_main_turn_billed_to_another_model_is_reported_as_that_model():
    mu = copy.deepcopy(REAL["modelUsage"])
    mu["claude-opus-5-5"] = mu.pop("claude-sonnet-5-5")
    assert answering_models(REAL["usage"], mu) == ("claude-opus-5-5",)


def test_no_entry_matching_the_main_turn_gives_no_answering_model():
    mu = copy.deepcopy(REAL["modelUsage"])
    mu["claude-sonnet-5-5"]["cacheReadInputTokens"] = 1
    assert answering_models(REAL["usage"], mu) == ()


def test_without_cache_tokens_the_output_tokens_decide():
    usage = {"input_tokens": 50, "output_tokens": 300, "cache_read_input_tokens": 0,
             "cache_creation_input_tokens": 0}
    mu = {"claude-haiku-5-5": {"inputTokens": 1174, "outputTokens": 14},
          "claude-sonnet-5-5": {"inputTokens": 50, "outputTokens": 300}}
    assert answering_models(usage, mu) == ("claude-sonnet-5-5",)


def test_interpret_records_the_answering_model_and_full_model_usage():
    out = interpret(json.dumps(REAL), {"type": "object"})
    assert out.model_usage_keys == ("claude-haiku-5-5", "claude-sonnet-5-5")
    assert out.answer_models == ("claude-sonnet-5-5",)
    assert out.model_usage["claude-haiku-5-5"]["outputTokens"] == 14
