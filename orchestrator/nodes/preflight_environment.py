import os
import shutil
from orchestrator.state import OrchestratorState

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/workspace")


def preflight_environment(state: OrchestratorState) -> OrchestratorState:
    errors = []

    # Check for claude CLI
    if not shutil.which("claude"):
        errors.append("claude CLI not found in PATH")

    # Check for git
    if not shutil.which("git"):
        errors.append("git not found in PATH")

    # Check for project root
    if not os.path.exists(PROJECT_ROOT):
        errors.append(f"{PROJECT_ROOT} directory does not exist")

    # Check for .git in project root
    if not os.path.exists(os.path.join(PROJECT_ROOT, ".git")):
        errors.append(f"{PROJECT_ROOT}/.git directory does not exist")

    # Check task file
    task_file = state.get("current_task_file")
    if not task_file or not os.path.exists(os.path.join(PROJECT_ROOT, task_file)):
        errors.append(f"Task file not found: {task_file}")

    if errors:
        state["builder_status"] = "failed"
        state["last_error"] = "\n".join(errors)
    else:
        state["builder_status"] = "ready"

    return state
