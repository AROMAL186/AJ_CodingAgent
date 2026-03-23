"""Executor layer for applying work plans and validating results."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agents.tool_agent import ToolAgent
from core.config import ExecutionSettings
from core.models import CommandResult, ExecutionResult, WorkPlan


@dataclass(slots=True)
class ExecutorLayer:
    """Applies file changes, installs dependencies, and runs commands."""

    tool_agent: ToolAgent
    workspace_root: Path
    settings: ExecutionSettings

    def execute(self, work_plan: WorkPlan) -> ExecutionResult:
        try:
            directory_plan = _auto_directory_plan(
                changes=work_plan.file_changes,
                explicit_directories=work_plan.directories,
            )
            ensured_directories = self._create_directories(directory_plan)
            changed_files = self._apply_file_changes(work_plan)
        except Exception as exc:
            return ExecutionResult(
                success=False,
                changed_files=[],
                dependency_results=[],
                command_results=[],
                failure_reason=f"Failed to apply file changes: {exc}",
            )

        dependency_results: list[CommandResult] = []
        if work_plan.dependencies:
            if not self.settings.allow_dependency_install:
                return ExecutionResult(
                    success=False,
                    changed_files=[*ensured_directories, *changed_files],
                    dependency_results=[],
                    command_results=[],
                    failure_reason="Dependencies requested but installation is disabled.",
                )
            dependency_response = self.tool_agent.handle(
                {
                    "description": (
                        "Install Python packages when validation needs missing dependencies."
                    ),
                    "arguments": {"packages": work_plan.dependencies},
                }
            )
            if dependency_response["status"] != "success":
                return ExecutionResult(
                    success=False,
                    changed_files=[*ensured_directories, *changed_files],
                    dependency_results=[],
                    command_results=[],
                    failure_reason=dependency_response["error"],
                )
            dependency_result = _command_result_from_tool_response(dependency_response)
            dependency_results.append(dependency_result)
            if dependency_result.exit_code != 0:
                return ExecutionResult(
                    success=False,
                    changed_files=[*ensured_directories, *changed_files],
                    dependency_results=dependency_results,
                    command_results=[],
                    failure_reason="Dependency installation failed.",
                )

        commands = _ordered_unique([*work_plan.commands, *work_plan.validation_commands])
        if not commands:
            return ExecutionResult(
                success=False,
                changed_files=[*ensured_directories, *changed_files],
                dependency_results=dependency_results,
                command_results=[],
                failure_reason="Work plan did not include any commands to execute.",
            )

        command_results: list[CommandResult] = []
        for command in commands:
            response = self.tool_agent.handle(
                {
                    "description": "Execute a validation command safely inside the workspace.",
                    "arguments": {"command": command},
                }
            )
            if response["status"] != "success":
                return ExecutionResult(
                    success=False,
                    changed_files=[*ensured_directories, *changed_files],
                    dependency_results=dependency_results,
                    command_results=command_results,
                    failure_reason=response["error"],
                )
            result = _command_result_from_tool_response(response)
            command_results.append(result)
            if result.exit_code != 0:
                return ExecutionResult(
                    success=False,
                    changed_files=[*ensured_directories, *changed_files],
                    dependency_results=dependency_results,
                    command_results=command_results,
                    failure_reason=f"Command failed: {command}",
                )

        return ExecutionResult(
            success=True,
            changed_files=[*ensured_directories, *changed_files],
            dependency_results=dependency_results,
            command_results=command_results,
        )

    def _create_directories(self, directory_paths: list[str]) -> list[str]:
        ensured: list[str] = []
        for path in directory_paths:
            result = self.tool_agent.handle(
                {
                    "description": (
                        "Create a directory in the workspace before files are written into it."
                    ),
                    "arguments": {"path": path},
                }
            )
            if result["status"] != "success":
                raise RuntimeError(result["error"])
            ensured.append(path)
        return list(dict.fromkeys(ensured))

    def _apply_file_changes(self, work_plan: WorkPlan) -> list[str]:
        changed_files: list[str] = []
        for change in work_plan.file_changes:
            request = {
                "description": _tool_description_for_file_change(change.action),
                "arguments": {"path": change.path},
            }
            if change.action in {"create", "overwrite", "append"}:
                request["arguments"]["content"] = change.content
            result = self.tool_agent.handle(request)
            if result["status"] != "success":
                raise RuntimeError(result["error"])
            changed_files.append(change.path)
        return changed_files


def _ordered_unique(items: list[str]) -> list[str]:
    cleaned = [item.strip() for item in items if item and item.strip()]
    return list(dict.fromkeys(cleaned))


def _auto_directory_plan(changes, explicit_directories) -> list[str]:
    planned_paths = [directory.path for directory in explicit_directories]
    for change in changes:
        parent = Path(change.path).parent
        if str(parent) not in {"", "."}:
            planned_paths.append(str(parent))
    return [path for path in dict.fromkeys(planned_paths) if path and path != "."]


def _command_result_from_tool_response(response: dict) -> CommandResult:
    payload = response.get("output")
    if not isinstance(payload, dict):
        raise RuntimeError("Execution tool did not return a command result payload.")
    return CommandResult(
        command=str(payload.get("command", "")),
        exit_code=int(payload.get("exit_code", 1)),
        stdout=str(payload.get("stdout", "")),
        stderr=str(payload.get("stderr", "")),
        duration_seconds=float(payload.get("duration_seconds", 0.0)),
    )


def _tool_description_for_file_change(action: str) -> str:
    mapping = {
        "create": "Write or overwrite a file when creating new source files with full contents.",
        "overwrite": "Write or overwrite a file when replacing an existing file with new contents.",
        "append": "Append text to an existing file when adding incremental content.",
        "delete": "Delete a file or directory when generated output must be removed.",
    }
    if action not in mapping:
        raise ValueError(f"Unsupported file action: {action}")
    return mapping[action]
