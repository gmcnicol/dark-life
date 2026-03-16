"""Sequential command executor for compiled render plans."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass

from shared.logging import log_debug

from .compiler.models import CommandSpec


@dataclass(frozen=True)
class CommandExecutionResult:
    label: str
    exit_code: int
    stdout: str
    stderr: str
    elapsed_ms: int


class CommandExecutionError(RuntimeError):
    def __init__(self, label: str, exit_code: int, stderr: str) -> None:
        self.label = label
        self.exit_code = exit_code
        self.stderr = stderr[:400]
        super().__init__(f"{label} failed with exit code {exit_code}")


class CommandTimeoutError(TimeoutError):
    def __init__(self, label: str, timeout_sec: float) -> None:
        self.label = label
        self.timeout_sec = timeout_sec
        super().__init__(f"{label} timed out after {timeout_sec:.1f}s")


def run_command(spec: CommandSpec, *, timeout_sec: float) -> CommandExecutionResult:
    argv = [spec.binary, *spec.args]
    log_debug("ffmpeg_cmd", label=spec.label, argv=argv)
    started = time.monotonic()
    process = subprocess.Popen(
        argv,
        cwd=spec.cwd,
        env={**os.environ, **(spec.env or {})},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_sec)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except Exception:
            process.kill()
        process.wait()
        raise CommandTimeoutError(spec.label, timeout_sec) from exc

    elapsed_ms = int((time.monotonic() - started) * 1000)
    if process.returncode != 0:
        raise CommandExecutionError(spec.label, process.returncode or 1, stderr or "")
    return CommandExecutionResult(
        label=spec.label,
        exit_code=process.returncode or 0,
        stdout=stdout or "",
        stderr=stderr or "",
        elapsed_ms=elapsed_ms,
    )


def run_commands(commands: list[CommandSpec], *, timeout_sec: int) -> list[CommandExecutionResult]:
    deadline = time.monotonic() + max(timeout_sec, 1)
    results: list[CommandExecutionResult] = []
    for spec in commands:
        remaining = max(deadline - time.monotonic(), 1.0)
        results.append(run_command(spec, timeout_sec=remaining))
    return results


__all__ = [
    "CommandExecutionError",
    "CommandExecutionResult",
    "CommandTimeoutError",
    "run_command",
    "run_commands",
]
