from __future__ import annotations

from pathlib import Path
import builtins
import sys
import types

import pytest

from core.config import AppConfig, ExecutionSettings, GuardrailsSettings, LLMSettings, MemorySettings, OrchestrationSettings
from core.guardrails_runtime import NeMoGuardrailsChatClient, build_chat_client


class FakeRailsConfig:
    last_path: str | None = None

    @classmethod
    def from_path(cls, path: str):
        cls.last_path = path
        return {"path": path}


class FakeLLMRails:
    def __init__(self, config):
        self.config = config

    def generate(self, messages):
        return {"role": "assistant", "content": f"guarded:{messages[-1]['content']}"}


def make_app_config(tmp_path: Path, enabled: bool = True) -> AppConfig:
    guardrails_dir = tmp_path / "guardrails"
    guardrails_dir.mkdir(parents=True, exist_ok=True)
    (guardrails_dir / "config.yml").write_text("models: []\n", encoding="utf-8")
    return AppConfig(
        llm=LLMSettings(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key_env="NVIDIA_API_KEY",
            model="meta/llama-3.1-405b-instruct",
            temperature=0.2,
            top_p=0.9,
            max_tokens=1024,
            timeout_seconds=30,
        ),
        execution=ExecutionSettings(
            shell="/bin/zsh",
            command_timeout_seconds=30,
            python_executable="python3",
            allow_dependency_install=True,
        ),
        orchestration=OrchestrationSettings(
            workspace_root=tmp_path / "workspace",
            max_task_retries=2,
            max_files_in_snapshot=20,
            max_chars_per_file=2000,
        ),
        memory=MemorySettings(
            path=tmp_path / "memory.jsonl",
            max_recent_entries=5,
        ),
        guardrails=GuardrailsSettings(
            enabled=enabled,
            provider="nemo",
            config_path=guardrails_dir,
            fail_closed=True,
        ),
    )


def test_build_chat_client_returns_nemo_client_when_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.SimpleNamespace(LLMRails=FakeLLMRails, RailsConfig=FakeRailsConfig)
    monkeypatch.setitem(sys.modules, "nemoguardrails", fake_module)

    client = build_chat_client(make_app_config(tmp_path, enabled=True))

    assert isinstance(client, NeMoGuardrailsChatClient)
    response = client.chat(messages=[{"role": "user", "content": "hello"}])
    assert response == "guarded:hello"
    assert FakeRailsConfig.last_path is not None


def test_nemo_client_raises_clear_error_when_package_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "nemoguardrails":
            raise ImportError("missing")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.delitem(sys.modules, "nemoguardrails", raising=False)

    with pytest.raises(RuntimeError, match="nemoguardrails"):
        NeMoGuardrailsChatClient(
            llm_settings=make_app_config(tmp_path).llm,
            guardrails_settings=make_app_config(tmp_path).guardrails,
        )
