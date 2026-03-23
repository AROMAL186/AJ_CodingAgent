"""CLI entry point for the AJ coding agent."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from agents.coder import CoderAgent
from agents.debugger import DebuggerAgent
from agents.planner import PlannerAgent
from agents.tool_agent import ToolAgent
from core.config import AppConfig, load_config, load_env_file
from core.executor import ExecutorLayer
from core.models import RunSummary
from core.llm import LLMClient
from core.orchestrator import AutonomousCodingOrchestrator
from core.tool_executor import ToolExecutor
from memory.store import MemoryStore
from tools.dependency_tool import DependencyInstallerTool
from tools.file_manager import FileManager
from tools.python_tool import PythonTool
from tools.registry import build_default_tool_registry
from tools.shell_tool import ShellTool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AJ coding agent.")
    parser.add_argument("goal", help="High-level software instruction to execute.")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the YAML configuration file.",
    )
    parser.add_argument(
        "--workspace",
        help="Optional workspace override where generated code should be created.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full structured JSON result to stdout instead of the concise summary.",
    )
    return parser.parse_args()


def build_orchestrator(config: AppConfig) -> AutonomousCodingOrchestrator:
    llm_client = LLMClient(config.llm)
    shell_tool = ShellTool(
        shell=config.execution.shell,
        timeout_seconds=config.execution.command_timeout_seconds,
    )
    python_tool = PythonTool(
        python_executable=config.execution.python_executable,
        shell_tool=shell_tool,
    )
    dependency_tool = DependencyInstallerTool(
        python_executable=config.execution.python_executable,
        shell_tool=shell_tool,
    )
    file_manager = FileManager(config.orchestration.workspace_root)
    tool_executor = ToolExecutor(
        build_default_tool_registry(
            file_manager=file_manager,
            shell_tool=shell_tool,
            python_tool=python_tool,
            dependency_tool=dependency_tool,
        )
    )
    tool_agent = ToolAgent(tool_executor)
    memory_store = MemoryStore(config.memory.path)
    executor = ExecutorLayer(
        tool_agent=tool_agent,
        workspace_root=file_manager.root,
        settings=config.execution,
    )
    planner = PlannerAgent(llm=llm_client, model=config.llm.model)
    coder = CoderAgent(llm=llm_client, model=config.llm.model)
    debugger = DebuggerAgent(llm=llm_client, model=config.llm.model)
    return AutonomousCodingOrchestrator(
        config=config,
        planner=planner,
        coder=coder,
        debugger=debugger,
        executor=executor,
        memory_store=memory_store,
        file_manager=file_manager,
    )


def write_run_log(summary: RunSummary) -> Path:
    workspace_root = Path(summary.workspace_root)
    log_dir = workspace_root / ".agent_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    safe_timestamp = summary.completed_at.replace(":", "-")
    log_path = log_dir / f"run-{safe_timestamp}.json"
    payload = json.dumps(asdict(summary), indent=2, ensure_ascii=True)
    log_path.write_text(payload + "\n", encoding="utf-8")
    (log_dir / "latest.json").write_text(payload + "\n", encoding="utf-8")
    return log_path


def format_run_summary(summary: RunSummary, log_path: Path) -> str:
    unique_files = sorted(
        {
            path
            for task_result in summary.task_results
            for path in task_result.get("changed_files", [])
        }
    )

    lines = [
        "Run completed successfully.",
        f"Goal: {summary.goal}",
        f"Workspace: {summary.workspace_root}",
        f"Tasks completed: {len(summary.task_results)}",
    ]

    for index, task_result in enumerate(summary.task_results, start=1):
        title = task_result.get("title", "Untitled task")
        attempts = task_result.get("attempts", 0)
        lines.append(f"{index}. {title} (attempts: {attempts})")

    if unique_files:
        lines.append(f"Files changed: {', '.join(unique_files)}")

    lines.append(f"Detailed log: {log_path}")
    lines.append(f"Completed at: {summary.completed_at}")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    load_env_file(".env")
    config = load_config(args.config)
    if args.workspace:
        config = config.with_workspace(Path(args.workspace))

    orchestrator = build_orchestrator(config)
    summary = orchestrator.run(args.goal)
    log_path = write_run_log(summary)

    if args.json:
        print(json.dumps(asdict(summary), indent=2))
        return

    print(format_run_summary(summary, log_path))


if __name__ == "__main__":
    main()
