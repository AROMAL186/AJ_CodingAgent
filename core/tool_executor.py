"""Validated execution of JSON tool calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tools.registry import ToolRegistry


@dataclass(slots=True)
class ToolExecutor:
    """Safely validates and dispatches tool invocations."""

    registry: ToolRegistry

    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            if not isinstance(request, dict):
                return self._error("Tool request must be a JSON object.")

            name = request.get("name")
            description = request.get("description", request.get("intent"))
            arguments = request.get("arguments", {})
            if not isinstance(arguments, dict):
                return self._error("Tool request 'arguments' must be an object.")
            if isinstance(name, str) and name.strip():
                tool = self.registry.get(name.strip())
                if tool is None:
                    return self._error(f"Unknown tool: {name}")
            else:
                if not isinstance(description, str) or not description.strip():
                    return self._error(
                        "Tool request must include a non-empty 'name' or 'description'."
                    )
                tool = self.registry.select(description=description, arguments=arguments)
                if tool is None:
                    return self._error(
                        f"No matching tool found for description: {description}"
                    )

            if tool is None:
                return self._error("Tool is not registered.")

            validation_error = self.registry.validate_arguments(tool, arguments)
            if validation_error:
                return self._error(validation_error)

            result = tool.execute(**arguments)
            if not isinstance(result, dict):
                return self._error("Tool execution failed: tool must return a result object.")
            return {**result, "selected_tool": tool.name}
        except Exception as exc:
            return self._error(f"Tool execution failed: {exc}")

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        return {"status": "error", "output": None, "error": message}
