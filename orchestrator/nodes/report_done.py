from orchestrator.state import OrchestratorState


def report_done(state: OrchestratorState) -> OrchestratorState:
    status = state.get("builder_status", "unknown")
    task_file = state.get("current_task_file", "n/a")
    review_status = state.get("review_status", "skipped")
    commit_sha = state.get("commit_sha", "none")

    report = f"Build finished. Status: {status}. Task: {task_file}."
    report += f" Review: {review_status}."
    if commit_sha != "none":
        report += f" Commit: {commit_sha[:7]}."

    state["final_report"] = report
    return state
