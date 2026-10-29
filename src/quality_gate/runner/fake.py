"""FakeInvoker: replays recorded `claude` outputs (tests/fixtures/cli/) in order.

It answers `auth status` and `--version` from fixed text and each `-p` call with
the next recorded output, and keeps what each `-p` call saw (argv, the working
directory's contents, the files its arguments point at) for assertions.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from quality_gate.runner.invoker import CliCall


@dataclass(frozen=True)
class SeenCall:
    argv: tuple[str, ...]
    cwd: str
    cwd_listing: list[str]
    files: dict[str, str]  # path -> text, for every argv element that names an existing file


@dataclass
class FakeInvoker:
    auth_status: str
    version: str
    runs: list[str | CliCall] = field(default_factory=list)  # a CliCall replays a non-zero exit too
    run_calls: list[SeenCall] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._queue = list(self.runs)
        self._lock = threading.Lock()

    def invoke(self, argv: Sequence[str], cwd: Path) -> CliCall:
        argv = list(argv)
        if argv[:2] == ["auth", "status"]:
            return CliCall(0, self.auth_status)
        if argv in (["--version"], ["-v"]):
            return CliCall(0, self.version)
        if argv[:1] != ["-p"]:
            raise AssertionError(f"FakeInvoker: unexpected argv {argv!r}")
        files = {a: Path(a).read_text(encoding="utf-8") for a in argv if len(a) < 260 and _is_file(a)}
        seen = SeenCall(tuple(argv), str(cwd), sorted(p.name for p in Path(cwd).iterdir()), files)
        with self._lock:
            self.run_calls.append(seen)
            if not self._queue:
                raise AssertionError("FakeInvoker: no recorded output left for this -p call")
            out = self._queue.pop(0)
        return out if isinstance(out, CliCall) else CliCall(0, out)


def _is_file(arg: str) -> bool:
    try:
        return Path(arg).is_file()
    except (OSError, ValueError):
        return False
