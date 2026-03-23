"""Skill-based tool registry with metadata-driven selection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from typing import Any, Callable
import inspect
import re

from core.models import CommandResult
from tools.dependency_tool import DependencyInstallerTool
from tools.file_manager import FileManager
from tools.python_tool import PythonTool
from tools.shell_tool import ShellTool


ToolFn = Callable[..., dict[str, Any]]
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "inside",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "use",
    "when",
    "with",
}
_TOKEN_RE = re.compile(r"[a-zA-Z0-9_./-]+")


@dataclass(slots=True)
class ToolSkill:
    """Self-describing tool skill with metadata and execution handler."""

    name: str
    description: str
    inputs: dict[str, str]
    execute: ToolFn

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("execute", None)
        return payload


class ToolRegistry:
    """Extensible registry of skill-like tools with relevance-based selection."""

    def __init__(self, tools: list[ToolSkill] | None = None) -> None:
        self._tools: dict[str, ToolSkill] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: ToolSkill) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolSkill | None:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return sorted(self._tools)

    def catalog(self) -> list[dict[str, Any]]:
        return [self._tools[name].to_dict() for name in self.names()]

    def select(self, description: str, arguments: dict[str, Any] | None = None) -> ToolSkill | None:
        query = str(description).strip()
        if not query:
            return None

        best_tool: ToolSkill | None = None
        best_score = float("-inf")
        for tool in self._tools.values():
            score = self._score(tool, query, arguments or {})
            if score > best_score:
                best_tool = tool
                best_score = score

        if best_tool is None or best_score <= 0:
            return None
        return best_tool

    def validate_arguments(self, tool: ToolSkill, arguments: dict[str, Any]) -> str | None:
        if not isinstance(arguments, dict):
            return "Tool request 'arguments' must be an object."

        try:
            inspect.signature(tool.execute).bind(**arguments)
        except TypeError as exc:
            return f"Invalid tool arguments: {exc}"

        for key, expected_type in tool.inputs.items():
            if key not in arguments:
                continue
            if not _matches_schema_type(arguments[key], expected_type):
                actual_type = type(arguments[key]).__name__
                return (
                    f"Invalid input for '{key}': expected {expected_type}, got {actual_type}."
                )
        return None

    def _score(self, tool: ToolSkill, description: str, arguments: dict[str, Any]) -> float:
        query_text = " ".join(filter(None, [description, _stringify_arguments(arguments)])).lower()
        searchable = " ".join(
            [
                tool.name,
                tool.description,
                " ".join(tool.inputs.keys()),
                " ".join(tool.inputs.values()),
            ]
        ).lower()
        query_tokens = set(_tokenize(query_text))
        tool_tokens = set(_tokenize(searchable))
        overlap = len(query_tokens & tool_tokens)
        exact_name_bonus = 6.0 if tool.name.lower() in query_text else 0.0
        schema_bonus = _score_schema_fit(tool, arguments)
        fuzzy_bonus = SequenceMatcher(None, query_text, searchable).ratio()
        return exact_name_bonus + (overlap * 2.0) + schema_bonus + fuzzy_bonus


def build_default_tool_registry(
    file_manager: FileManager,
    shell_tool: ShellTool,
    python_tool: PythonTool,
    dependency_tool: DependencyInstallerTool,
) -> ToolRegistry:
    return ToolRegistry(
        tools=[
            ToolSkill(
                name="read_file",
                description="Read a file from the workspace. Use when inspecting existing code or configuration.",
                inputs={"path": "string"},
                execute=file_manager.read_file,
            ),
            ToolSkill(
                name="write_file",
                description="Write or overwrite a file. Use when creating or updating code files with full contents.",
                inputs={"path": "string", "content": "string"},
                execute=file_manager.write_file,
            ),
            ToolSkill(
                name="append_file",
                description="Append text to an existing file. Use when adding logs, notes, or incremental content.",
                inputs={"path": "string", "content": "string"},
                execute=file_manager.append_file,
            ),
            ToolSkill(
                name="delete_file",
                description="Delete a file or directory. Use when removing obsolete generated artifacts.",
                inputs={"path": "string"},
                execute=file_manager.delete_file,
            ),
            ToolSkill(
                name="create_dir",
                description="Create a directory in the workspace. Use before writing files into a new folder.",
                inputs={"path": "string"},
                execute=file_manager.create_dir,
            ),
            ToolSkill(
                name="move",
                description="Move or rename a file or directory. Use when reorganizing generated project structure.",
                inputs={"src": "string", "dest": "string"},
                execute=file_manager.move,
            ),
            ToolSkill(
                name="list_files",
                description="List files or directories in the workspace. Use when exploring project contents.",
                inputs={"path": "string"},
                execute=file_manager.list_files,
            ),
            ToolSkill(
                name="run_python_command",
                description="Run a Python command or script in the workspace. Use for python validation commands and script execution.",
                inputs={"command": "string"},
                execute=lambda command: _command_success(python_tool.run_command(command, cwd=file_manager.root)),
            ),
            ToolSkill(
                name="run_shell_command",
                description="Run a shell command in the workspace. Use for grep, test, ls, or mixed shell validation commands.",
                inputs={"command": "string"},
                execute=lambda command: _command_success(shell_tool.run_command(command, cwd=file_manager.root)),
            ),
            ToolSkill(
                name="install_python_packages",
                description="Install Python packages with pip. Use when code needs missing dependencies before validation can pass.",
                inputs={"packages": "array"},
                execute=lambda packages: _command_success(
                    dependency_tool.install_python_packages(packages, cwd=file_manager.root)
                ),
            ),
        ]
    )


def build_file_tool_registry(file_manager: FileManager) -> ToolRegistry:
    shell_tool = ShellTool(shell="/bin/zsh", timeout_seconds=600)
    python_tool = PythonTool(python_executable="python3", shell_tool=shell_tool)
    dependency_tool = DependencyInstallerTool(
        python_executable="python3",
        shell_tool=shell_tool,
    )
    return build_default_tool_registry(
        file_manager=file_manager,
        shell_tool=shell_tool,
        python_tool=python_tool,
        dependency_tool=dependency_tool,
    )


def _command_success(result: CommandResult) -> dict[str, Any]:
    return {"status": "success", "output": asdict(result), "error": None}


def _matches_schema_type(value: Any, expected_type: str) -> bool:
    normalized = expected_type.strip().lower()
    if normalized == "string":
        return isinstance(value, str)
    if normalized == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if normalized == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if normalized == "boolean":
        return isinstance(value, bool)
    if normalized == "array":
        return isinstance(value, list)
    if normalized == "object":
        return isinstance(value, dict)
    return True


def _score_schema_fit(tool: ToolSkill, arguments: dict[str, Any]) -> float:
    if not arguments:
        return 0.0
    provided = set(arguments)
    expected = set(tool.inputs)
    overlap = len(provided & expected)
    mismatch = len(provided - expected)
    return float(overlap) - (0.5 * mismatch)


def _stringify_arguments(arguments: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key, value in arguments.items():
        if isinstance(value, list):
            chunks.append(f"{key} {' '.join(str(item) for item in value)}")
        else:
            chunks.append(f"{key} {value}")
    return " ".join(chunks)


def _tokenize(text: str) -> list[str]:
    tokens = [token.lower() for token in _TOKEN_RE.findall(text)]
    return [token for token in tokens if token not in _STOPWORDS]
