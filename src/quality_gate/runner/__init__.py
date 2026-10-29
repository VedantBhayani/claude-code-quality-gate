"""Runner: one `claude -p` call per (post, arm, repeat), behind one invocation interface.

Production code passes ClaudeCli() as the invoker; tests pass FakeInvoker with
recorded outputs from tests/fixtures/cli/. Nothing else starts `claude`.
"""
from quality_gate.runner.batch import (
    AuthMethodError,
    BatchResult,
    ResumeTooEarlyError,
    RunJob,
    run_batch,
    signal_jobs,
)
from quality_gate.runner.command import CLI_DEFAULT_EFFORT, RunSettings, build_command, inline_schema
from quality_gate.runner.fake import FakeInvoker
from quality_gate.runner.invoker import ClaudeCli, CliCall, Invoker
from quality_gate.runner.output import Stop
from quality_gate.runner.prompts import DRAFT_OUTPUT_SCHEMA, draft_prompt, read_offer_wording, signal_prompt
from quality_gate.runner.runlog import LoggedRun, RunLog, read_run_log

__all__ = [
    "AuthMethodError", "BatchResult", "CLI_DEFAULT_EFFORT", "ClaudeCli", "CliCall", "DRAFT_OUTPUT_SCHEMA",
    "FakeInvoker", "Invoker", "LoggedRun", "ResumeTooEarlyError", "RunJob", "RunLog", "RunSettings", "Stop",
    "build_command", "draft_prompt", "inline_schema", "read_offer_wording", "read_run_log", "run_batch",
    "signal_jobs", "signal_prompt",
]
