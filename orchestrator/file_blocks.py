import os
import shutil


PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.getcwd())
DEFAULT_PROTECTED_ROOTS = (".git",)
DEFAULT_PROTECTED_PATHS: tuple[str, ...] = ()


class FileBlockError(ValueError):
    pass


def _matches_root(path: str, roots: tuple[str, ...]) -> bool:
    return any(path == root.rstrip("/") or path.startswith(root.rstrip("/") + "/") for root in roots)


def _matches_path(path: str, paths: tuple[str, ...]) -> bool:
    return any(path == protected.rstrip("/") for protected in paths)


def normalize_relative_path(
    path: str,
    allowed_roots: tuple[str, ...],
    protected_roots: tuple[str, ...] = DEFAULT_PROTECTED_ROOTS,
    protected_paths: tuple[str, ...] = DEFAULT_PROTECTED_PATHS,
) -> str:
    raw_path = path.strip().replace("\\", "/")
    if not raw_path:
        raise FileBlockError("Empty file path in LLM file block.")
    if os.path.isabs(raw_path) or ":" in raw_path:
        raise FileBlockError(f"Absolute paths are not allowed: {path}")

    normalized = os.path.normpath(raw_path).replace("\\", "/")
    if normalized == "." or normalized.startswith("../") or normalized == "..":
        raise FileBlockError(f"Path traversal is not allowed: {path}")
    if _matches_root(normalized, protected_roots) or _matches_path(normalized, protected_paths):
        raise FileBlockError(f"Writing to protected path is not allowed: {normalized}")

    if "*" in allowed_roots:
        return normalized

    if not _matches_root(normalized, allowed_roots):
        allowed = ", ".join(allowed_roots)
        raise FileBlockError(f"Path {normalized} is outside allowed roots: {allowed}")

    return normalized


def parse_file_blocks(
    response_text: str,
    allowed_roots: tuple[str, ...],
    protected_roots: tuple[str, ...] = DEFAULT_PROTECTED_ROOTS,
    protected_paths: tuple[str, ...] = DEFAULT_PROTECTED_PATHS,
) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for part in response_text.split("---FILE: "):
        if not part.strip() or "---ENDFILE---" not in part:
            continue
        main_content = part.split("---ENDFILE---", 1)[0].strip()
        lines = main_content.split("\n", 1)
        if len(lines) < 2:
            continue
        rel_path = normalize_relative_path(
            lines[0].split("---", 1)[0],
            allowed_roots,
            protected_roots,
            protected_paths,
        )
        content = lines[1].strip() + "\n"
        blocks.append((rel_path, content))
    return blocks


def write_file_blocks(
    response_text: str,
    base_dir: str,
    allowed_roots: tuple[str, ...],
    protected_roots: tuple[str, ...] = DEFAULT_PROTECTED_ROOTS,
    protected_paths: tuple[str, ...] = DEFAULT_PROTECTED_PATHS,
) -> list[str]:
    written: list[str] = []
    base_abs = os.path.realpath(base_dir)
    for rel_path, content in parse_file_blocks(
        response_text,
        allowed_roots,
        protected_roots,
        protected_paths,
    ):
        full_path = os.path.realpath(os.path.join(base_abs, rel_path))
        if os.path.commonpath([base_abs, full_path]) != base_abs:
            raise FileBlockError(f"Resolved path escapes base directory: {rel_path}")
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        written.append(rel_path)
    return written


def reset_directory(path: str) -> None:
    root_abs = os.path.realpath(PROJECT_ROOT)
    path_abs = os.path.realpath(path)
    if os.path.commonpath([root_abs, path_abs]) != root_abs:
        raise FileBlockError(f"Refusing to reset directory outside project: {path}")
    if os.path.exists(path_abs):
        shutil.rmtree(path_abs)
    os.makedirs(path_abs, exist_ok=True)


def copy_tree_contents(src_dir: str, dst_dir: str) -> list[str]:
    copied: list[str] = []
    if not os.path.exists(src_dir):
        return copied
    src_abs = os.path.realpath(src_dir)
    dst_abs = os.path.realpath(dst_dir)
    for root, _, files in os.walk(src_dir):
        for filename in files:
            src_path = os.path.join(root, filename)
            src_real = os.path.realpath(src_path)
            if os.path.commonpath([src_abs, src_real]) != src_abs:
                raise FileBlockError(f"Refusing to copy file outside source tree: {src_path}")
            rel_path = os.path.relpath(src_path, src_dir).replace("\\", "/")
            dst_path = os.path.realpath(os.path.join(dst_abs, rel_path))
            if os.path.commonpath([dst_abs, dst_path]) != dst_abs:
                raise FileBlockError(f"Refusing to copy file outside destination tree: {rel_path}")
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            shutil.copyfile(src_real, dst_path)
            copied.append(rel_path)
    return copied
