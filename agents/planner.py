"""Planner agent that turns a goal into ordered execution tasks."""

from __future__ import annotations

from dataclasses import dataclass

from agents.base import BaseAgent
from core.guardrails import PlanGuardrails
from core.models import ExecutionPlan, ExecutionTask
from core.prompts import planner_system_prompt, planner_user_prompt


@dataclass(slots=True)
class PlannerAgent(BaseAgent):
    """Builds an ordered project plan from a high-level goal."""

    def create_plan(
        self,
        goal: str,
        workspace_snapshot: str,
        memory_context: str,
        tool_catalog_text: str = "",
        complexity_guidance: str = "",
    ) -> ExecutionPlan:
        payload = self.run_json(
            system_prompt=planner_system_prompt(),
            user_prompt=planner_user_prompt(
                goal=goal,
                workspace_snapshot=workspace_snapshot,
                memory_context=memory_context,
                tool_catalog_text=tool_catalog_text,
                complexity_guidance=complexity_guidance,
            ),
        )
        tasks = [ExecutionTask.from_dict(item) for item in payload.get("tasks", [])]
        if not tasks:
            raise ValueError("Planner returned no executable tasks.")
        plan = ExecutionPlan(
            goal=goal,
            summary=payload.get("summary", "").strip(),
            assumptions=list(payload.get("assumptions", [])),
            tasks=tasks,
        )
        return PlanGuardrails().validate(plan)
