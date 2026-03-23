"""Testing and validation agent for autonomous coding workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from core.models import CommandResult
from tools.executor import ProjectExecutor


_MISSING_MODULE_RE = re.compile(
    r"(?:ModuleNotFoundError|ImportError): .*?(?:No module named|named) ['\"]([^'\"]+)['\"]"
)
_SYNTAX_MARKERS = ("SyntaxError", "IndentationError", "TabError")
_LOGICAL_FAILURE_MARKERS = ("AssertionError", "FAILED", "Expected", "Traceback")


@dataclass(slots=True)
class TestingFeedback:
    """Structured feedback emitted for downstream agents."""

    status: str
    error_type: str
    message: str
    suggestion: str
    next_action: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(slots=True)
class TestingAgent:
    """Executes code, analyzes failures, and returns structured feedback."""

    __test__ = False

    executor: ProjectExecutor

    def run_python_file(self, path: str) -> dict[str, str]:
        result = self.executor.run_python_file(path)
        return self._build_feedback(result, target=f"Python file '{path}'").to_dict()

    def run_command(self, command: str) -> dict[str, str]:
        result = self.executor.run_command(command)
        return self._build_feedback(result, target=f"command '{command}'").to_dict()

    def install_dependencies(self, packages: list[str]) -> CommandResult:
        return self.executor.install_dependencies(packages)

    def validate(self, *, path: str | None = None, command: str | None = None) -> dict[str, str]:
        if bool(path) == bool(command):
            raise ValueError("Provide exactly one of 'path' or 'command'.")
        if path is not None:
            return self.run_python_file(path)
        return self.run_command(command or "")

    def execute_with_details(
        self,
        *,
        path: str | None = None,
        command: str | None = None,
    ) -> dict[str, Any]:
        if bool(path) == bool(command):
            raise ValueError("Provide exactly one of 'path' or 'command'.")

        if path is not None:
            result = self.executor.run_python_file(path)
            target = f"Python file '{path}'"
        else:
            result = self.executor.run_command(command or "")
            target = f"command '{command}'"

        feedback = self._build_feedback(result, target=target)
        return {
            "feedback": feedback.to_dict(),
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "duration_seconds": result.duration_seconds,
            "command": result.command,
        }

    def _build_feedback(self, result: CommandResult, target: str) -> TestingFeedback:
        combined_output = "\n".join(part for part in (result.stderr, result.stdout) if part).strip()
        missing_modules = self._extract_missing_modules(combined_output)

        if result.exit_code == 0 and not self._looks_like_logical_failure(combined_output):
            return TestingFeedback(
                status="success",
                error_type="none",
                message=f"{target} executed successfully.",
                suggestion="No action needed.",
                next_action="complete",
            )

        if missing_modules:
            packages = " ".join(missing_modules)
            return TestingFeedback(
                status="fail",
                error_type="dependency_error",
                message=f"Missing dependency detected while executing {target}: {', '.join(missing_modules)}.",
                suggestion=f"Install the missing package(s) with `python3 -m pip install {packages}` and rerun validation.",
                next_action="install_dependency",
            )

        if any(marker in combined_output for marker in _SYNTAX_MARKERS):
            return TestingFeedback(
                status="fail",
                error_type="syntax_error",
                message=f"Syntax validation failed for {target}.",
                suggestion="Fix the reported syntax issue near the referenced file and line, then rerun the test.",
                next_action="fix_code",
            )

        if result.exit_code == 124:
            return TestingFeedback(
                status="fail",
                error_type="runtime_error",
                message=f"{target} timed out after {self.executor.timeout_seconds} seconds.",
                suggestion="Check for infinite loops, blocking I/O, or raise the timeout only if the workload is expected.",
                next_action="fix_code",
            )

        if "Blocked dangerous shell command" in result.stderr:
            return TestingFeedback(
                status="fail",
                error_type="runtime_error",
                message=f"Execution was blocked for safety while running {target}.",
                suggestion="Replace the command with a project-safe validation command that does not use restricted operations.",
                next_action="fix_code",
            )

        if self._looks_like_logical_failure(combined_output):
            return TestingFeedback(
                status="fail",
                error_type="runtime_error",
                message=f"Execution finished but validation failed for {target}.",
                suggestion="Inspect the assertion or failing test output and update the implementation to satisfy the expected behavior.",
                next_action="fix_code",
            )

        return TestingFeedback(
            status="fail",
            error_type="runtime_error",
            message=f"{target} exited with code {result.exit_code}.",
            suggestion="Review stderr/stdout, fix the code or command, and retry validation.",
            next_action="retry",
        )

    @staticmethod
    def _extract_missing_modules(output: str) -> list[str]:
        modules = [match.strip() for match in _MISSING_MODULE_RE.findall(output) if match.strip()]
        return list(dict.fromkeys(modules))

    @staticmethod
    def _looks_like_logical_failure(output: str) -> bool:
        return any(marker in output for marker in _LOGICAL_FAILURE_MARKERS)
