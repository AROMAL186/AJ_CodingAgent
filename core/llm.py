"""Reusable NVIDIA NIM LLM client."""

from __future__ import annotations

import os
from typing import Any

import requests

from core.config import LLMSettings


class LLMClient:
    """Thin wrapper around the NVIDIA-hosted OpenAI-compatible chat API."""

    def __init__(self, settings: LLMSettings, session: requests.Session | None = None) -> None:
        self.settings = settings
        self.session = session or requests.Session()

    def _api_key(self) -> str:
        value = os.getenv(self.settings.api_key_env, "").strip()
        if not value:
            raise RuntimeError(
                f"Missing API key. Export {self.settings.api_key_env} before running the agent."
            )
        return value

    def _endpoint(self) -> str:
        return f"{self.settings.base_url.rstrip('/')}/chat/completions"

    def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        payload = {
            "model": model or self.settings.model,
            "messages": messages,
            "temperature": self.settings.temperature if temperature is None else temperature,
            "top_p": self.settings.top_p,
            "max_tokens": self.settings.max_tokens if max_tokens is None else max_tokens,
        }
        response = self.session.post(
            self._endpoint(),
            headers={
                "Authorization": f"Bearer {self._api_key()}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.settings.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        return self._extract_content(data)

    @staticmethod
    def _extract_content(data: dict[str, Any]) -> str:
        choices = data.get("choices")
        if not choices:
            raise RuntimeError(f"NVIDIA NIM response did not include choices: {data}")

        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
            return "\n".join(part for part in text_parts if part)
        raise RuntimeError(f"Unsupported content format returned by NVIDIA NIM: {content!r}")
