import os
import datetime
from orchestrator.state import OrchestratorState
from orchestrator.llm.roles import invoke_reviewer
from orchestrator.git_utils import (
    assert_head_unchanged,
    changed_files_since_baseline,
    diff_for_paths,
    file_contents_blocks,
    get_head_sha,
    get_status_porcelain,
)

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.getcwd())


def review_with_gemini(state: OrchestratorState) -> OrchestratorState:
    """
    Code Reviewer: evaluates the builder's uncommitted changes against the task definition.
    Captures both tracked modifications (git diff HEAD) and new untracked files.
    Uses Gemini Pro (configurable via GEMINI_REVIEW_MODEL).
    """
    task_file = state.get("current_task_file")
    if not task_file:
        state["review_with_gemini_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = "No current_task_file in state"
        return state

    task_path = os.path.join(PROJECT_ROOT, task_file)
    try:
        with open(task_path, "r", encoding="utf-8") as f:
            task_content = f.read()
    except Exception as e:
        state["review_with_gemini_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = f"Could not read task file: {e}"
        return state

    # Collect only changes since the preflight baseline.
    try:
        baseline_sha = state.get("baseline_sha") or get_head_sha()
        assert_head_unchanged(baseline_sha, "builder execution before review")
        baseline_status = state.get("baseline_status", {})
        baseline_hashes = state.get("baseline_hashes", {})
        changed_files, unsafe_files = changed_files_since_baseline(
            baseline_status,
            baseline_hashes,
        )
        state["changed_files"] = changed_files
        state["unsafe_changed_files"] = unsafe_files
    except RuntimeError as e:
        state["review_with_gemini_status"] = "policy_violation"
        state["builder_status"] = "policy_violation"
        state["task_status"] = "failed"
        state["policy_violation"] = "head_changed_before_review"
        state["last_error"] = str(e)
        return state
    except Exception as e:
        state["review_with_gemini_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = f"Failed to get git diff: {e}"
        return state

    if unsafe_files:
        state["review_with_gemini_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = (
            "Builder modified files that were already dirty at task start: "
            + ", ".join(unsafe_files)
        )
        return state

    _SYSTEM_PROTECTED = (
        "orchestrator/",
        ".agent/",
        "run_graph.py",
        "docker-compose.yml",
        "Dockerfile",
        "requirements.txt",
    )
    system_violations = [
        f for f in changed_files
        if any(f == p.rstrip("/") or f.startswith(p) for p in _SYSTEM_PROTECTED)
    ]
    if system_violations:
        state["review_with_gemini_status"] = "policy_violation"
        state["builder_status"] = "policy_violation"
        state["task_status"] = "failed"
        state["policy_violation"] = "system_file_modified"
        state["last_error"] = (
            "Builder modified system-protected files: " + ", ".join(system_violations)
        )
        return state

    current_status = get_status_porcelain()
    untracked_files = [p for p in changed_files if current_status.get(p, "").startswith("??")]
    git_diff = diff_for_paths(baseline_sha, changed_files)
    new_file_contents = file_contents_blocks(untracked_files)

    combined_changes = git_diff
    if new_file_contents:
        combined_changes += f"\n\n=== NEW FILES ===\n{new_file_contents}"

    if not combined_changes.strip():
        state["review_with_gemini_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = (
            "No changes detected — git diff and untracked file list are both empty. "
            "The builder may not have made any changes."
        )
        return state

    prompt = f"""You are a code reviewer. Evaluate the uncommitted workspace changes against the task definition below.

Task Definition:
{task_content}

Changes (tracked modifications + new untracked files):
{combined_changes}

Decide the status:
- 'approved' if the implementation is correct and complete
- 'needs_revision' if changes are required
- 'failed' if there are critical errors that cannot be addressed by revision

Respond in exactly this format:
STATUS: [approved | needs_revision | failed]
REASON: [specific, actionable feedback — if not approved, be concrete about what must change]
"""

    try:
        response_text = invoke_reviewer(prompt)

        status = "failed"
        reason = "No reason provided."

        for line in response_text.splitlines():
            if line.startswith("STATUS:"):
                status = line.replace("STATUS:", "").strip().lower()
                break

        if "REASON:" in response_text:
            reason = response_text.split("REASON:", 1)[1].strip()

        state["review_with_gemini_status"] = status

        # Issue 7: store reviewer feedback for builder retry prompt
        if status == "needs_revision":
            state["review_feedback"] = reason
            state["retry_feedback"] = reason
            review_retry_count = state.get("review_retry_count", state.get("retry_count", 0)) + 1
            state["review_retry_count"] = review_retry_count
            state["retry_count"] = review_retry_count
            if review_retry_count > state.get("max_review_retries", state.get("max_retries", 2)):
                state["task_status"] = "failed"
                state["last_error"] = (
                    f"Max review retries reached ({review_retry_count}) - task revision did not converge."
                )
        elif status == "approved":
            state["review_feedback"] = None
            state["retry_feedback"] = None
            state["review_retry_count"] = 0
        elif status == "failed":
            state["task_status"] = "failed"
            state["last_error"] = reason

        # Append to persistent review log
        log_path = os.path.join(PROJECT_ROOT, "reports", "review-log.md")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n## {os.path.basename(task_file)} — {date_str}\n")
            f.write(f"**Status:** {status}\n")
            f.write(f"**Feedback:** {reason}\n")

    except ValueError as e:
        state["review_with_gemini_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = str(e)
    except Exception as e:
        state["review_with_gemini_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = f"Review with Gemini failed: {e}"

    return state
