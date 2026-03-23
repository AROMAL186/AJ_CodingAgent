"""Python-specific execution helpers."""

from __future__ import annotations

from pathlib import Path
import re

from core.models import CommandResult
from tools.shell_tool import ShellTool


PYTHON_PREFIX_RE = re.compile(r"^(python|python3)\b")


class PythonTool:
    """Normalizes Python invocations to the configured interpreter."""

    def __init__(self, python_executable: str, shell_tool: ShellTool) -> None:
        self.python_executable = python_executable
        self.shell_tool = shell_tool

    def can_run(self, command: str) -> bool:
        return bool(PYTHON_PREFIX_RE.match(command.strip()))

    def run_command(self, command: str, cwd: Path) -> CommandResult:
        normalized = PYTHON_PREFIX_RE.sub(self.python_executable, command.strip(), count=1)
        return self.shell_tool.run_command(normalized, cwd=cwd)
