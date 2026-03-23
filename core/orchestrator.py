"""Top-level orchestration for the autonomous coding loop."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from agents.coder import CoderAgent
from agents.debugger import DebuggerAgent
from agents.planner import PlannerAgent
from core.complexity import analyze_goal_complexity
from core.config import AppConfig
from core.executor import ExecutorLayer
from core.models import MemoryEntry, RunSummary, utc_now
from memory.store import MemoryStore
from tools.file_manager import FileManager


@dataclass(slots=True)
class AutonomousCodingOrchestrator:
    """Coordinates planning, coding, execution, debugging, and retries."""

    config: AppConfig
    planner: PlannerAgent
    coder: CoderAgent
    debugger: DebuggerAgent
    executor: ExecutorLayer
    memory_store: MemoryStore
    file_manager: FileManager

    def run(self, goal: str) -> RunSummary:
        initial_snapshot = self.file_manager.build_snapshot(
            max_files=self.config.orchestration.max_files_in_snapshot,
            max_chars_per_file=self.config.orchestration.max_chars_per_file,
        )
        tool_catalog_text = _render_tool_catalog(self.executor.tool_agent.executor.registry.catalog())
        complexity = analyze_goal_complexity(goal=goal, workspace_snapshot=initial_snapshot)
        plan = self.planner.create_plan(
            goal=goal,
            workspace_snapshot=initial_snapshot,
            memory_context=self.memory_store.render_context(
                goal=goal,
                limit=self.config.memory.max_recent_entries,
            ),
            tool_catalog_text=tool_catalog_text,
            complexity_guidance=complexity.guidance,
        )
        self.memory_store.append(
            MemoryEntry(
                timestamp=utc_now(),
                kind="plan",
                goal=goal,
                task_id="plan",
                status="created",
                summary=plan.summary,
                details={**plan.to_dict(), "complexity": asdict(complexity)},
            )
        )

        task_results: list[dict] = []
        for task in plan.tasks:
            previous_summary = ""
            failed_result = None

            for attempt in range(1, self.config.orchestration.max_task_retries + 1):
                snapshot = self.file_manager.build_snapshot(
                    max_files=self.config.orchestration.max_files_in_snapshot,
                    max_chars_per_file=self.config.orchestration.max_chars_per_file,
                )
                memory_context = self.memory_store.render_context(
                    goal=goal,
                    limit=self.config.memory.max_recent_entries,
                )
                if attempt == 1:
                    work_plan = self.coder.create_work_plan(
                        goal=goal,
                        task=task,
                        workspace_snapshot=snapshot,
                        memory_context=memory_context,
                        tool_catalog_text=tool_catalog_text,
                        complexity_guidance=complexity.guidance,
                    )
                    phase = "code"
                else:
                    if failed_result is None:
                        raise RuntimeError("Retry path reached without a failed execution result.")
                    work_plan = self.debugger.create_fix_plan(
                        goal=goal,
                        task=task,
                        workspace_snapshot=snapshot,
                        memory_context=memory_context,
                        failed_result=failed_result,
                        previous_summary=previous_summary,
                        tool_catalog_text=tool_catalog_text,
                        complexity_guidance=complexity.guidance,
                    )
                    phase = "debug"

                execution_result = self.executor.execute(work_plan)
                self.memory_store.append(
                    MemoryEntry(
                        timestamp=utc_now(),
                        kind="attempt",
                        goal=goal,
                        task_id=task.id,
                        status="success" if execution_result.success else "failure",
                        summary=work_plan.summary,
                        details={
                            "phase": phase,
                            "attempt": attempt,
                            "task": asdict(task),
                            "work_plan": asdict(work_plan),
                            "execution_result": asdict(execution_result),
                        },
                    )
                )

                previous_summary = work_plan.summary
                if execution_result.success:
                    task_results.append(
                        {
                            "task_id": task.id,
                            "title": task.title,
                            "attempts": attempt,
                            "changed_files": execution_result.changed_files,
                            "commands": [result.command for result in execution_result.command_results],
                        }
                    )
                    break

                failed_result = execution_result
            else:
                raise RuntimeError(
                    f"Task '{task.title}' failed after "
                    f"{self.config.orchestration.max_task_retries} attempts."
                )

        return RunSummary(
            goal=goal,
            workspace_root=str(self.file_manager.root),
            plan=plan,
            task_results=task_results,
        )


def _render_tool_catalog(tool_catalog: list[dict]) -> str:
    if not tool_catalog:
        return "No tool skills available."

    lines: list[str] = []
    for item in tool_catalog:
        inputs = ", ".join(f"{key}: {value}" for key, value in item.get("inputs", {}).items())
        lines.append(
            f"- {item.get('name', 'unknown')}: {item.get('description', '').strip()} "
            f"Inputs: {inputs or 'none'}"
        )
    return "\n".join(lines)
