"""Runtime integration for NVIDIA NeMo Guardrails."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.config import AppConfig, GuardrailsSettings, LLMSettings
from core.llm import LLMClient


def build_chat_client(config: AppConfig) -> Any:
    if not config.guardrails.enabled:
        return LLMClient(config.llm)

    if config.guardrails.provider != "nemo":
        raise ValueError(f"Unsupported guardrails provider: {config.guardrails.provider}")

    return NeMoGuardrailsChatClient(
        llm_settings=config.llm,
        guardrails_settings=config.guardrails,
    )


@dataclass(slots=True)
class NeMoGuardrailsChatClient:
    """OpenAI-style chat client backed by NVIDIA NeMo Guardrails."""

    llm_settings: LLMSettings
    guardrails_settings: GuardrailsSettings
    _rails: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.guardrails_settings.config_path is None:
            raise RuntimeError("NeMo Guardrails is enabled but no config_path was provided.")
        self._rails = self._build_rails(self.guardrails_settings.config_path)

    def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        _ = model, temperature, max_tokens
        try:
            response = self._rails.generate(messages=messages)
            return _extract_guardrails_content(response)
        except Exception:
            if self.guardrails_settings.fail_closed:
                raise
            fallback_client = LLMClient(self.llm_settings)
            return fallback_client.chat(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

    @staticmethod
    def _build_rails(config_path: Path) -> Any:
        if not config_path.exists():
            raise RuntimeError(f"NeMo Guardrails config path does not exist: {config_path}")

        try:
            from nemoguardrails import LLMRails, RailsConfig
        except ImportError as exc:
            raise RuntimeError(
                "NeMo Guardrails is enabled but the 'nemoguardrails' package is not installed. "
                "Install it with: pip install \"nemoguardrails[nvidia]\""
            ) from exc

        config = RailsConfig.from_path(str(config_path))
        return LLMRails(config)


def _extract_guardrails_content(response: Any) -> str:
    if isinstance(response, str):
        return response

    if isinstance(response, dict):
        content = response.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [str(item) for item in content if item]
            if text_parts:
                return "\n".join(text_parts)

    if isinstance(response, list):
        for item in reversed(response):
            if isinstance(item, dict) and item.get("role") == "assistant":
                content = item.get("content")
                if isinstance(content, str):
                    return content

    raise RuntimeError(f"Unsupported NeMo Guardrails response format: {response!r}")
