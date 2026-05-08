from __future__ import annotations

import os
import shutil
import subprocess


SUPPORTED_BUILDERS = frozenset({"claude", "codex"})
FACTORY_ARTIFACT_ROOTS = ("reports", "tasks", "specs", "questions")


class ExternalBuilderError(RuntimeError):
    """Raised when External Builder setup is invalid."""


def run_external_builder(
    state: dict[str, object],
    task_file: str,
    builder: str | None = None,
) -> dict[str, object]:
    selected_builder = _select_builder(state, builder)
    factory_root = _required_path(state, "factory_root")
    target_root = _required_path(state, "target_root")
    run_dir = _required_path(state, "run_dir")
    os.makedirs(run_dir, exist_ok=True)

    task_path = _resolve_task_path(factory_root, task_file)
    prompt = build_external_prompt(state, task_path)

    result_state = dict(state)
    result_state["external_builder"] = selected_builder
    result_state["builder_prompt_path"] = _slash_path(_write_text(run_dir, "builder_prompt.md", prompt))

    artifacts_before = _find_factory_artifacts(target_root)
    try:
        head_before = _get_head_sha(target_root)
        completed = _invoke_builder(selected_builder, prompt, target_root, run_dir)
        _write_text(run_dir, f"{selected_builder}_stdout.log", completed.stdout or "")
        _write_text(run_dir, f"{selected_builder}_stderr.log", completed.stderr or "")

        head_after = _get_head_sha(target_root)
        if head_after != head_before:
            result_state.update(
                {
                    "builder_status": "policy_violation",
                    "build_status": "policy_violation",
                    "task_status": "failed",
                    "policy_violation": "builder_commit",
                    "last_error": "Builder created a git commit. Builders must not change HEAD.",
                }
            )
        else:
            artifact_violations = sorted(_find_factory_artifacts(target_root) - artifacts_before)
            if artifact_violations:
                result_state.update(
                    {
                        "builder_status": "policy_violation",
                        "build_status": "policy_violation",
                        "task_status": "failed",
                        "policy_violation": "external_artifact_created",
                        "last_error": (
                            "Builder created Factory artifacts in TARGET_ROOT: "
                            + ", ".join(artifact_violations)
                        ),
                    }
                )
            elif completed.returncode == 0:
                result_state.update(
                    {
                        "builder_status": "success",
                        "build_status": "success",
                    }
                )
            else:
                result_state.update(
                    {
                        "builder_status": "failed",
                        "build_status": "failed",
                        "task_status": "failed",
                        "last_error": (
                            f"{selected_builder} exited with code {completed.returncode}: "
                            f"{_error_summary(completed.stderr or completed.stdout)}"
                        ),
                    }
                )

        result_state["changed_files"] = _git_status_paths(target_root)
        result_state[f"{selected_builder}_stdout_log"] = _slash_path(
            os.path.join(run_dir, f"{selected_builder}_stdout.log")
        )
        result_state[f"{selected_builder}_stderr_log"] = _slash_path(
            os.path.join(run_dir, f"{selected_builder}_stderr.log")
        )
    except Exception as e:
        result_state.update(
            {
                "builder_status": "failed",
                "build_status": "failed",
                "task_status": "failed",
                "last_error": str(e),
            }
        )

    result_state["external_builder_report_path"] = _slash_path(
        write_external_builder_report(result_state)
    )
    return result_state


def build_external_prompt(
    state: dict[str, object],
    task_path: str,
) -> str:
    target_root = _required_path(state, "target_root")
    run_dir = _required_path(state, "run_dir")
    hashes = state.get("required_read_hashes")
    if not isinstance(hashes, dict) or not hashes:
        raise ExternalBuilderError("External builder state requires required_read_hashes")
    summary_path = os.path.join(run_dir, "builder_summary.md")

    task_content = _read_text(task_path)
    hashes_block = "\n".join(
        f"- {path}: {digest}"
        for path, digest in sorted((str(k), str(v)) for k, v in hashes.items())
    )

    return (
        "You are an implementation agent working on an external target repository.\n"
        f"Workspace: {_slash_path(target_root)}\n"
        f"Task file: {_slash_path(task_path)}\n"
        f"Run dir: {_slash_path(run_dir)}\n\n"
        "Task definition:\n"
        f"{task_content}\n\n"
        "Before implementing, read and follow these required target documents.\n"
        "Verify you are using the versions identified by these SHA256 hashes:\n"
        f"{hashes_block}\n\n"
        "Rules:\n"
        "- Implement only what the task describes; do not touch unrelated files.\n"
        "- Do not create a git commit, tag, branch, or other VCS operation that changes HEAD.\n"
        "- Do not create Factory artifacts inside the target repository: reports/, tasks/, specs/, or questions/.\n"
        "- Do not quote or copy confidential required-read contents into logs or reports.\n"
        f"- Write the implementation summary only to {_slash_path(summary_path)}.\n"
    )


def write_external_builder_report(state: dict[str, object]) -> str:
    run_dir = _required_path(state, "run_dir")
    path = os.path.abspath(os.path.join(run_dir, "report.md"))
    changed_files = state.get("changed_files", [])
    if isinstance(changed_files, list):
        changed = ", ".join(str(p) for p in changed_files) if changed_files else "none"
    else:
        changed = "unknown"
    lines = [
        "# External Builder Report",
        "",
        f"Target: {state.get('external_target', 'unknown')}",
        f"Builder: {state.get('external_builder', 'unknown')}",
        f"Status: {state.get('builder_status', 'unknown')}",
        f"Policy violation: {state.get('policy_violation', 'none')}",
        f"Changed files: {changed}",
    ]
    if state.get("last_error"):
        lines.append(f"Error: {_error_summary(str(state['last_error']))}")
    _write_text(run_dir, "report.md", "\n".join(lines) + "\n")
    return path


def _select_builder(state: dict[str, object], requested: str | None) -> str:
    selected = requested or state.get("external_builder_primary")
    if not isinstance(selected, str) or selected not in SUPPORTED_BUILDERS:
        raise ExternalBuilderError("External builder must be one of: claude, codex")
    return selected


def _invoke_builder(
    builder: str,
    prompt: str,
    target_root: str,
    run_dir: str,
) -> subprocess.CompletedProcess[str]:
    if builder == "codex":
        return _invoke_codex(prompt, target_root, run_dir)
    if builder == "claude":
        return _invoke_claude(prompt, target_root)
    raise ExternalBuilderError(f"Unsupported external builder: {builder}")


def _invoke_codex(
    prompt: str,
    target_root: str,
    run_dir: str,
) -> subprocess.CompletedProcess[str]:
    codex_path = shutil.which("codex")
    if not codex_path:
        raise ExternalBuilderError("codex binary not found in PATH")
    command = [
        codex_path,
        "--ask-for-approval",
        "never",
        "exec",
        "--cd",
        target_root,
        "--add-dir",
        run_dir,
        "--sandbox",
        "workspace-write",
        "--output-last-message",
        os.path.join(run_dir, "codex_last_message.md"),
        "-",
    ]
    return _run_builder_command(
        command,
        prompt,
        cwd=target_root,
        timeout=int(os.environ.get("CODEX_TIMEOUT", "600")),
    )


def _invoke_claude(
    prompt: str,
    target_root: str,
) -> subprocess.CompletedProcess[str]:
    claude_path = shutil.which("claude")
    if not claude_path:
        raise ExternalBuilderError("claude binary not found in PATH")
    return _run_builder_command(
        [claude_path, "--dangerously-skip-permissions"],
        prompt,
        cwd=target_root,
        timeout=int(os.environ.get("CLAUDE_TIMEOUT", "600")),
    )


def _run_builder_command(
    command: list[str],
    prompt: str,
    cwd: str,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        input=prompt,
        text=True,
        capture_output=True,
        cwd=cwd,
        env=os.environ.copy(),
        timeout=timeout,
        check=False,
    )


def _get_head_sha(target_root: str) -> str:
    result = _run_git(["rev-parse", "HEAD"], cwd=target_root)
    return result.stdout.strip()


def _git_status_paths(target_root: str) -> list[str]:
    result = _run_git(["status", "--porcelain"], cwd=target_root)
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        path = line[3:].strip()
        if " -> " in path:
            _old, path = path.split(" -> ", 1)
        paths.append(_slash_path(path))
    return sorted(paths)


def _run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ExternalBuilderError(f"git {' '.join(args)} failed: {detail}")
    return result


def _find_factory_artifacts(target_root: str) -> set[str]:
    root = os.path.abspath(target_root)
    found: set[str] = set()
    for rel_root in FACTORY_ARTIFACT_ROOTS:
        full_root = os.path.join(root, rel_root)
        if not os.path.exists(full_root):
            continue
        found.add(_slash_path(rel_root))
        if os.path.isdir(full_root):
            for current_root, dirs, files in os.walk(full_root):
                if ".git" in dirs:
                    dirs.remove(".git")
                for name in dirs:
                    found.add(_slash_path(os.path.relpath(os.path.join(current_root, name), root)))
                for name in files:
                    found.add(_slash_path(os.path.relpath(os.path.join(current_root, name), root)))
    return found


def _resolve_task_path(factory_root: str, task_file: str) -> str:
    path = task_file if os.path.isabs(task_file) else os.path.join(factory_root, task_file)
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise ExternalBuilderError(f"Task file not found: {task_file}")
    return path


def _required_path(state: dict[str, object], key: str) -> str:
    value = state.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ExternalBuilderError(f"External builder state requires {key}")
    return os.path.abspath(value)


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


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
