from __future__ import annotations

from pathlib import Path

from agents.coder import CoderAgent
from agents.debugger import DebuggerAgent
from agents.planner import PlannerAgent
from agents.tool_agent import ToolAgent
from core.config import AppConfig, ExecutionSettings, LLMSettings, MemorySettings, OrchestrationSettings
from core.executor import ExecutorLayer
from core.orchestrator import AutonomousCodingOrchestrator
from core.tool_executor import ToolExecutor
from memory.store import MemoryStore
from tools.dependency_tool import DependencyInstallerTool
from tools.file_manager import FileManager
from tools.python_tool import PythonTool
from tools.registry import ToolSkill, build_default_tool_registry
from tools.shell_tool import ShellTool


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses

    def chat(self, messages, model=None, temperature=None, max_tokens=None) -> str:
        if not self.responses:
            raise AssertionError("No fake responses remaining.")
        return self.responses.pop(0)


def make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        llm=LLMSettings(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key_env="NVIDIA_API_KEY",
            model="test-model",
            temperature=0.0,
            top_p=1.0,
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
    )


def test_orchestrator_retries_and_recovers(tmp_path: Path) -> None:
    fake_llm = FakeLLM(
        responses=[
            """
            {
              "summary": "Create a hello-world script and validate it.",
              "assumptions": [],
              "tasks": [
                {
                  "id": "task-1",
                  "title": "Create greeting script",
                  "description": "Create a script that prints hello",
                  "deliverables": ["hello.py"],
                  "validation_commands": ["python3 hello.py"],
                  "done_definition": "The script prints hello"
                }
              ]
            }
            """,
            """
            {
              "summary": "Initial implementation with a bug.",
              "dependencies": [],
              "directories": [{"path": "app"}],
              "file_changes": [
                {
                  "path": "app/hello.py",
                  "action": "create",
                  "content": "print('helo')\\n"
                }
              ],
              "commands": [],
              "validation_commands": ["python3 app/hello.py && test \\"$(python3 app/hello.py)\\" = \\"hello\\""],
              "notes": []
            }
            """,
            """
            {
              "summary": "Fix the typo in the greeting.",
              "dependencies": [],
              "directories": [{"path": "app"}],
              "file_changes": [
                {
                  "path": "app/hello.py",
                  "action": "overwrite",
                  "content": "print('hello')\\n"
                }
              ],
              "commands": [],
              "validation_commands": ["python3 app/hello.py && test \\"$(python3 app/hello.py)\\" = \\"hello\\""],
              "notes": []
            }
            """,
        ]
    )

    config = make_config(tmp_path)
    shell_tool = ShellTool(
        shell=config.execution.shell,
        timeout_seconds=config.execution.command_timeout_seconds,
    )
    python_tool = PythonTool(config.execution.python_executable, shell_tool)
    dependency_tool = DependencyInstallerTool(config.execution.python_executable, shell_tool)
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
    orchestrator = AutonomousCodingOrchestrator(
        config=config,
        planner=PlannerAgent(llm=fake_llm, model="test-model"),
        coder=CoderAgent(llm=fake_llm, model="test-model"),
        debugger=DebuggerAgent(llm=fake_llm, model="test-model"),
        executor=executor,
        memory_store=memory_store,
        file_manager=file_manager,
    )

    summary = orchestrator.run("Build a greeting program.")

    hello_file = config.orchestration.workspace_root / "app" / "hello.py"
    assert hello_file.read_text(encoding="utf-8") == "print('hello')\n"
    assert summary.task_results[0]["attempts"] == 2
    assert (config.orchestration.workspace_root / "app").is_dir()

    memory_lines = config.memory.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(memory_lines) == 3


def test_file_manager_inventory_lists_directories_and_files(tmp_path: Path) -> None:
    file_manager = FileManager(tmp_path / "workspace")
    assert file_manager.create_dir("src/api")["status"] == "success"
    assert file_manager.write_file("src/api/server.py", "print('ok')\n")["status"] == "success"
    assert file_manager.create_dir("tests")["status"] == "success"

    inventory = file_manager.inventory()
    assert "src" in inventory["directories"]
    assert "src/api" in inventory["directories"]
    assert "tests" in inventory["directories"]
    assert "src/api/server.py" in inventory["files"]


def test_tool_agent_executes_json_requests_and_enforces_root_sandbox(tmp_path: Path) -> None:
    file_manager = FileManager(tmp_path / "workspace")
    shell_tool = ShellTool(shell="/bin/zsh", timeout_seconds=30)
    python_tool = PythonTool("python3", shell_tool)
    dependency_tool = DependencyInstallerTool("python3", shell_tool)
    tool_agent = ToolAgent(
        ToolExecutor(
            build_default_tool_registry(
                file_manager=file_manager,
                shell_tool=shell_tool,
                python_tool=python_tool,
                dependency_tool=dependency_tool,
            )
        )
    )

    create_result = tool_agent.handle(
        {
            "tool": "write_file",
            "arguments": {
                "path": "src/app.py",
                "content": "print('hello')\n",
            },
        }
    )
    assert create_result["status"] == "success"

    read_result = tool_agent.handle('{"tool":"read_file","arguments":{"path":"src/app.py"}}')
    assert read_result["status"] == "success"
    assert read_result["output"] == "print('hello')\n"

    move_result = tool_agent.handle(
        {
            "tool": "move",
            "arguments": {
                "src": "src/app.py",
                "dest": "src/main.py",
            },
        }
    )
    assert move_result["status"] == "success"

    list_result = tool_agent.handle({"tool": "list_files", "arguments": {"path": "."}})
    assert list_result["status"] == "success"
    assert "src/main.py" in list_result["output"]

    blocked_result = tool_agent.handle(
        {
            "tool": "write_file",
            "arguments": {
                "path": "../escape.py",
                "content": "print('nope')\n",
            },
        }
    )
    assert blocked_result["status"] == "error"
    assert "project root" in blocked_result["error"]


def test_tool_agent_selects_tools_by_description_and_supports_new_skills(tmp_path: Path) -> None:
    file_manager = FileManager(tmp_path / "workspace")
    shell_tool = ShellTool(shell="/bin/zsh", timeout_seconds=30)
    python_tool = PythonTool("python3", shell_tool)
    dependency_tool = DependencyInstallerTool("python3", shell_tool)
    registry = build_default_tool_registry(
        file_manager=file_manager,
        shell_tool=shell_tool,
        python_tool=python_tool,
        dependency_tool=dependency_tool,
    )
    registry.register(
        ToolSkill(
            name="count_lines",
            description="Count the number of lines in a workspace file. Use when validating file length or size.",
            inputs={"path": "string"},
            execute=lambda path: {"status": "success", "output": len(file_manager.read_file(path)["output"].splitlines()), "error": None},
        )
    )
    tool_agent = ToolAgent(ToolExecutor(registry))

    assert file_manager.write_file("notes.txt", "a\nb\nc\n")["status"] == "success"

    write_result = tool_agent.handle(
        {
            "description": "Create or overwrite a source file with complete contents.",
            "arguments": {"path": "src/app.py", "content": "print('ok')\n"},
        }
    )
    assert write_result["status"] == "success"
    assert write_result["selected_tool"] == "write_file"

    count_result = tool_agent.handle(
        {
            "description": "Count how many lines are in a workspace file.",
            "arguments": {"path": "notes.txt"},
        }
    )
    assert count_result["status"] == "success"
    assert count_result["selected_tool"] == "count_lines"
    assert count_result["output"] == 3
