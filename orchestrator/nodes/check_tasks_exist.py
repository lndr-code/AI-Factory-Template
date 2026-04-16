import os
import glob
from orchestrator.state import OrchestratorState

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.getcwd())
TERMINAL_TASK_MARKERS = (".done.", ".failed.", ".blocked.")


def _is_open_task(path: str) -> bool:
    basename = os.path.basename(path)
    return basename != ".gitkeep" and not any(marker in basename for marker in TERMINAL_TASK_MARKERS)


def check_tasks_exist(state: OrchestratorState) -> OrchestratorState:
    """
    Checks if there are any non-terminal tasks in the tasks directory.
    If empty, we route to architect_agent. Otherwise to preflight_environment.
    """
    tasks_dir = os.path.join(PROJECT_ROOT, "tasks")
    if not os.path.exists(tasks_dir):
        state["builder_status"] = "no_tasks"
        state["task_status"] = "no_tasks"
        return state

    all_tasks = glob.glob(os.path.join(tasks_dir, "*.md"))
    open_tasks = [t for t in all_tasks if _is_open_task(t)]

    if not open_tasks:
        state["builder_status"] = "no_tasks"
        state["task_status"] = "no_tasks"
    else:
        state["builder_status"] = "tasks_exist"
        state["task_status"] = "open"
    
    return state
