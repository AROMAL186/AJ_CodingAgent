"""Debugger agent that diagnoses failed attempts and proposes fixes."""

from __future__ import annotations

from dataclasses import dataclass

from agents.base import BaseAgent
from core.guardrails import WorkPlanGuardrails
from core.models import ExecutionResult, ExecutionTask, WorkPlan
from core.prompts import debugger_system_prompt, debugger_user_prompt


@dataclass(slots=True)
class DebuggerAgent(BaseAgent):
    """Repairs failed work plans by incorporating execution feedback."""

    def create_fix_plan(
        self,
        goal: str,
        task: ExecutionTask,
        workspace_snapshot: str,
        memory_context: str,
        failed_result: ExecutionResult,
        previous_summary: str,
        tool_catalog_text: str = "",
        complexity_guidance: str = "",
    ) -> WorkPlan:
        payload = self.run_json(
            system_prompt=debugger_system_prompt(),
            user_prompt=debugger_user_prompt(
                goal=goal,
                task=task,
                workspace_snapshot=workspace_snapshot,
                memory_context=memory_context,
                failed_result=failed_result,
                previous_summary=previous_summary,
                tool_catalog_text=tool_catalog_text,
                complexity_guidance=complexity_guidance,
            ),
        )
        work_plan = WorkPlan.from_dict(payload, fallback_validation_commands=task.validation_commands)
        return WorkPlanGuardrails().validate(work_plan)
