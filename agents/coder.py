"""Coder agent that produces implementation batches."""

from __future__ import annotations

from dataclasses import dataclass

from agents.base import BaseAgent
from core.guardrails import WorkPlanGuardrails
from core.models import ExecutionTask, WorkPlan
from core.prompts import coder_system_prompt, coder_user_prompt


@dataclass(slots=True)
class CoderAgent(BaseAgent):
    """Generates code, file changes, dependencies, and execution commands."""

    def create_work_plan(
        self,
        goal: str,
        task: ExecutionTask,
        workspace_snapshot: str,
        memory_context: str,
        tool_catalog_text: str = "",
        complexity_guidance: str = "",
    ) -> WorkPlan:
        payload = self.run_json(
            system_prompt=coder_system_prompt(),
            user_prompt=coder_user_prompt(
                goal=goal,
                task=task,
                workspace_snapshot=workspace_snapshot,
                memory_context=memory_context,
                tool_catalog_text=tool_catalog_text,
                complexity_guidance=complexity_guidance,
            ),
        )
        work_plan = WorkPlan.from_dict(payload, fallback_validation_commands=task.validation_commands)
        return WorkPlanGuardrails().validate(work_plan)
