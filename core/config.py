"""Configuration loading and normalization."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any
import os

import yaml


@dataclass(slots=True)
class LLMSettings:
    base_url: str
    api_key_env: str
    model: str
    temperature: float
    top_p: float
    max_tokens: int
    timeout_seconds: int


@dataclass(slots=True)
class ExecutionSettings:
    shell: str
    command_timeout_seconds: int
    python_executable: str
    allow_dependency_install: bool


@dataclass(slots=True)
class OrchestrationSettings:
    workspace_root: Path
    max_task_retries: int
    max_files_in_snapshot: int
    max_chars_per_file: int


@dataclass(slots=True)
class MemorySettings:
    path: Path
    max_recent_entries: int


@dataclass(slots=True)
class GuardrailsSettings:
    enabled: bool = False
    provider: str = "nemo"
    config_path: Path | None = None
    fail_closed: bool = True


@dataclass(slots=True)
class AppConfig:
    llm: LLMSettings
    execution: ExecutionSettings
    orchestration: OrchestrationSettings
    memory: MemorySettings
    guardrails: GuardrailsSettings = field(default_factory=GuardrailsSettings)

    def with_workspace(self, workspace_root: Path) -> "AppConfig":
        return replace(
            self,
            orchestration=replace(self.orchestration, workspace_root=workspace_root.resolve()),
        )


def _resolve_path(value: str, base_dir: Path) -> Path:
    expanded = Path(os.path.expandvars(os.path.expanduser(value)))
    if expanded.is_absolute():
        return expanded
    return (base_dir / expanded).resolve()


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")
    return loaded


def load_env_file(path: str | Path) -> None:
    env_path = Path(path).expanduser().resolve()
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).expanduser().resolve()
    raw = _read_yaml(config_path)
    base_dir = config_path.parent

    llm = raw.get("llm", {})
    execution = raw.get("execution", {})
    orchestration = raw.get("orchestration", {})
    memory = raw.get("memory", {})
    guardrails = raw.get("guardrails", {})

    return AppConfig(
        llm=LLMSettings(
            base_url=str(llm.get("base_url", "https://integrate.api.nvidia.com/v1")).rstrip("/"),
            api_key_env=str(llm.get("api_key_env", "NVIDIA_API_KEY")),
            model=str(llm.get("model", "meta/llama-3.3-70b-instruct")),
            temperature=float(llm.get("temperature", 0.2)),
            top_p=float(llm.get("top_p", 0.9)),
            max_tokens=int(llm.get("max_tokens", 4096)),
            timeout_seconds=int(llm.get("timeout_seconds", 180)),
        ),
        execution=ExecutionSettings(
            shell=str(execution.get("shell", "/bin/zsh")),
            command_timeout_seconds=int(execution.get("command_timeout_seconds", 600)),
            python_executable=str(execution.get("python_executable", "python3")),
            allow_dependency_install=bool(execution.get("allow_dependency_install", True)),
        ),
        orchestration=OrchestrationSettings(
            workspace_root=_resolve_path(
                str(orchestration.get("workspace_root", "./generated_workspace")),
                base_dir,
            ),
            max_task_retries=int(orchestration.get("max_task_retries", 3)),
            max_files_in_snapshot=int(orchestration.get("max_files_in_snapshot", 60)),
            max_chars_per_file=int(orchestration.get("max_chars_per_file", 5000)),
        ),
        memory=MemorySettings(
            path=_resolve_path(str(memory.get("path", "./memory/agent_memory.jsonl")), base_dir),
            max_recent_entries=int(memory.get("max_recent_entries", 12)),
        ),
        guardrails=GuardrailsSettings(
            enabled=bool(guardrails.get("enabled", False)),
            provider=str(guardrails.get("provider", "nemo")).strip().lower(),
            config_path=(
                _resolve_path(str(guardrails.get("config_path")), base_dir)
                if guardrails.get("config_path")
                else None
            ),
            fail_closed=bool(guardrails.get("fail_closed", True)),
        ),
    )
