"""Prompt builders for planner, coder, and debugger agents."""

from __future__ import annotations

from dataclasses import asdict
import json

from core.models import ExecutionResult, ExecutionTask


def _json_schema_block(example: dict) -> str:
    return json.dumps(example, indent=2)


def planner_system_prompt() -> str:
    return """You are the Planner Agent in an autonomous software engineering system.
Break a high-level software goal into ordered tasks that can be executed by the AJ coding agent.
Return JSON only. Do not wrap the JSON in markdown.
Every task must include at least one concrete validation command that can be run in a shell.
Be specific, implementation-aware, and production-minded."""


def planner_user_prompt(
    goal: str,
    workspace_snapshot: str,
    memory_context: str,
    tool_catalog_text: str = "",
    complexity_guidance: str = "",
) -> str:
    schema = {
        "summary": "One paragraph summary of the execution strategy.",
        "assumptions": ["List of assumptions"],
        "tasks": [
            {
                "id": "task-1",
                "title": "Short task title",
                "description": "Detailed task description",
                "deliverables": ["Files or outcomes expected from this task"],
                "validation_commands": ["Commands to verify this task"],
                "done_definition": "What success means for the task",
            }
        ],
    }
    return (
        f"Goal:\n{goal}\n\n"
        f"Complexity guidance:\n{complexity_guidance or 'No special complexity guidance.'}\n\n"
        f"Available tool skills:\n{tool_catalog_text or 'No tool skills provided.'}\n\n"
        f"Workspace snapshot:\n{workspace_snapshot}\n\n"
        f"Relevant memory:\n{memory_context}\n\n"
        "Return a plan that is ordered, minimal, and executable.\n"
        f"JSON schema:\n{_json_schema_block(schema)}"
    )


def coder_system_prompt() -> str:
    return """You are the Coder Agent in an autonomous software engineering system.
Produce production-quality code and execution steps for exactly one task.
Return JSON only. Do not wrap the JSON in markdown.
Rules:
- Prefer modular Python code with explicit error handling.
- Plan folders intentionally and include any required directories.
- Use full file contents for every file creation or overwrite.
- Include dependencies only when necessary.
- Always include commands that validate the result."""


def coder_user_prompt(
    goal: str,
    task: ExecutionTask,
    workspace_snapshot: str,
    memory_context: str,
    tool_catalog_text: str = "",
    complexity_guidance: str = "",
) -> str:
    schema = {
        "summary": "Short explanation of the implementation approach.",
        "dependencies": ["PyYAML==6.0.2"],
        "directories": [{"path": "src/api"}],
        "file_changes": [
            {
                "path": "relative/path/to/file.py",
                "action": "create",
                "content": "full file content here",
            }
        ],
        "commands": ["python3 -m compileall ."],
        "validation_commands": ["pytest -q"],
        "notes": ["Optional implementation notes"],
    }
    return (
        f"Goal:\n{goal}\n\n"
        f"Complexity guidance:\n{complexity_guidance or 'No special complexity guidance.'}\n\n"
        f"Available tool skills:\n{tool_catalog_text or 'No tool skills provided.'}\n\n"
        f"Task:\n{json.dumps(asdict(task), indent=2)}\n\n"
        f"Workspace snapshot:\n{workspace_snapshot}\n\n"
        f"Relevant memory:\n{memory_context}\n\n"
        "Produce the implementation batch for this task only.\n"
        f"JSON schema:\n{_json_schema_block(schema)}"
    )


def debugger_system_prompt() -> str:
    return """You are the Debugger Agent in an autonomous software engineering system.
Analyze failed execution output, repair the code, and produce the next corrective work batch.
Return JSON only. Do not wrap the JSON in markdown.
Focus on root causes, not superficial edits.
Always include commands to re-run the failing validation path."""


def debugger_user_prompt(
    goal: str,
    task: ExecutionTask,
    workspace_snapshot: str,
    memory_context: str,
    failed_result: ExecutionResult,
    previous_summary: str,
    tool_catalog_text: str = "",
    complexity_guidance: str = "",
) -> str:
    schema = {
        "summary": "Short explanation of the diagnosed root cause and fix.",
        "dependencies": [],
        "directories": [{"path": "src/api"}],
        "file_changes": [
            {
                "path": "relative/path/to/file.py",
                "action": "overwrite",
                "content": "full corrected file content here",
            }
        ],
        "commands": ["python3 path/to/script.py"],
        "validation_commands": ["pytest -q"],
        "notes": ["Optional notes about why the previous attempt failed"],
    }
    return (
        f"Goal:\n{goal}\n\n"
        f"Complexity guidance:\n{complexity_guidance or 'No special complexity guidance.'}\n\n"
        f"Available tool skills:\n{tool_catalog_text or 'No tool skills provided.'}\n\n"
        f"Task:\n{json.dumps(asdict(task), indent=2)}\n\n"
        f"Previous work summary:\n{previous_summary}\n\n"
        f"Workspace snapshot:\n{workspace_snapshot}\n\n"
        f"Relevant memory:\n{memory_context}\n\n"
        f"Execution failure summary:\n{failed_result.to_summary()}\n\n"
        "Generate a corrective work batch.\n"
        f"JSON schema:\n{_json_schema_block(schema)}"
    )
