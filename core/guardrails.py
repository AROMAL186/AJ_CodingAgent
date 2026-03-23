"""Guardrail-style validation for plans, work plans, and commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from core.models import ExecutionPlan, WorkPlan


_DANGEROUS_COMMAND_PATTERNS = (
    re.compile(r"(^|[;&|])\s*sudo\b"),
    re.compile(r"(^|[;&|])\s*rm\s+-rf\s+(/|~|--no-preserve-root\b)"),
    re.compile(r"(^|[;&|])\s*mkfs(\.\w+)?\b"),
    re.compile(r"(^|[;&|])\s*shutdown\b"),
    re.compile(r"(^|[;&|])\s*reboot\b"),
    re.compile(r"(^|[;&|])\s*poweroff\b"),
    re.compile(r"(^|[;&|])\s*halt\b"),
)


@dataclass(slots=True)
class PlanGuardrails:
    """Validates planner output before the execution loop starts."""

    def validate(self, plan: ExecutionPlan) -> ExecutionPlan:
        if not plan.summary.strip():
            raise ValueError("Planner returned an empty summary.")
        if not plan.tasks:
            raise ValueError("Planner returned no executable tasks.")

        seen_ids: set[str] = set()
        for task in plan.tasks:
            if not task.id.strip():
                raise ValueError("Every task must include a non-empty id.")
            if task.id in seen_ids:
                raise ValueError(f"Duplicate task id returned by planner: {task.id}")
            if not task.title.strip():
                raise ValueError(f"Task '{task.id}' is missing a title.")
            if not task.description.strip():
                raise ValueError(f"Task '{task.id}' is missing a description.")
            if not task.validation_commands:
                raise ValueError(f"Task '{task.id}' must include at least one validation command.")
            for command in task.validation_commands:
                _validate_command(command, context=f"task '{task.id}' validation command")
            seen_ids.add(task.id)
        return plan


@dataclass(slots=True)
class WorkPlanGuardrails:
    """Validates coder/debugger output before it reaches the executor."""

    def validate(self, work_plan: WorkPlan) -> WorkPlan:
        if not work_plan.summary.strip():
            raise ValueError("Work plan summary cannot be empty.")

        for directory in work_plan.directories:
            _validate_relative_path(directory.path, context="directory path")

        for change in work_plan.file_changes:
            _validate_relative_path(change.path, context="file change path")

        all_commands = [*work_plan.commands, *work_plan.validation_commands]
        if not all_commands:
            raise ValueError("Work plan must include commands or validation commands.")

        for command in all_commands:
            _validate_command(command, context="work plan command")

        return work_plan


def _validate_relative_path(path: str, context: str) -> None:
    candidate = Path(path)
    if not str(candidate).strip():
        raise ValueError(f"{context} cannot be empty.")
    if candidate.is_absolute():
        raise ValueError(f"{context} cannot be absolute: {path}")
    if ".." in candidate.parts:
        raise ValueError(f"{context} escapes the workspace: {path}")


def _validate_command(command: str, context: str) -> None:
    normalized = str(command).strip()
    if not normalized:
        raise ValueError(f"{context} cannot be empty.")
    if "\n" in normalized or "\r" in normalized or "\x00" in normalized:
        raise ValueError(f"{context} contains unsupported control characters.")
    for pattern in _DANGEROUS_COMMAND_PATTERNS:
        if pattern.search(normalized):
            raise ValueError(f"{context} contains a blocked shell pattern: {normalized}")
