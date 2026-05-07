import os
import glob
from orchestrator.state import OrchestratorState

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.getcwd())
TERMINAL_TASK_MARKERS = (".done.", ".failed.", ".blocked.")
TERMINAL_STATUSES = {"done", "failed", "blocked"}


def _get_frontmatter_status(path: str) -> str:
    """Extract status from YAML frontmatter, return 'open' if absent or unreadable."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.startswith("---"):
            return "open"
        end = content.find("\n---", 3)
        if end == -1:
            return "open"
        fm = content[3:end]
        for line in fm.splitlines():
            if line.strip().startswith("status:"):
                return line.split(":", 1)[1].strip().strip("\"'")
        return "open"
    except Exception:
        return "open"


def _is_open_task(path: str) -> bool:
    basename = os.path.basename(path)
    if basename == ".gitkeep":
        return False
    # Legacy: skip files with terminal markers in filename (pre-migration tasks)
    if any(marker in basename for marker in TERMINAL_TASK_MARKERS):
        return False
    # Primary: YAML frontmatter status is SSOT
    return _get_frontmatter_status(path) not in TERMINAL_STATUSES


def check_tasks_exist(state: OrchestratorState) -> OrchestratorState:
    """
    Checks if there are any non-terminal tasks in the tasks directory.
    If empty, we route to architect_agent. Otherwise to preflight_environment.
    Task status is determined by YAML frontmatter (status field), with legacy
    filename-marker support for unmigrated tasks.
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
