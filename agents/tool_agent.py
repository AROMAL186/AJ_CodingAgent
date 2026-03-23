"""Dedicated tool execution agent."""

from __future__ import annotations

import json
from typing import Any

from core.tool_executor import ToolExecutor


class ToolAgent:
    """Receives tool requests and delegates them to the tool executor."""

    def __init__(self, executor: ToolExecutor) -> None:
        self.executor = executor

    def handle(self, request: dict[str, Any] | str) -> dict[str, Any]:
        if isinstance(request, str):
            try:
                request = json.loads(request)
            except json.JSONDecodeError as exc:
                return self._error(f"Invalid JSON tool request: {exc}")

        if not isinstance(request, dict):
            return self._error("Tool request must be a JSON object.")

        normalized = {
            "name": request.get("name", request.get("tool")),
            "description": request.get("description", request.get("intent")),
            "arguments": request.get("arguments", {}),
        }
        return self.executor.execute(normalized)

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        return {"status": "error", "output": None, "error": message}
