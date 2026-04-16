import os
import shutil
from orchestrator.state import OrchestratorState
from orchestrator.git_utils import capture_workspace_baseline, get_staged_paths

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.getcwd())


def preflight_environment(state: OrchestratorState) -> OrchestratorState:
    """
    Validates that all required tools, API keys, and workspace preconditions
    are met before the build phase begins.
    """
    errors = []

    # Check required CLIs
    if not shutil.which("claude"):
        errors.append(
            "claude CLI not found in PATH. "
            "Ensure @anthropic-ai/claude-code is installed (npm install -g @anthropic-ai/claude-code)."
        )
    if not shutil.which("git"):
        errors.append("git not found in PATH.")

    # Issue 4: Check required API keys for non-interactive container use
    if not os.environ.get("ANTHROPIC_API_KEY"):
        errors.append(
            "ANTHROPIC_API_KEY is not set. "
            "The Claude Code CLI requires it for non-interactive authentication."
        )
    if not os.environ.get("GEMINI_API_KEY"):
        errors.append("GEMINI_API_KEY is not set.")
    if os.environ.get("CODEX_ENABLED", "false").lower() == "true" and not os.environ.get("OPENAI_API_KEY"):
        errors.append("CODEX_ENABLED=true but OPENAI_API_KEY is not set.")

    # Check project workspace
    if not os.path.exists(PROJECT_ROOT):
        errors.append(f"PROJECT_ROOT does not exist: {PROJECT_ROOT}")
    if not os.path.exists(os.path.join(PROJECT_ROOT, ".git")):
        errors.append(f"No git repository found at {PROJECT_ROOT}.")

    # Check task file — only required when one has been explicitly assigned.
    # An empty task_file is valid during the architect path; that path no longer
    # routes through preflight, but we keep this guard non-fatal for safety.
    task_file = state.get("current_task_file")
    if task_file and not os.path.exists(os.path.join(PROJECT_ROOT, task_file)):
        errors.append(f"Task file not found: {task_file}")

    try:
        staged_paths = get_staged_paths()
        if staged_paths:
            errors.append(
                "Pre-staged changes are not allowed before a task starts: "
                + ", ".join(staged_paths)
            )
        baseline = capture_workspace_baseline()
        state["baseline_sha"] = baseline["sha"]  # type: ignore[index]
        state["baseline_status"] = baseline["status"]  # type: ignore[index]
        state["baseline_hashes"] = baseline["hashes"]  # type: ignore[index]
        max_retries = int(os.environ.get("MAX_TASK_RETRIES", "2"))
        state["max_retries"] = max_retries
        state["max_review_retries"] = int(os.environ.get("MAX_REVIEW_RETRIES", str(max_retries)))
        state["max_validation_retries"] = int(os.environ.get("MAX_VALIDATION_RETRIES", str(max_retries)))
        state["review_retry_count"] = int(state.get("review_retry_count", 0))
        state["validation_retry_count"] = int(state.get("validation_retry_count", 0))
    except Exception as e:
        errors.append(f"Could not capture git workspace baseline: {e}")

    if errors:
        state["preflight_status"] = "failed"
        state["task_status"] = "failed"
        state["builder_status"] = "failed"
        state["last_error"] = "\n".join(errors)
    else:
        state["preflight_status"] = "ready"
        state["task_status"] = "in_progress"
        state["builder_status"] = "ready"

    return state
