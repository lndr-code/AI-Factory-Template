import hashlib
import os
import subprocess
from typing import Iterable


PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.getcwd())


def run_git(args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=check,
    )


def get_head_sha() -> str:
    result = run_git(["rev-parse", "HEAD"], check=True)
    return result.stdout.strip()


def get_status_porcelain() -> dict[str, str]:
    result = run_git(["status", "--porcelain"], check=True)
    status: dict[str, str] = {}
    for code, path, _old_path in get_status_entries(result.stdout):
        status[path] = code
    return status


def get_status_entries(output: str | None = None) -> list[tuple[str, str, str | None]]:
    """Return (xy_status, path, old_path) entries, preserving both sides of renames."""
    if output is None:
        output = run_git(["status", "--porcelain"], check=True).stdout

    entries: list[tuple[str, str, str | None]] = []
    for line in output.splitlines():
        if not line:
            continue
        code = line[:2]
        path = line[3:].strip()
        old_path = None
        if " -> " in path:
            old_path, path = path.split(" -> ", 1)
            old_path = old_path.replace("\\", "/")
        entries.append((code, path.replace("\\", "/"), old_path))
    return entries


def get_status_paths(include_rename_sources: bool = True) -> set[str]:
    paths: set[str] = set()
    for _code, path, old_path in get_status_entries():
        paths.add(path)
        if include_rename_sources and old_path:
            paths.add(old_path)
    return paths


def get_staged_paths() -> list[str]:
    """Return staged paths, including both old and new paths for staged renames."""
    result = run_git(["diff", "--cached", "--name-status", "-M"], check=True)
    paths: set[str] = set()
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith(("R", "C")) and len(parts) >= 3:
            paths.add(parts[1].replace("\\", "/"))
            paths.add(parts[2].replace("\\", "/"))
        elif len(parts) >= 2:
            paths.add(parts[1].replace("\\", "/"))
    return sorted(paths)


def file_hash(rel_path: str) -> str:
    full_path = os.path.join(PROJECT_ROOT, rel_path)
    if not os.path.exists(full_path) or os.path.isdir(full_path):
        return ""
    digest = hashlib.sha256()
    with open(full_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture_workspace_baseline() -> dict[str, object]:
    status = get_status_porcelain()
    return {
        "sha": get_head_sha(),
        "status": status,
        "hashes": {path: file_hash(path) for path in status},
    }


def changed_files_since_baseline(
    baseline_status: dict[str, str],
    baseline_hashes: dict[str, str],
) -> tuple[list[str], list[str]]:
    current_entries = get_status_entries()
    current_status = {path: code for code, path, _old_path in current_entries}
    current_paths = get_status_paths(include_rename_sources=True)
    changed: set[str] = set()
    unsafe: set[str] = set()

    for _code, path, old_path in current_entries:
        if path not in baseline_status:
            changed.add(path)
        elif file_hash(path) != baseline_hashes.get(path, ""):
            unsafe.add(path)

        if old_path:
            changed.add(old_path)
            if old_path in baseline_status:
                unsafe.add(old_path)

    for path in sorted(baseline_status):
        if path not in current_paths:
            unsafe.add(path)

    return sorted(changed), sorted(unsafe)


def diff_for_paths(base_sha: str, paths: Iterable[str]) -> str:
    tracked_paths = [p for p in paths if not get_status_porcelain().get(p, "").startswith("??")]
    if not tracked_paths:
        return ""
    result = run_git(["diff", base_sha, "--", *tracked_paths], check=False)
    return result.stdout


def file_contents_blocks(paths: Iterable[str]) -> str:
    sections: list[str] = []
    for rel_path in paths:
        full_path = os.path.join(PROJECT_ROOT, rel_path)
        if not os.path.exists(full_path):
            continue
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                sections.append(f"--- FILE: {rel_path} ---\n{f.read()}\n")
        except Exception:
            sections.append(f"--- FILE: {rel_path} --- (unreadable)\n")
    return "\n".join(sections)


def stage_paths(paths: Iterable[str]) -> None:
    unique_paths = sorted({p for p in paths if p})
    if unique_paths:
        run_git(["add", "--", *unique_paths], check=True)


def assert_head_unchanged(expected_sha: str, context: str) -> None:
    current_sha = get_head_sha()
    if current_sha != expected_sha:
        raise RuntimeError(
            f"Git HEAD changed during {context}: expected {expected_sha}, got {current_sha}."
        )


def assert_index_subset(allowed_paths: Iterable[str]) -> None:
    allowed = {p.replace("\\", "/") for p in allowed_paths}
    staged = set(get_staged_paths())
    unexpected = sorted(staged - allowed)
    if unexpected:
        raise RuntimeError(
            "Refusing to commit staged paths outside the task change set: "
            + ", ".join(unexpected)
        )
