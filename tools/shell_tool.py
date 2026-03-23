"""Shell command execution with structured results."""

from __future__ import annotations

from pathlib import Path
import subprocess
import time

from core.models import CommandResult


class ShellTool:
    """Executes shell commands inside a working directory."""

    def __init__(self, shell: str, timeout_seconds: int) -> None:
        self.shell = shell
        self.timeout_seconds = timeout_seconds

    def run_command(self, command: str, cwd: Path) -> CommandResult:
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                shell=True,
                executable=self.shell,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            duration = time.perf_counter() - started
            return CommandResult(
                command=command,
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.perf_counter() - started
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            return CommandResult(
                command=command,
                exit_code=124,
                stdout=stdout,
                stderr=stderr or f"Command timed out after {self.timeout_seconds} seconds.",
                duration_seconds=duration,
            )
