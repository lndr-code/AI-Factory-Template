from __future__ import annotations

import datetime
import fnmatch
import os
import subprocess

from orchestrator.external.manifest import ExternalTargetConfig, load_external_target
from orchestrator.external.read_receipt import build_read_receipt, write_read_receipt


class ExternalRunnerError(RuntimeError):
    """Raised when External Mode preflight cannot proceed safely."""


def run_external_preflight(
    target_name: str,
    factory_root: str | None = None,
    target_root: str | None = None,
) -> dict[str, object]:
    """Open an external target and write a required-read hash receipt."""
    resolved_factory_root = resolve_factory_root(factory_root)
    manifest = load_external_target(target_name, factory_root=resolved_factory_root)
    resolved_target_root = resolve_target_root(
        target_name=target_name,
        factory_root=resolved_factory_root,
        target_root=target_root,
    )

    open_target_repo(manifest, resolved_target_root)
    deny_matches = find_deny_glob_matches(
        resolved_target_root,
        manifest.security.deny_globs,
    )
    if deny_matches and manifest.security.abort_if_deny_glob_present:
        raise ExternalRunnerError(
            "Target contains files blocked by deny_globs: " + ", ".join(deny_matches)
        )

    hashes = build_read_receipt(
        resolved_target_root,
        manifest.required_read_files,
    )
    run_id = make_run_id(target_name)
    run_dir = os.path.abspath(os.path.join(resolved_factory_root, "runs", run_id))
    receipt = {
        "target": target_name,
        "target_root": _slash_path(resolved_target_root),
        "base_branch": manifest.base_branch,
        "required_read_hashes": hashes,
    }
    receipt_path = write_read_receipt(run_dir, receipt)

    state: dict[str, object] = {
        "external_mode": True,
        "external_target": target_name,
        "factory_root": _slash_path(resolved_factory_root),
        "target_root": _slash_path(resolved_target_root),
        "run_id": run_id,
        "run_dir": _slash_path(run_dir),
        "manifest_path": manifest.manifest_path,
        "required_read_hashes": hashes,
        "validation_command": manifest.validation.command,
        "validation_timeout_seconds": manifest.validation.timeout_seconds,
        "external_builder_primary": manifest.builders.primary,
        "external_builder_fallback": manifest.builders.fallback,
        "deny_globs": list(manifest.security.deny_globs),
        "protected_paths_in_diff": list(manifest.security.protected_paths_in_diff),
        "read_receipt_path": _slash_path(receipt_path),
    }
    return state


def resolve_factory_root(factory_root: str | None = None) -> str:
    root = factory_root or os.environ.get("FACTORY_ROOT") or os.getcwd()
    return os.path.abspath(root)


def resolve_target_root(
    target_name: str,
    factory_root: str,
    target_root: str | None = None,
) -> str:
    root = (
        target_root
        or os.environ.get("TARGET_ROOT")
        or os.path.join(factory_root, "external_targets", target_name)
    )
    resolved = os.path.abspath(root)
    _validate_target_root(factory_root, resolved)
    return resolved


def open_target_repo(
    manifest: ExternalTargetConfig,
    target_root: str,
) -> None:
    if os.path.exists(target_root):
        if not os.path.isdir(target_root):
            raise ExternalRunnerError(f"TARGET_ROOT exists but is not a directory: {target_root}")
        if not os.path.isdir(os.path.join(target_root, ".git")):
            raise ExternalRunnerError(f"TARGET_ROOT exists but is not a git repository: {target_root}")
    else:
        parent = os.path.dirname(target_root)
        os.makedirs(parent, exist_ok=True)
        _run_git(["clone", manifest.repo, target_root], cwd=parent)

    _run_git(["checkout", manifest.base_branch], cwd=target_root)
    active_branch = _run_git(["branch", "--show-current"], cwd=target_root).stdout.strip()
    if active_branch != manifest.base_branch:
        raise ExternalRunnerError(
            f"Target branch must be {manifest.base_branch!r}, got {active_branch!r}"
        )
    if active_branch in manifest.protected_branches:
        raise ExternalRunnerError(f"Refusing to operate on protected branch: {active_branch}")

    status = _run_git(["status", "--porcelain"], cwd=target_root).stdout.strip()
    if status:
        raise ExternalRunnerError("TARGET_ROOT must be clean before External Mode preflight")


def find_deny_glob_matches(
    target_root: str,
    deny_globs: tuple[str, ...],
) -> list[str]:
    root = os.path.abspath(target_root)
    normalized_globs = tuple(_slash_path(pattern) for pattern in deny_globs)
    matches: set[str] = set()

    for current_root, dirs, files in os.walk(root):
        if ".git" in dirs:
            dirs.remove(".git")
        for name in dirs:
            rel = _slash_path(os.path.relpath(os.path.join(current_root, name), root))
            if _matches_any(rel, normalized_globs):
                matches.add(rel)
        for name in files:
            rel = _slash_path(os.path.relpath(os.path.join(current_root, name), root))
            if _matches_any(rel, normalized_globs):
                matches.add(rel)

    return sorted(matches)


def make_run_id(target_name: str) -> str:
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{target_name}"


def _validate_target_root(factory_root: str, target_root: str) -> None:
    factory = os.path.abspath(factory_root)
    target = os.path.abspath(target_root)
    if factory == target:
        raise ExternalRunnerError("TARGET_ROOT must not be the same directory as FACTORY_ROOT")

    sensitive_roots = (
        ".git",
        "orchestrator",
        "targets",
        "runs",
    )
    for rel in sensitive_roots:
        sensitive = os.path.abspath(os.path.join(factory, rel))
        if _is_within(target, sensitive):
            raise ExternalRunnerError(f"TARGET_ROOT must not be inside FACTORY_ROOT/{rel}")


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(_matches_pattern(path, pattern) for pattern in patterns)


def _matches_pattern(path: str, pattern: str) -> bool:
    if fnmatch.fnmatchcase(path, pattern):
        return True
    if pattern.endswith("/**"):
        root = pattern[:-3].rstrip("/")
        return path == root or path.startswith(root + "/")
    return False


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
        raise ExternalRunnerError(f"git {' '.join(args)} failed: {detail}")
    return result


def _is_within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _slash_path(path: str) -> str:
    return path.replace("\\", "/")
