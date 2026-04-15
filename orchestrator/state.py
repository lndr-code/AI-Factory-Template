from typing import TypedDict, Optional

class OrchestratorState(TypedDict, total=False):
    current_task_file: str
    builder_status: str
    last_error: Optional[str]
    final_report: str
    claude_stdout: str
    claude_stderr: str
    codex_stdout: str
    codex_stderr: str
    review_status: str
    git_status_output: str
    test_output: str
    commit_sha: str
