from __future__ import annotations

import os
import subprocess

from orchestrator.external.read_receipt import ReadReceiptError, verify_read_receipt


FACTORY_ARTIFACT_ROOTS = ("reports", "tasks", "specs", "questions")


class ExternalFinalizeError(RuntimeError):
    """Raised when the External Mode patch finalizer cannot run safely."""


def finalize_external_patch(state: dict[str, object]) -> dict[str, object]:
    """Validate TARGET_ROOT and write changes.patch into the run directory."""
    result_state = dict(state)
    if state.get("builder_status") != "success":
        result_state.update(
            {
                "finalize_status": "skipped",
                "task_status": "failed",
                "last_error": "External finalizer requires builder_status=success.",
            }
        )
        result_state["external_finalizer_report_path"] = _slash_path(
            write_external_finalizer_report(result_state)
        )
        return result_state

    target_root = _required_path(state, "target_root")
    run_dir = _required_path(state, "run_dir")
    validation_command = _required_string(state, "validation_command")
    validation_timeout = _required_int(state, "validation_timeout_seconds")
    os.makedirs(run_dir, exist_ok=True)

    expected_hashes = state.get("required_read_hashes", {})
    if not isinstance(expected_hashes, dict):
        raise ExternalFinalizeError("External finalizer state requires required_read_hashes")
    try:
        verify_read_receipt(
            target_root,
            {str(path): str(digest) for path, digest in expected_hashes.items()},
        )
    except ReadReceiptError as e:
        result_state.update(
            {
                "finalize_status": "policy_violation",
                "validation_status": "skipped",
                "patch_status": "skipped",
                "task_status": "failed",
                "policy_violation": "required_read_changed",
                "last_error": str(e),
            }
        )
        result_state["external_finalizer_report_path"] = _slash_path(
            write_external_finalizer_report(result_state)
        )
        return result_state

    validation_passed, validation_output = _run_validation(
        command=validation_command,
        target_root=target_root,
        timeout_seconds=validation_timeout,
    )
    validation_log_path = _write_text(run_dir, "validation.log", validation_output)
    result_state["validation_log_path"] = _slash_path(validation_log_path)

    if not validation_passed:
        result_state.update(
            {
                "finalize_status": "failed",
                "validation_status": "failed",
                "patch_status": "skipped",
                "task_status": "failed",
                "last_error": _error_summary(validation_output) or "Validation failed.",
            }
        )
        result_state["external_finalizer_report_path"] = _slash_path(
            write_external_finalizer_report(result_state)
        )
        return result_state

    result_state["validation_status"] = "passed"
    changed_files = _git_changed_files(target_root)
    result_state["changed_files"] = changed_files

    artifact_paths = _factory_artifact_paths(changed_files)
    if artifact_paths:
        result_state.update(
            {
                "finalize_status": "policy_violation",
                "patch_status": "policy_violation",
                "task_status": "failed",
                "policy_violation": "idp_artifact_in_patch",
                "last_error": "Patch would include Factory artifacts: " + ", ".join(artifact_paths),
            }
        )
        result_state["external_finalizer_report_path"] = _slash_path(
            write_external_finalizer_report(result_state)
        )
        return result_state

    patch = _git_diff_binary(target_root)
    if not patch.strip():
        result_state.update(
            {
                "finalize_status": "failed",
                "patch_status": "no_changes",
                "task_status": "failed",
                "last_error": "No target changes available for changes.patch.",
            }
        )
        result_state["external_finalizer_report_path"] = _slash_path(
            write_external_finalizer_report(result_state)
        )
        return result_state

    patch_path = _write_text(run_dir, "changes.patch", patch)
    # The working tree intentionally remains dirty for human inspection. Check
    # the patch against the index instead of the already-modified files.
    apply_check = _run_git(
        ["apply", "--check", "--cached", "--ignore-whitespace", patch_path],
        cwd=target_root,
        check=False,
    )
    if apply_check.returncode != 0:
        result_state.update(
            {
                "finalize_status": "failed",
                "patch_status": "failed",
                "task_status": "failed",
                "changes_patch_path": _slash_path(patch_path),
                "last_error": _error_summary(apply_check.stderr or apply_check.stdout),
            }
        )
        result_state["external_finalizer_report_path"] = _slash_path(
            write_external_finalizer_report(result_state)
        )
        return result_state

    result_state.update(
        {
            "finalize_status": "success",
            "patch_status": "created",
            "task_status": "done",
            "changes_patch_path": _slash_path(patch_path),
        }
    )
    result_state["external_finalizer_report_path"] = _slash_path(
        write_external_finalizer_report(result_state)
    )
    return result_state


def write_external_finalizer_report(state: dict[str, object]) -> str:
    run_dir = _required_path(state, "run_dir")
    path = os.path.abspath(os.path.join(run_dir, "report.md"))
    changed_files = state.get("changed_files", [])
    if isinstance(changed_files, list):
        changed = ", ".join(str(p) for p in changed_files) if changed_files else "none"
    else:
        changed = "unknown"
    lines = [
        "# External Run Report",
        "",
        f"Target: {state.get('external_target', 'unknown')}",
        f"Builder: {state.get('external_builder', 'unknown')}",
        f"Builder status: {state.get('builder_status', 'unknown')}",
        f"Validation status: {state.get('validation_status', 'unknown')}",
        f"Patch status: {state.get('patch_status', 'unknown')}",
        f"Policy violation: {state.get('policy_violation', 'none')}",
        f"Changed files: {changed}",
        f"Validation log: {state.get('validation_log_path', 'none')}",
        f"Patch: {state.get('changes_patch_path', 'none')}",
    ]
    if state.get("last_error"):
        lines.append(f"Error: {_error_summary(str(state['last_error']))}")
    _write_text(run_dir, "report.md", "\n".join(lines) + "\n")
    return path


def _run_validation(
    command: str,
    target_root: str,
    timeout_seconds: int,
) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=target_root,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        output = (e.stdout or "") + (e.stderr or "")
        output = output + "\nValidation timed out."
        return False, output

    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode == 0:
        return True, output
    return False, f"Validation failed (exit {result.returncode}):\n{output}"


def _git_changed_files(target_root: str) -> list[str]:
    result = _run_git(["diff", "--name-only", "HEAD"], cwd=target_root)
    return sorted(_slash_path(line.strip()) for line in result.stdout.splitlines() if line.strip())


def _git_diff_binary(target_root: str) -> str:
    return _run_git(["diff", "--binary", "HEAD"], cwd=target_root).stdout


def _factory_artifact_paths(paths: list[str]) -> list[str]:
    artifacts: list[str] = []
    for path in paths:
        if any(path == root or path.startswith(root + "/") for root in FACTORY_ARTIFACT_ROOTS):
            artifacts.append(path)
    return artifacts


def _run_git(
    args: list[str],
    cwd: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ExternalFinalizeError(f"git {' '.join(args)} failed: {detail}")
    return result


def _required_path(state: dict[str, object], key: str) -> str:
    value = state.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ExternalFinalizeError(f"External finalizer state requires {key}")
    return os.path.abspath(value)


def _required_string(state: dict[str, object], key: str) -> str:
    value = state.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ExternalFinalizeError(f"External finalizer state requires {key}")
    return value


def _required_int(state: dict[str, object], key: str) -> int:
    value = state.get(key)
    if not isinstance(value, int) or value <= 0:
        raise ExternalFinalizeError(f"External finalizer state requires positive integer {key}")
    return value


def _write_text(run_dir: str, filename: str, content: str) -> str:
    os.makedirs(run_dir, exist_ok=True)
    path = os.path.abspath(os.path.join(run_dir, filename))
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _error_summary(text: str, limit: int = 500) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _slash_path(path: str) -> str:
    return path.replace("\\", "/")
