import os
import subprocess

from orchestrator.git_utils import (
    assert_head_unchanged,
    assert_index_subset,
    get_head_sha,
    get_status_porcelain,
    run_git,
    stage_paths,
)
from orchestrator.state import OrchestratorState


PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.getcwd())


def _run_validation() -> tuple[bool, str]:
    """
    Run VALIDATION_COMMAND if set. Returns (passed: bool, output: str).
    If not set, skips validation and returns True with an informational message.
    """
    cmd = os.environ.get("VALIDATION_COMMAND", "").strip()
    if not cmd:
        return True, "Validation skipped - VALIDATION_COMMAND not set."

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            timeout=int(os.environ.get("VALIDATION_TIMEOUT", "300")),
        )
        output = result.stdout + result.stderr
        if result.returncode == 0:
            return True, output
        return False, f"Validation failed (exit {result.returncode}):\n{output}"
    except subprocess.TimeoutExpired:
        return False, "Validation timed out."
    except Exception as e:
        return False, f"Validation error: {e}"


def _patch_frontmatter_status(content: str, new_status: str) -> str:
    """Set or add status field in YAML frontmatter without touching the rest."""
    import re
    if not content.startswith("---"):
        return f"---\nstatus: {new_status}\n---\n{content}"
    end = content.find("\n---", 3)
    if end == -1:
        return content
    fm = content[3:end]
    rest = content[end:]
    if re.search(r"^status:", fm, re.MULTILINE):
        fm = re.sub(r"^status:.*$", f"status: {new_status}", fm, flags=re.MULTILINE)
    else:
        fm = fm.rstrip("\n") + f"\nstatus: {new_status}\n"
    return f"---{fm}{rest}"


def review_and_commit(state: OrchestratorState) -> OrchestratorState:
    """
    Commit node: runs after reviewer approval.
    Validation failures become retry feedback. Successful commits include the
    task's .done.md lifecycle marker in the same commit as the implementation.
    """
    try:
        changed_files = list(state.get("changed_files", []))
        status = get_status_porcelain()
        state["git_status_output"] = "\n".join(f"{v} {k}" for k, v in status.items())
        baseline_sha = state.get("baseline_sha") or get_head_sha()
        assert_head_unchanged(baseline_sha, "review and commit")

        if not changed_files:
            state["review_status"] = "no_changes"
            state["task_status"] = "failed"
            state["last_error"] = "No task-scoped changes available to commit."
            return state

        assert_index_subset(changed_files)

        validation_passed, validation_output = _run_validation()
        state["test_output"] = validation_output

        if not validation_passed:
            retry_count = state.get("validation_retry_count", 0) + 1
            state["validation_retry_count"] = retry_count
            state["retry_count"] = retry_count
            state["review_status"] = "needs_revision"
            state["validation_status"] = "failed"
            state["retry_feedback"] = validation_output
            state["last_error"] = validation_output
            if retry_count > state.get("max_validation_retries", state.get("max_retries", 2)):
                state["review_status"] = "failed"
                state["task_status"] = "failed"
            return state

        state["validation_status"] = "passed"

        task_file = state.get("current_task_file", "unknown-task")
        task_name = os.path.basename(task_file).replace(".md", "")
        commit_message = f"feat: complete {task_name} [automated]"
        stage_candidates = set(changed_files)

        if task_file and task_file != "unknown-task":
            full_path = os.path.join(PROJECT_ROOT, task_file)
            if os.path.exists(full_path) and ".done." not in task_file:
                with open(full_path, "r", encoding="utf-8") as f:
                    task_content = f.read()
                patched = _patch_frontmatter_status(task_content, "done")
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(patched)
                stage_candidates.add(task_file.replace("\\", "/"))

        stage_paths(stage_candidates)
        assert_index_subset(stage_candidates)
        assert_head_unchanged(baseline_sha, "final commit boundary")
        run_git(["commit", "-m", commit_message], check=True)

        state["commit_sha"] = get_head_sha()
        state["review_status"] = "success"
        state["task_status"] = "done"
        state["retry_feedback"] = None
        state["validation_retry_count"] = 0

    except subprocess.CalledProcessError as e:
        state["review_status"] = "failed"
        state["builder_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = f"Git operation failed: {e.stderr if e.stderr else str(e)}"
    except RuntimeError as e:
        state["review_status"] = "policy_violation"
        state["builder_status"] = "policy_violation"
        state["task_status"] = "failed"
        state["policy_violation"] = "commit_boundary"
        state["last_error"] = str(e)
    except Exception as e:
        state["review_status"] = "failed"
        state["builder_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = str(e)

    return state
