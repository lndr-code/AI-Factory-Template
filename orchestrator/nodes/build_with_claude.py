import os
import subprocess
import shutil
from orchestrator.state import OrchestratorState

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/workspace")


def build_with_claude(state: OrchestratorState) -> OrchestratorState:
    # If preflight failed, don't run
    if state.get("builder_status") == "failed":
        return state

    task_file = state.get("current_task_file")

    claude_path = shutil.which("claude")
    if not claude_path:
        state["builder_status"] = "failed"
        state["last_error"] = "claude binary not found in PATH"
        return state

    try:
        prompt = f"""
You are the implementation agent for this repository.

Your workspace is at: {PROJECT_ROOT}

Read the task file at:
{os.path.join(PROJECT_ROOT, task_file)}

Before implementing, read the project specs in {PROJECT_ROOT}/specs/ to understand the architecture and requirements.

Implement the task in the repository following these rules:
- Follow the architecture and specs defined in /specs/
- Do not modify unrelated files
- Keep changes minimal, coherent, and well-organized
- When finished, write a brief summary to {PROJECT_ROOT}/reports/session-report.md
- Create a git commit with a clear, descriptive message describing what was implemented
"""

        env = os.environ.copy()
        env["CLAUDE_CODE_BUBBLEWRAP"] = "1"

        result = subprocess.run(
            [claude_path, "--dangerously-skip-permissions"],
            input=prompt,
            text=True,
            capture_output=True,
            cwd=PROJECT_ROOT,
            env=env
        )

        state["claude_stdout"] = result.stdout
        state["claude_stderr"] = result.stderr

        if result.returncode == 0:
            state["builder_status"] = "success"
        else:
            state["builder_status"] = "failed"
            state["last_error"] = f"Claude CLI exited with code {result.returncode}"

        return state

    except Exception as e:
        state["builder_status"] = "failed"
        state["last_error"] = str(e)
        return state
