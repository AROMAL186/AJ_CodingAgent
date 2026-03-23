# AJ coding agent

This project implements the production-oriented AJ coding agent with a multi-agent architecture:

- `PlannerAgent` breaks a goal into ordered, executable tasks.
- `CoderAgent` generates code, file changes, dependencies, and validation commands.
- `TestingAgent` executes generated code safely, analyzes failures, and emits structured feedback for retry loops.
- `DebuggerAgent` diagnoses failed execution attempts and produces corrective changes.
- `ToolAgent` is the only write-capable agent and executes structured tool calls for file operations.
- `ToolSkill` defines each tool with a name, concise description, input schema, and execution function.
- `ToolRegistry` stores tool skills and selects the most relevant tool from descriptions and input context.
- `ToolExecutor` validates tool requests and dispatches them through the skill registry.
- `ComplexityProfile` scores incoming goals and pushes the planner/coder toward smaller, safer decomposition for harder tasks.
- `PlanGuardrails` and `WorkPlanGuardrails` add NeMo-style validation rails before plans and work batches reach execution.
- `FileManager` enforces the project-root sandbox for all file creation, reads, moves, and deletes.
- `ProjectExecutor` provides subprocess-based execution with timeouts, project-root restrictions, and dangerous-command blocking.
- `ExecutorLayer` converts work plans into Tool Agent requests, runs dependencies, and captures logs.
- `MemoryStore` persists plans, attempts, failures, and fixes in JSONL for iterative improvement.
- `WorkspaceFileTool` is now read-only and used only for workspace inspection and snapshots.

The runtime loop is:

`PLAN -> CODE -> EXECUTE -> ERROR? -> DEBUG -> RETRY -> SUCCESS`

For more complex goals, the system now injects:

- complexity guidance into planner/coder/debugger prompts
- the available tool-skill catalog into prompts
- guardrail validation on plans, file paths, and execution commands

## Structure

```text
agents/
core/
memory/
tests/
tools/
config.yaml
main.py
pyproject.toml
```

## Setup

1. Set your NVIDIA API key.

Option A: put it in a local `.env` file:

```bash
cp .env.example .env
```

Then edit `.env` and set:

```bash
NVIDIA_API_KEY="your_api_key_here"
```

Option B: export it in your shell:

```bash
export NVIDIA_API_KEY="your_api_key_here"
```

2. Install the project and dev dependencies:

```bash
python3 -m pip install -e '.[dev]'
```

## Run

```bash
python3 main.py "Build a FastAPI RAG service for PDF question answering."
```

## Tool Agent Example

Other agents can issue structured tool requests like this:

```json
{
  "tool": "write_file",
  "arguments": {
    "path": "src/main.py",
    "content": "print('hello')\n"
  }
}
```

The Tool Agent handles the request through:

`ToolAgent -> ToolExecutor -> ToolRegistry -> FileManager`

Description-based selection is also supported, so tool usage does not need to be hardcoded:

```json
{
  "description": "Write or overwrite a file when creating a new source file.",
  "arguments": {
    "path": "src/main.py",
    "content": "print('hello')\n"
  }
}
```

To generate into a custom workspace:

```bash
python3 main.py "Build a Streamlit SQL assistant." --workspace ./runs/sql-assistant
```

## Test

```bash
python3 -m pytest -q
```

## Testing Agent Example

```python
from pathlib import Path

from agents.testing_agent import TestingAgent
from tools.executor import ProjectExecutor

workspace = Path("./generated_workspace")
executor = ProjectExecutor(
    root=workspace,
    shell="/bin/zsh",
    timeout_seconds=30,
    python_executable="python3",
)
testing_agent = TestingAgent(executor=executor)

feedback = testing_agent.run_python_file("app/main.py")
print(feedback)

detailed_result = testing_agent.execute_with_details(command="python3 -m pytest -q")
print(detailed_result)
```
