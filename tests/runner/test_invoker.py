"""ClaudeCli: which `claude` binary runs, and which env vars never reach it.

This machine has two installs: an npm shim (claude.cmd -> node_modules/.../claude.exe)
first on PATH, and an older native claude.exe later on PATH. CreateProcess("claude")
skips the .cmd and picks the native one, so the runner must resolve the shim itself
and run the same binary the user's shell runs. No real `claude` is started here.
"""
import sys
from pathlib import Path

import pytest

from quality_gate.runner import invoker as inv


def _npm_shim(root: Path) -> Path:
    exe = root / "npm" / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    shim = root / "npm" / "claude.cmd"
    shim.write_text('"%dp0%\\node_modules\\@anthropic-ai\\claude-code\\bin\\claude.exe" %*\n', encoding="utf-8")
    return shim


def test_an_explicit_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("QG_CLAUDE_BIN", str(tmp_path / "my-claude.exe"))
    monkeypatch.setattr(inv.shutil, "which", lambda name: pytest.fail("PATH must not be searched"))
    assert inv.resolve_claude_executable() == str(tmp_path / "my-claude.exe")


def test_an_npm_cmd_shim_resolves_to_the_exe_it_launches(monkeypatch, tmp_path):
    monkeypatch.delenv("QG_CLAUDE_BIN", raising=False)
    shim = _npm_shim(tmp_path)
    monkeypatch.setattr(inv.shutil, "which", lambda name: str(shim))
    expected = tmp_path / "npm" / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    assert inv.resolve_claude_executable() == str(expected)


def test_a_cmd_shim_without_the_package_exe_is_refused(monkeypatch, tmp_path):
    monkeypatch.delenv("QG_CLAUDE_BIN", raising=False)
    shim = tmp_path / "claude.cmd"
    shim.write_text("@echo off\n", encoding="utf-8")
    monkeypatch.setattr(inv.shutil, "which", lambda name: str(shim))
    with pytest.raises(inv.ClaudeNotFoundError, match="QG_CLAUDE_BIN"):
        inv.resolve_claude_executable()


def test_a_plain_executable_on_path_is_used_as_is(monkeypatch, tmp_path):
    monkeypatch.delenv("QG_CLAUDE_BIN", raising=False)
    exe = tmp_path / "claude.exe"
    monkeypatch.setattr(inv.shutil, "which", lambda name: str(exe))
    assert inv.resolve_claude_executable() == str(exe)


def test_no_claude_on_path_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("QG_CLAUDE_BIN", raising=False)
    monkeypatch.setattr(inv.shutil, "which", lambda name: None)
    with pytest.raises(inv.ClaudeNotFoundError, match="not found on PATH"):
        inv.resolve_claude_executable()


def test_env_that_could_move_calls_off_the_pro_login_is_removed(monkeypatch, tmp_path):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["env"] = cmd, kw["env"]

        class P:
            returncode, stdout, stderr = 0, "", ""
        return P()

    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"):
        monkeypatch.setenv(k, "x")
    monkeypatch.setenv("KEEP_ME", "1")
    monkeypatch.setattr(inv.subprocess, "run", fake_run)
    inv.ClaudeCli(executable=sys.executable).invoke(["--version"], cwd=tmp_path)
    assert seen["cmd"] == [sys.executable, "--version"]
    assert not {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"} & set(seen["env"])
    assert seen["env"]["KEEP_ME"] == "1"
