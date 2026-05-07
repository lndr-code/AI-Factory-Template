from __future__ import annotations

import hashlib
import json
import os
from typing import Any


class ReadReceiptError(ValueError):
    """Raised when required-read files cannot be hashed or persisted."""


def build_read_receipt(
    target_root: str,
    required_files: tuple[str, ...],
) -> dict[str, str]:
    """Return SHA256 hashes for required target files, keyed by relative path."""
    root = os.path.abspath(target_root)
    hashes: dict[str, str] = {}

    for rel_path in required_files:
        normalized = _slash_path(rel_path)
        full_path = os.path.abspath(os.path.join(root, normalized))
        if not _is_within(full_path, root):
            raise ReadReceiptError(f"Required-read file escapes TARGET_ROOT: {normalized}")
        if not os.path.isfile(full_path):
            raise ReadReceiptError(f"Required-read file not found: {normalized}")
        hashes[normalized] = _sha256_file(full_path)

    return hashes


def write_read_receipt(
    run_dir: str,
    receipt: dict[str, Any],
) -> str:
    """Write read_receipt.json into run_dir and return its absolute path."""
    os.makedirs(run_dir, exist_ok=True)
    path = os.path.abspath(os.path.join(run_dir, "read_receipt.json"))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, sort_keys=True)
        f.write("\n")
    return path


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _slash_path(path: str) -> str:
    return path.replace("\\", "/")
