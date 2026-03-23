"""Project-scoped execution helpers for validation and testing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shlex
import subprocess
import time

from core.models import CommandResult


_INVALID_COMMAND_SNIPPETS = ("\x00", "\n", "\r")
_DANGEROUS_COMMAND_PATTERNS = (
    re.compile(r"(^|[;&|])\s*sudo\b"),
    re.compile(r"(^|[;&|])\s*rm\s+-rf\s+(/|~|--no-preserve-root\b)"),
    re.compile(r"(^|[;&|])\s*mkfs(\.\w+)?\b"),
    re.compile(r"(^|[;&|])\s*dd\b"),
    re.compile(r"(^|[;&|])\s*shutdown\b"),
    re.compile(r"(^|[;&|])\s*reboot\b"),
    re.compile(r"(^|[;&|])\s*poweroff\b"),
    re.compile(r"(^|[;&|])\s*halt\b"),
    re.compile(r"(^|[;&|])\s*killall\b"),
    re.compile(r"(^|[;&|])\s*kill\s+-9\s+1\b"),
    re.compile(r"(^|[;&|])\s*curl\b.*\|\s*(sh|bash|zsh)\b"),
    re.compile(r"(^|[;&|])\s*wget\b.*\|\s*(sh|bash|zsh)\b"),
)
_UNSAFE_PACKAGE_PATTERN = re.compile(r"[;&|`$><\s]")


@dataclass(slots=True)
class ProjectExecutor:
    """Runs commands within a project root with timeout and safety checks."""

    root: Path
    shell: str
    timeout_seconds: int
    python_executable: str = "python3"

    def __post_init__(self) -> None:
        self.root = self.root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def run_python_file(self, path: str) -> CommandResult:
        command = f"{shlex.quote(self.python_executable)} {shlex.quote(path)}"
        try:
            target = self._resolve_project_path(path)
        except ValueError as exc:
            return self._error_result(command, str(exc))

        if not target.exists() or not target.is_file():
            return self._error_result(command, f"Python file does not exist: {path}")

        relative_path = target.relative_to(self.root)
        safe_command = f"{shlex.quote(self.python_executable)} {shlex.quote(str(relative_path))}"
        return self._run_subprocess(safe_command)

    def run_command(self, command: str) -> CommandResult:
        try:
            normalized = self._validate_command(command)
        except ValueError as exc:
            return self._error_result(command, str(exc))
        return self._run_subprocess(normalized)

    def install_dependencies(self, packages: list[str]) -> CommandResult:
        unique_packages = [package for package in dict.fromkeys(packages) if str(package).strip()]
        if not unique_packages:
            return CommandResult(
                command="",
                exit_code=0,
                stdout="No dependencies requested.",
                stderr="",
                duration_seconds=0.0,
            )

        cleaned_packages: list[str] = []
        for raw_package in unique_packages:
            package = str(raw_package).strip()
            if _UNSAFE_PACKAGE_PATTERN.search(package):
                return self._error_result(
                    f"{self.python_executable} -m pip install {package}",
                    f"Unsafe package specification rejected: {package}",
                )
            cleaned_packages.append(package)

        command = f"{shlex.quote(self.python_executable)} -m pip install " + " ".join(
            shlex.quote(package) for package in cleaned_packages
        )
        return self._run_subprocess(command)

    def _resolve_project_path(self, path: str) -> Path:
        candidate = Path(str(path).strip())
        if not str(candidate):
            raise ValueError("Execution path cannot be empty.")
        if candidate.is_absolute():
            raise ValueError("Absolute execution paths are not allowed.")

        target = (self.root / candidate).resolve()
        if self.root not in target.parents and target != self.root:
            raise ValueError(f"Execution path escapes project root: {path}")
        return target

    def _validate_command(self, command: str) -> str:
        normalized = str(command).strip()
        if not normalized:
            raise ValueError("Command cannot be empty.")
        if any(snippet in normalized for snippet in _INVALID_COMMAND_SNIPPETS):
            raise ValueError("Command contains unsupported control characters.")
        for pattern in _DANGEROUS_COMMAND_PATTERNS:
            if pattern.search(normalized):
                raise ValueError(f"Blocked dangerous shell command: {normalized}")
        return normalized

    def _run_subprocess(self, command: str) -> CommandResult:
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                cwd=str(self.root),
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
        except OSError as exc:
            duration = time.perf_counter() - started
            return self._error_result(command, f"Execution failed: {exc}", duration)
        except Exception as exc:
            duration = time.perf_counter() - started
            return self._error_result(command, f"Unexpected execution error: {exc}", duration)

    @staticmethod
    def _error_result(command: str, message: str, duration_seconds: float = 0.0) -> CommandResult:
        return CommandResult(
            command=command,
            exit_code=1,
            stdout="",
            stderr=message,
            duration_seconds=duration_seconds,
        )
