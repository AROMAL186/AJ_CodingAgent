"""Dependency installation utilities."""

from __future__ import annotations

from pathlib import Path

from core.models import CommandResult
from tools.shell_tool import ShellTool


class DependencyInstallerTool:
    """Installs Python packages using pip through the configured interpreter."""

    def __init__(self, python_executable: str, shell_tool: ShellTool) -> None:
        self.python_executable = python_executable
        self.shell_tool = shell_tool

    def install_python_packages(self, packages: list[str], cwd: Path) -> CommandResult:
        unique_packages = [package for package in dict.fromkeys(packages) if package]
        if not unique_packages:
            return CommandResult(
                command="",
                exit_code=0,
                stdout="No dependencies requested.",
                stderr="",
                duration_seconds=0.0,
            )
        command = f"{self.python_executable} -m pip install " + " ".join(unique_packages)
        return self.shell_tool.run_command(command, cwd=cwd)
