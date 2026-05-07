from typing import TypedDict, Optional

class OrchestratorState(TypedDict, total=False):
    current_task_file: str
    task_status: str
    planning_status: str
    critic_status: str
    preflight_status: str
    build_status: str
    validation_status: str
    builder_status: str
    last_error: Optional[str]
    final_report: str
    claude_stdout: str
    claude_stderr: str
    codex_stdout: str
    codex_stderr: str
    review_status: str
    review_with_gemini_status: str
    retry_count: int
    max_retries: int
    review_retry_count: int
    validation_retry_count: int
    max_review_retries: int
    max_validation_retries: int
    critic_feedback: Optional[str]
    review_feedback: Optional[str]
    retry_feedback: Optional[str]
    git_status_output: str
    test_output: str
    commit_sha: str
    baseline_sha: str
    baseline_status: dict[str, str]
    baseline_hashes: dict[str, str]
    changed_files: list[str]
    unsafe_changed_files: list[str]
    planning_files: list[str]
    policy_violation: str
    external_mode: bool
    external_target: str
    factory_root: str
    target_root: str
    run_id: str
    run_dir: str
    manifest_path: str
    required_read_hashes: dict[str, str]
    validation_command: str
    validation_timeout_seconds: int
    deny_globs: list[str]
    protected_paths_in_diff: list[str]
