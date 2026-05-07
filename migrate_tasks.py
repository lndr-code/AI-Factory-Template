#!/usr/bin/env python3
"""
migrate_tasks.py — Einmalige Migration von .done.md-Dateien auf YAML-status SSOT.

Wandelt alle tasks/*.done.md (und *.failed.md, *.blocked.md) um in:
  - tasks/01_setup.md  (Datei ohne Terminal-Marker im Namen)
  - YAML-Frontmatter: status: done | failed | blocked

Lauf: python migrate_tasks.py [--dry-run]
"""
import os
import sys
import glob
import re

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
TASKS_DIR = os.path.join(PROJECT_ROOT, "tasks")

MARKER_STATUS_MAP = {
    ".done.": "done",
    ".failed.": "failed",
    ".blocked.": "blocked",
}


def _detect_marker(basename: str) -> tuple[str, str] | None:
    """Return (marker, status) if a terminal marker is found in the filename."""
    for marker, status in MARKER_STATUS_MAP.items():
        if marker in basename:
            return marker, status
    return None


def _clean_filename(basename: str, marker: str) -> str:
    """Remove the terminal marker from the filename."""
    return basename.replace(marker, ".")


def _patch_frontmatter_status(content: str, new_status: str) -> str:
    """Set or add status field in YAML frontmatter."""
    if not content.startswith("---"):
        return f"---\nstatus: {new_status}\n---\n{content}"
    end = content.find("\n---", 3)
    if end == -1:
        return content
    fm = content[3:end]
    rest = content[end:]
    if re.search(r"^status:", fm, re.MULTILINE):
        fm = re.sub(r"^status:.*$", f"status: {new_status}", fm, flags=re.MULTILINE)
    else:
        fm = fm.rstrip("\n") + f"\nstatus: {new_status}\n"
    return f"---{fm}{rest}"


def migrate(dry_run: bool = False) -> None:
    task_files = glob.glob(os.path.join(TASKS_DIR, "*.md"))
    migrated = 0

    for path in sorted(task_files):
        basename = os.path.basename(path)
        result = _detect_marker(basename)
        if not result:
            continue

        marker, status = result
        new_basename = _clean_filename(basename, marker)
        new_path = os.path.join(TASKS_DIR, new_basename)

        if os.path.exists(new_path):
            print(f"  SKIP  {basename} → target {new_basename} already exists")
            continue

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        patched = _patch_frontmatter_status(content, status)

        print(f"  {'DRY ' if dry_run else ''}MIGRATE  {basename} → {new_basename}  (status: {status})")
        if not dry_run:
            with open(new_path, "w", encoding="utf-8") as f:
                f.write(patched)
            os.remove(path)

        migrated += 1

    print(f"\n{'[dry-run] ' if dry_run else ''}Migriert: {migrated} Datei(en).")
    if dry_run and migrated:
        print("Führe ohne --dry-run aus, um die Migration anzuwenden.")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    migrate(dry_run=dry_run)
