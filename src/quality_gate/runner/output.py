"""Reading what `claude` printed: auth method, version, and one run's outcome.

Field names follow 02a ([TS] SDKResultMessage, [HL], [SO]); see
tests/fixtures/cli/PROVENANCE.toml for which parts are documented vs assumed.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import jsonschema

RETRIES_SUBTYPE = "error_max_structured_output_retries"


@dataclass(frozen=True)
class Stop:
    """Why a batch stopped. reason: 'rate_limit' or 'billing'."""

    reason: str
    detail: str
    resets_at: Any = None  # as reported (assumed epoch seconds)
    key: tuple[str, str, int] | None = None


@dataclass(frozen=True)
class Outcome:
    structured_output: dict[str, Any] | None
    failure_reason: str | None
    model_usage_keys: tuple[str, ...]
    answer_models: tuple[str, ...]
    model_usage: dict[str, Any]
    usage: dict[str, Any]
    cost_usd: float | None
    init_model: str | None
    subtype: str | None
    session_id: str | None
    stop: Stop | None
    has_result: bool
    limits: dict[str, Any] | None = None  # plan utilization reported by this run (see _limits)
    launch_failed: bool = False  # claude never started (see _launch_failed): not a model result


def parse_auth_method(text: str) -> str | None:
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "authMethod" in data:
            return str(data["authMethod"])
    except json.JSONDecodeError:
        pass
    m = re.search(r"auth\s*method\W*([\w.\-]+)", text, re.IGNORECASE)
    return m.group(1) if m else None


def parse_version(text: str) -> str:
    m = re.search(r"\d+\.\d+\.\d+\S*", text)
    if not m:
        raise ValueError(f"cannot read a CLI version from {text!r}")
    return m.group(0)


def parse_messages(stdout: str) -> list[dict[str, Any]]:
    """A bare result object, a JSON array of messages, or JSON lines."""
    text = stdout.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        msgs = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                try:
                    msgs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return [m for m in msgs if isinstance(m, dict)]
    if isinstance(data, dict):
        return [data]
    return [m for m in data if isinstance(m, dict)] if isinstance(data, list) else []


def _stop_for(msg: dict[str, Any]) -> Stop | None:
    if msg.get("type") == "rate_limit_event":
        info = msg.get("rate_limit_info") or {}
        if info.get("errorCode") == "credits_required":
            return Stop("billing", "rate_limit_event errorCode credits_required", info.get("resetsAt"))
        if info.get("isUsingOverage"):
            return Stop("billing", "rate_limit_event isUsingOverage: this run drew on overage, not Pro limits",
                        info.get("resetsAt"))
        if info.get("status") == "rejected":
            return Stop("rate_limit", "rate_limit_event status rejected", info.get("resetsAt"))
    if msg.get("type") == "system" and msg.get("subtype") == "api_retry":
        err = msg.get("error")
        if err == "billing_error":
            return Stop("billing", "api_retry error billing_error")
        if err == "rate_limit":
            return Stop("rate_limit", "api_retry error rate_limit", msg.get("resets_at") or msg.get("resetsAt"))
    return None


def _limits(msgs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Last rate_limit_event's plan utilization (0..1) per window, plus the overage state."""
    event = next((m for m in reversed(msgs) if m.get("type") == "rate_limit_event"), None)
    if event is None:
        return None
    info = event.get("rate_limit_info") or {}
    windows = info.get("unifiedWindows") or {}
    return {
        "five_hour": (windows.get("five_hour") or {}).get("utilization"),
        "five_hour_resets_at": (windows.get("five_hour") or {}).get("resetsAt"),
        "seven_day": (windows.get("seven_day") or {}).get("utilization"),
        "seven_day_resets_at": (windows.get("seven_day") or {}).get("resetsAt"),
        "overage_status": info.get("overageStatus"),
        "is_using_overage": info.get("isUsingOverage"),
    }


# Windows NTSTATUS exit codes (0xC0000000 and up), e.g. 0xC0000142 STATUS_DLL_INIT_FAILED,
# recorded 2026-10-27 for 107 calls in one second: the process never ran, so no model answered.
_NTSTATUS_MIN = 0xC0000000


def _launch_failed(stdout: str, returncode: int, has_result: bool) -> bool:
    crashed = returncode >= _NTSTATUS_MIN or returncode < 0
    return not has_result and not stdout.strip() and crashed


def _tokens(d: dict[str, Any], *keys: str) -> int:
    return sum(int(d.get(k) or 0) for k in keys)


def answering_models(usage: dict[str, Any], model_usage: dict[str, Any]) -> tuple[str, ...]:
    """The modelUsage entries that wrote the main turn.

    Claude Code also bills small background calls (seen: claude-haiku-5-5, ~1.2k in / 14 out,
    no cache tokens) to modelUsage, so its keys alone cannot show a model switch. The main
    turn's cache tokens (top-level `usage`) are matched against each entry; without cache
    tokens, output tokens decide. No match = () so the run cannot be confirmed (fail closed).
    """
    main_cache = _tokens(usage, "cache_read_input_tokens", "cache_creation_input_tokens")
    if main_cache:
        match = [m for m, u in model_usage.items()
                 if _tokens(u, "cacheReadInputTokens", "cacheCreationInputTokens") == main_cache]
    else:
        out = int(usage.get("output_tokens") or 0)
        match = [m for m, u in model_usage.items() if out and int(u.get("outputTokens") or 0) == out]
    return tuple(sorted(match))


def interpret(stdout: str, schema: dict[str, Any], returncode: int = 0, stderr: str = "") -> Outcome:
    msgs = parse_messages(stdout)
    init = next((m for m in msgs if m.get("type") == "system" and m.get("subtype") == "init"), None)
    result = next((m for m in reversed(msgs) if m.get("type") == "result"), None)
    stops = [s for s in map(_stop_for, msgs) if s]
    # billing outranks rate limit: it is the one that could cost money
    stop = next((s for s in stops if s.reason == "billing"), stops[0] if stops else None)

    result = result or {}
    model_usage = result.get("modelUsage") or {}
    keys = tuple(model_usage.keys())
    structured = result.get("structured_output")
    subtype = result.get("subtype")
    failure = None
    if not result:
        failure = f"no result message (exit {returncode}): {stderr.strip()[:200]}"
    elif subtype == RETRIES_SUBTYPE:
        failure = f"{RETRIES_SUBTYPE}: {result.get('errors')}"
    elif result.get("is_error") or subtype != "success":
        failure = f"error result (subtype {subtype}): {str(result.get('result', ''))[:200]}"
    elif structured is None:
        failure = "structured_output missing (subtype success)"
    else:
        errors = sorted(jsonschema.Draft7Validator(schema).iter_errors(structured), key=lambda e: list(e.path))
        if errors:
            failure = "structured_output invalid: " + "; ".join(e.message for e in errors[:3])
    return Outcome(
        structured_output=None if failure else structured,
        failure_reason=failure,
        model_usage_keys=keys,
        answer_models=answering_models(result.get("usage") or {}, model_usage),
        model_usage=model_usage,
        usage=result.get("usage") or {},
        cost_usd=result.get("total_cost_usd"),
        init_model=(init or {}).get("model"),
        subtype=subtype,
        session_id=result.get("session_id") or (init or {}).get("session_id"),
        stop=stop,
        has_result=bool(result),
        limits=_limits(msgs),
        launch_failed=_launch_failed(stdout, returncode, bool(result)),
    )
