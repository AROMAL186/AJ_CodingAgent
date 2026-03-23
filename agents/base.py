"""Shared logic for LLM-backed agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.json_utils import extract_json_object
from core.llm import LLMClient


@dataclass(slots=True)
class BaseAgent:
    """Base class for agents that produce structured JSON output."""

    llm: LLMClient
    model: str

    def run_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        raw_response = self.llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=self.model,
        )
        return extract_json_object(raw_response)
