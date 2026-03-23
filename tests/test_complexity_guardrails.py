from __future__ import annotations

import pytest

from core.complexity import analyze_goal_complexity
from core.guardrails import PlanGuardrails, WorkPlanGuardrails
from core.models import ExecutionPlan, ExecutionTask, FileChange, WorkPlan


def test_complexity_analysis_marks_large_multi_agent_goal_as_high() -> None:
    profile = analyze_goal_complexity(
        goal=(
            "Build a production autonomous multi-agent orchestrator with memory, "
            "validation, testing, observability, retries, and database integration."
        ),
        workspace_snapshot="Workspace files:\n- app/main.py\n- tests/test_app.py\n",
    )

    assert profile.level == "high"
    assert profile.score >= 6
    assert "high:agent" in profile.signals


def test_plan_guardrails_require_validation_commands() -> None:
    plan = ExecutionPlan(
        goal="Create a file",
        summary="Create a file.",
        assumptions=[],
        tasks=[
            ExecutionTask(
                id="task-1",
                title="Create file",
                description="Write the file.",
                validation_commands=[],
            )
        ],
    )

    with pytest.raises(ValueError, match="validation command"):
        PlanGuardrails().validate(plan)


def test_work_plan_guardrails_reject_absolute_paths() -> None:
    work_plan = WorkPlan(
        summary="Write a file.",
        file_changes=[FileChange(path="/tmp/escape.py", action="create", content="print('x')\n")],
        validation_commands=["python3 app.py"],
    )

    with pytest.raises(ValueError, match="cannot be absolute"):
        WorkPlanGuardrails().validate(work_plan)
