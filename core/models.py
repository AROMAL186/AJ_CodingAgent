"""Shared dataclasses used across the agent system."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


@dataclass(slots=True)
class ExecutionTask:
    id: str
    title: str
    description: str
    deliverables: list[str] = field(default_factory=list)
    validation_commands: list[str] = field(default_factory=list)
    done_definition: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionTask":
        return cls(
            id=str(data.get("id", "")).strip(),
            title=str(data.get("title", "")).strip(),
            description=str(data.get("description", "")).strip(),
            deliverables=[str(item) for item in data.get("deliverables", [])],
            validation_commands=[str(item) for item in data.get("validation_commands", [])],
            done_definition=str(data.get("done_definition", "")).strip(),
        )


@dataclass(slots=True)
class ExecutionPlan:
    goal: str
    summary: str
    assumptions: list[str]
    tasks: list[ExecutionTask]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DirectoryChange:
    path: str

    @classmethod
    def from_dict(cls, data: dict[str, Any] | str) -> "DirectoryChange":
        if isinstance(data, str):
            path = data
        else:
            path = str(data.get("path", "")).strip()
        normalized = str(path).strip()
        if not normalized:
            raise ValueError("Directory path cannot be empty.")
        return cls(path=normalized)


@dataclass(slots=True)
class FileChange:
    path: str
    action: str
    content: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileChange":
        action = str(data.get("action", "overwrite")).strip().lower()
        if action not in {"create", "overwrite", "append", "delete"}:
            raise ValueError(f"Unsupported file action: {action}")
        return cls(
            path=str(data.get("path", "")).strip(),
            action=action,
            content=str(data.get("content", "")),
        )


@dataclass(slots=True)
class WorkPlan:
    summary: str
    dependencies: list[str] = field(default_factory=list)
    directories: list[DirectoryChange] = field(default_factory=list)
    file_changes: list[FileChange] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    validation_commands: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        fallback_validation_commands: list[str] | None = None,
    ) -> "WorkPlan":
        validation_commands = [str(item) for item in data.get("validation_commands", [])]
        if not validation_commands and fallback_validation_commands:
            validation_commands = list(fallback_validation_commands)

        return cls(
            summary=str(data.get("summary", "")).strip(),
            dependencies=sorted({str(item).strip() for item in data.get("dependencies", []) if str(item).strip()}),
            directories=[DirectoryChange.from_dict(item) for item in data.get("directories", [])],
            file_changes=[FileChange.from_dict(item) for item in data.get("file_changes", [])],
            commands=[str(item) for item in data.get("commands", [])],
            validation_commands=validation_commands,
            notes=[str(item) for item in data.get("notes", [])],
        )


@dataclass(slots=True)
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float


@dataclass(slots=True)
class ExecutionResult:
    success: bool
    changed_files: list[str]
    dependency_results: list[CommandResult]
    command_results: list[CommandResult]
    failure_reason: str = ""

    def to_summary(self) -> str:
        lines = [f"success={self.success}"]
        if self.failure_reason:
            lines.append(f"failure_reason={self.failure_reason}")
        for result in [*self.dependency_results, *self.command_results]:
            lines.append(
                f"command={result.command!r} exit_code={result.exit_code} "
                f"stdout={result.stdout[-400:]} stderr={result.stderr[-400:]}"
            )
        return "\n".join(lines)


@dataclass(slots=True)
class MemoryEntry:
    timestamp: str
    kind: str
    goal: str
    task_id: str
    status: str
    summary: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RunSummary:
    goal: str
    workspace_root: str
    plan: ExecutionPlan
    task_results: list[dict[str, Any]]
    completed_at: str = field(default_factory=utc_now)
