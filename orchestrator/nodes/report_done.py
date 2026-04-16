import datetime
import os

from orchestrator.state import OrchestratorState

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.getcwd())


def report_done(state: OrchestratorState) -> OrchestratorState:
    """
    Terminal node: generates a structured report and appends it to reports/run-report.md.
    Also resolves retry exhaustion into explicit terminal task states.
    """
    task_file = state.get("current_task_file", "n/a")
    review_status = state.get("review_status", "skipped")
    planning_status = state.get("planning_status", "skipped")
    preflight_status = state.get("preflight_status", "skipped")
    build_status = state.get("build_status", "skipped")
    validation_status = state.get("validation_status", "skipped")
    commit_sha = state.get("commit_sha", "none")
    last_error = state.get("last_error", "")
    review_retry_count = state.get("review_retry_count", state.get("retry_count", 0))
    validation_retry_count = state.get("validation_retry_count", 0)
    retry_count = max(review_retry_count, validation_retry_count)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if (
        state.get("review_with_gemini_status") == "needs_revision"
        and review_retry_count > state.get("max_review_retries", state.get("max_retries", 2))
    ):
        last_error = last_error or (
            f"Max review retries reached ({review_retry_count}) - task revision did not converge."
        )
        state["last_error"] = last_error
        state["task_status"] = "failed"

    if (
        state.get("validation_status") == "failed"
        and validation_retry_count > state.get("max_validation_retries", state.get("max_retries", 2))
    ):
        last_error = last_error or (
            f"Max validation retries reached ({validation_retry_count}) - validation did not converge."
        )
        state["last_error"] = last_error
        state["task_status"] = "failed"

    status = state.get("task_status") or state.get("builder_status", "unknown")

    lines = [
        f"[{timestamp}] Run finished.",
        f"  Task:    {task_file}",
        f"  Status:  {status}",
        f"  Plan:    {planning_status}",
        f"  Preflight: {preflight_status}",
        f"  Build:   {build_status}",
        f"  Review:  {review_status}",
        f"  Validation: {validation_status}",
    ]
    if commit_sha != "none":
        lines.append(f"  Commit:  {commit_sha[:7]}")
    if last_error:
        lines.append(f"  Error:   {last_error}")
    if review_retry_count:
        lines.append(f"  Review retries: {review_retry_count}")
    if validation_retry_count:
        lines.append(f"  Validation retries: {validation_retry_count}")

    report = "\n".join(lines)
    state["final_report"] = report

    try:
        reports_dir = os.path.join(PROJECT_ROOT, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        with open(os.path.join(reports_dir, "run-report.md"), "a", encoding="utf-8") as f:
            f.write(report + "\n\n")
    except Exception:
        pass

    # Mark failed tasks in the filesystem so they are skipped on the next run.
    if state.get("task_status") == "failed":
        _task_file = state.get("current_task_file", "")
        if _task_file and not any(m in _task_file for m in (".done.", ".failed.", ".blocked.")):
            _full = os.path.join(PROJECT_ROOT, _task_file)
            if os.path.exists(_full):
                _base, _ext = os.path.splitext(_full)
                _failed = f"{_base}.failed{_ext or '.md'}"
                try:
                    os.rename(_full, _failed)
                except Exception:
                    pass  # best-effort; don't mask the original failure

    return state
