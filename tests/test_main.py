from __future__ import annotations

from pathlib import Path

from core.models import ExecutionPlan, ExecutionTask, RunSummary
from main import format_run_summary, write_run_log


def make_run_summary(tmp_path: Path) -> RunSummary:
    return RunSummary(
        goal="Create hello.py",
        workspace_root=str(tmp_path / "workspace"),
        plan=ExecutionPlan(
            goal="Create hello.py",
            summary="Create hello.py and validate it.",
            assumptions=["Python is installed."],
            tasks=[
                ExecutionTask(
                    id="task-1",
                    title="Create hello.py",
                    description="Write the file.",
                )
            ],
        ),
        task_results=[
            {
                "task_id": "task-1",
                "title": "Create hello.py",
                "attempts": 1,
                "changed_files": ["hello.py"],
                "commands": ["python3 hello.py"],
            }
        ],
        completed_at="2026-03-23T10:48:02.050087+00:00",
    )


def test_write_run_log_persists_timestamped_and_latest_files(tmp_path: Path) -> None:
    summary = make_run_summary(tmp_path)

    log_path = write_run_log(summary)

    assert log_path.exists()
    assert log_path.name == "run-2026-03-23T10-48-02.050087+00-00.json"
    latest_path = log_path.parent / "latest.json"
    assert latest_path.exists()
    assert '"goal": "Create hello.py"' in latest_path.read_text(encoding="utf-8")


def test_format_run_summary_returns_concise_terminal_output(tmp_path: Path) -> None:
    summary = make_run_summary(tmp_path)
    log_path = tmp_path / "workspace" / ".agent_logs" / "latest.json"

    text = format_run_summary(summary, log_path)

    assert "Run completed successfully." in text
    assert "Tasks completed: 1" in text
    assert "1. Create hello.py (attempts: 1)" in text
    assert "Files changed: hello.py" in text
    assert f"Detailed log: {log_path}" in text
