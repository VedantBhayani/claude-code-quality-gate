"""The one invocation interface every model call goes through.

An Invoker takes the argv after the executable name plus a working directory
and returns what the process printed. ClaudeCli is the only implementation that
starts a real `claude` process; tests use runner.fake.FakeInvoker with recorded
outputs instead.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Sequence


@dataclass(frozen=True)
class CliCall:
    returncode: int
    stdout: str
    stderr: str = ""


class Invoker(Protocol):
    def invoke(self, argv: Sequence[str], cwd: Path) -> CliCall: ...


# Env vars that would move calls off the Pro login (02a section 6): an API key or
# token bills the API instead; a base URL could route every call through a proxy.
_BILLING_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")

_NPM_EXE = Path("node_modules") / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"


class ClaudeNotFoundError(RuntimeError):
    """No usable `claude` executable."""


def resolve_claude_executable() -> str:
    """The `claude` binary the user's shell would run.

    QG_CLAUDE_BIN overrides. Otherwise the first `claude` on PATH; an npm .cmd shim is
    resolved to the claude.exe it launches, because CreateProcess skips .cmd files and
    would silently pick a different (possibly older) claude.exe further down PATH.
    """
    override = os.environ.get("QG_CLAUDE_BIN")
    if override:
        return override
    found = shutil.which("claude")
    if not found:
        raise ClaudeNotFoundError("`claude` not found on PATH; install Claude Code or set QG_CLAUDE_BIN")
    if Path(found).suffix.lower() in (".cmd", ".bat"):
        exe = Path(found).parent / _NPM_EXE
        if not exe.is_file():
            raise ClaudeNotFoundError(f"{found} is a shim whose claude.exe was not found at {exe}; "
                                      "set QG_CLAUDE_BIN to the claude.exe to use")
        return str(exe)
    return found


@dataclass(frozen=True)
class ClaudeCli:
    """Runs the real `claude` executable. argv is a list, never a shell string,
    so the inline --json-schema survives Windows quoting (02a section 3)."""

    executable: str = field(default_factory=resolve_claude_executable)
    timeout_s: float = 600.0

    def invoke(self, argv: Sequence[str], cwd: Path) -> CliCall:
        env = {k: v for k, v in os.environ.items() if k not in _BILLING_ENV}
        proc = subprocess.run(
            [self.executable, *argv],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.timeout_s,
            stdin=subprocess.DEVNULL,
        )
        return CliCall(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
