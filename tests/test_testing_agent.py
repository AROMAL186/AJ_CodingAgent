from __future__ import annotations

from pathlib import Path

from agents.testing_agent import TestingAgent
from tools.executor import ProjectExecutor


def make_testing_agent(tmp_path: Path, timeout_seconds: int = 5) -> tuple[TestingAgent, Path]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    executor = ProjectExecutor(
        root=workspace,
        shell="/bin/zsh",
        timeout_seconds=timeout_seconds,
        python_executable="python3",
    )
    return TestingAgent(executor=executor), workspace


def test_testing_agent_reports_success_for_python_file(tmp_path: Path) -> None:
    agent, workspace = make_testing_agent(tmp_path)
    (workspace / "ok.py").write_text("print('ready')\n", encoding="utf-8")

    details = agent.execute_with_details(path="ok.py")

    assert details["feedback"]["status"] == "success"
    assert details["feedback"]["error_type"] == "none"
    assert details["feedback"]["next_action"] == "complete"
    assert details["stdout"].strip() == "ready"
    assert details["exit_code"] == 0


def test_testing_agent_detects_syntax_errors(tmp_path: Path) -> None:
    agent, workspace = make_testing_agent(tmp_path)
    (workspace / "bad.py").write_text("def broken(:\n    pass\n", encoding="utf-8")

    feedback = agent.run_python_file("bad.py")

    assert feedback["status"] == "fail"
    assert feedback["error_type"] == "syntax_error"
    assert feedback["next_action"] == "fix_code"


def test_testing_agent_detects_missing_dependencies(tmp_path: Path) -> None:
    agent, workspace = make_testing_agent(tmp_path)
    (workspace / "missing_dep.py").write_text(
        "import package_that_should_not_exist_12345\n",
        encoding="utf-8",
    )

    feedback = agent.run_python_file("missing_dep.py")

    assert feedback["status"] == "fail"
    assert feedback["error_type"] == "dependency_error"
    assert feedback["next_action"] == "install_dependency"
    assert "pip install package_that_should_not_exist_12345" in feedback["suggestion"]


def test_testing_agent_blocks_dangerous_shell_commands(tmp_path: Path) -> None:
    agent, _ = make_testing_agent(tmp_path)

    details = agent.execute_with_details(command="rm -rf /")

    assert details["feedback"]["status"] == "fail"
    assert details["feedback"]["error_type"] == "runtime_error"
    assert details["feedback"]["next_action"] == "fix_code"
    assert "Blocked dangerous shell command" in details["stderr"]


def test_testing_agent_rejects_paths_outside_project_root(tmp_path: Path) -> None:
    agent, _ = make_testing_agent(tmp_path)

    details = agent.execute_with_details(path="../escape.py")

    assert details["feedback"]["status"] == "fail"
    assert details["feedback"]["error_type"] == "runtime_error"
    assert details["exit_code"] == 1
    assert "project root" in details["stderr"]
