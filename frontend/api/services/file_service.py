"""
File service: all file I/O for the AI Factory UI backend.

_has_substantive_content() is replicated verbatim from run_graph.py to ensure
strict compatibility with the orchestrator's question-detection logic.
"""
import glob
import os
import re

PROJECT_ROOT: str = os.environ.get("PROJECT_ROOT", "/workspace")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_substantive_content(text: str) -> bool:
    """
    Language-agnostic check: True if the text has non-empty lines that are
    not Markdown headings (#) or HTML comments (<!--).
    Replicated verbatim from run_graph.py to ensure exact compatibility.
    """
    ignored_fragments = (
        "lassen sie diese datei leer",
        "leave this file empty",
    )
    for line in text.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
            continue
        if any(fragment in lower for fragment in ignored_fragments):
            continue
        if stripped:
            return True
    return False


def _read_file(path: str, default: str = "") -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return default


# ---------------------------------------------------------------------------
# Dashboard / Reports
# ---------------------------------------------------------------------------

def get_report_content() -> dict:
    report_path = os.path.join(PROJECT_ROOT, "reports", "run-report.md")
    session_path = os.path.join(PROJECT_ROOT, "reports", "session-report.md")

    report_content = _read_file(report_path)
    session_report = _read_file(session_path)

    # Extract the last timestamped entry (lines from the last timestamp block onwards)
    last_entry = ""
    if report_content:
        lines = report_content.splitlines()
        last_block_start = 0
        for i, line in enumerate(lines):
            if line.startswith("[") and "] Run" in line:
                last_block_start = i
        last_entry = "\n".join(lines[last_block_start:]).strip()

    return {
        "report_content": report_content,
        "last_entry": last_entry,
        "session_report": session_report,
    }


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

TERMINAL_MARKERS = {
    ".done.": "done",
    ".failed.": "failed",
    ".blocked.": "blocked",
}


def _task_status(filename: str) -> str:
    for marker, status in TERMINAL_MARKERS.items():
        if marker in filename:
            return status
    return "open"


def _display_name(filename: str) -> str:
    # Remove status marker + extension: "01_setup.done.md" → "01 setup"
    name = re.sub(r"\.(done|failed|blocked)?\.md$", "", filename)
    name = re.sub(r"\.md$", "", name)
    return name.replace("_", " ")


def list_tasks() -> list:
    pattern = os.path.join(PROJECT_ROOT, "tasks", "*.md")
    files = sorted(glob.glob(pattern))
    result = []
    for f in files:
        basename = os.path.basename(f)
        if basename == ".gitkeep":
            continue
        result.append({
            "filename": basename,
            "display_name": _display_name(basename),
            "status": _task_status(basename),
            "path": f"tasks/{basename}",
        })
    return result


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------

def get_questions() -> dict:
    open_path = os.path.join(PROJECT_ROOT, "questions", "open_questions.md")
    answered_path = os.path.join(PROJECT_ROOT, "questions", "answered_questions.md")

    open_content = _read_file(open_path)
    answered_content = _read_file(answered_path)

    return {
        "open_questions": open_content,
        "has_questions": _has_substantive_content(open_content),
        "answered_questions": answered_content,
    }


def save_answer(answer: str) -> str:
    """
    Appends the answer to answered_questions.md and resets open_questions.md.
    Format matches run_graph.py:check_and_prompt_questions() exactly.
    Returns the archived question content.

    Raises ValueError if the answer is empty.
    Raises LookupError if there are no open questions.
    """
    if not answer.strip():
        raise ValueError("answer must not be empty")

    open_path = os.path.join(PROJECT_ROOT, "questions", "open_questions.md")
    answered_path = os.path.join(PROJECT_ROOT, "questions", "answered_questions.md")

    open_content = _read_file(open_path).strip()
    if not _has_substantive_content(open_content):
        raise LookupError("no open questions to answer")

    # Append to answered_questions.md — exact format from run_graph.py
    os.makedirs(os.path.dirname(answered_path), exist_ok=True)
    with open(answered_path, "a", encoding="utf-8") as af:
        af.write(f"\n## Q:\n{open_content}\n## A:\n{answer}\n")

    # Reset open_questions.md — language-agnostic empty state from run_graph.py
    with open(open_path, "w", encoding="utf-8") as f:
        f.write("# Open Questions\n")

    return open_content
