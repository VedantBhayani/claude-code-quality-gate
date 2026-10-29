"""The run log: one JSON line per completed run (success or failed) or batch stop.

A completed (post, arm, repeat) key is never run again, which is how a re-run
resumes. Stop lines carry resets_at so a resume can wait for the reset. Each
line is flushed as soon as it is known, so a crash loses at most the call in flight.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from quality_gate.runner.output import Stop
from quality_gate.types import RunRecord

Key = tuple[str, str, int]


@dataclass(frozen=True)
class LoggedRun:
    record: RunRecord
    init_model: str | None
    subtype: str | None
    session_id: str | None
    recorded_at: str
    limits: dict[str, Any] | None = None  # plan utilization after this run (runner.output._limits)


@dataclass
class RunLog:
    runs: list[LoggedRun] = field(default_factory=list)
    stops: list[Stop] = field(default_factory=list)

    def completed_keys(self) -> set[Key]:
        return {(r.record.post_id, r.record.arm, r.record.repeat) for r in self.runs}

    @property
    def records(self) -> list[RunRecord]:
        return [r.record for r in self.runs]


def _record_from(d: dict[str, Any]) -> RunRecord:
    d = dict(d)
    d["model_usage_keys"] = tuple(d["model_usage_keys"])
    if d.get("answer_models") is not None:
        d["answer_models"] = tuple(d["answer_models"])
    return RunRecord(**d)


def read_run_log(path: Path) -> RunLog:
    log = RunLog()
    path = Path(path)
    if not path.exists():
        return log
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry["kind"] == "run":
            log.runs.append(LoggedRun(_record_from(entry["record"]), entry.get("init_model"), entry.get("subtype"),
                                      entry.get("session_id"), entry["recorded_at"], entry.get("limits")))
        elif entry["kind"] == "stop":
            key = tuple(entry["key"]) if entry.get("key") else None
            log.stops.append(Stop(entry["reason"], entry["detail"], entry.get("resets_at"), key))
    return log


def _append(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
        f.flush()


def append_run(path: Path, run: LoggedRun) -> None:
    entry = {"kind": "run", "record": asdict(run.record), "init_model": run.init_model, "subtype": run.subtype,
             "session_id": run.session_id, "recorded_at": run.recorded_at, "limits": run.limits}
    _append(Path(path), entry)


def append_stop(path: Path, stop: Stop, recorded_at: str) -> None:
    entry = {"kind": "stop", "reason": stop.reason, "detail": stop.detail, "resets_at": stop.resets_at,
             "key": list(stop.key) if stop.key else None, "recorded_at": recorded_at}
    _append(Path(path), entry)
