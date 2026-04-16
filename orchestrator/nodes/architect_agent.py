import os
from orchestrator.state import OrchestratorState
from orchestrator.llm.roles import invoke_architect
from orchestrator.file_blocks import copy_tree_contents, reset_directory, write_file_blocks

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.getcwd())
PLANNING_DRAFT_DIR = os.path.join(PROJECT_ROOT, ".agent", "planning_draft")
PLANNING_ALLOWED_ROOTS = ("specs", "tasks", "questions")

_TEMPLATE_MARKERS = [
    "Ersetze diese Datei",
    "replace this file",
    "describe your product here",
]


def _spec_is_template(content: str) -> bool:
    """Return True if the spec still contains placeholder text from the template."""
    lower = content.lower()
    return any(m.lower() in lower for m in _TEMPLATE_MARKERS)


def _read_answered_questions() -> str:
    """Return answered_questions.md content, or empty string if not present."""
    path = os.path.join(PROJECT_ROOT, "questions", "answered_questions.md")
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _has_substantive_content(text: str) -> bool:
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
        return True
    return False


def _draft_open_questions_are_substantive() -> bool:
    path = os.path.join(PLANNING_DRAFT_DIR, "questions", "open_questions.md")
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        return _has_substantive_content(f.read())


def _publish_draft_questions() -> None:
    src_dir = os.path.join(PLANNING_DRAFT_DIR, "questions")
    dst_dir = os.path.join(PROJECT_ROOT, "questions")
    copy_tree_contents(src_dir, dst_dir)


def write_planning_draft(response_text: str, reset: bool = False) -> list[str]:
    if reset:
        reset_directory(PLANNING_DRAFT_DIR)
    return write_file_blocks(response_text, PLANNING_DRAFT_DIR, PLANNING_ALLOWED_ROOTS)


def architect_agent(state: OrchestratorState) -> OrchestratorState:
    """
    Lead Architect: translates product_spec.md into architecture and task files.
    Uses Gemini Pro (configurable via GEMINI_ARCHITECT_MODEL).
    """
    spec_path = os.path.join(PROJECT_ROOT, "specs", "product_spec.md")

    if not os.path.exists(spec_path):
        state["builder_status"] = "failed"
        state["last_error"] = (
            f"Product spec not found at {spec_path}. "
            "Create specs/product_spec.md before running the orchestrator."
        )
        state["planning_status"] = "failed"
        state["task_status"] = "failed"
        return state

    with open(spec_path, "r", encoding="utf-8") as f:
        spec_content = f.read()

    if _spec_is_template(spec_content):
        state["builder_status"] = "failed"
        state["planning_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = (
            "specs/product_spec.md still contains template placeholder text. "
            "Edit the file to describe your actual product before running."
        )
        return state

    missing_keys = []
    if not os.environ.get("GEMINI_API_KEY"):
        missing_keys.append("GEMINI_API_KEY")
    if not os.environ.get("OPENAI_API_KEY"):
        missing_keys.append("OPENAI_API_KEY")
    if missing_keys:
        state["builder_status"] = "failed"
        state["planning_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = "Missing required planning API key(s): " + ", ".join(missing_keys)
        return state

    answered = _read_answered_questions()
    answered_section = (
        f"\n\nPreviously answered clarifying questions:\n{answered}\n"
        if answered else ""
    )

    prompt = f"""You are a Lead Architect. Read the following product_spec.md and produce:
1. specs/architecture.md — tech stack, directory structure, data model, key decisions
2. Numbered task files in tasks/ (e.g. tasks/01_setup.md, tasks/02_api.md)
   Each task must be:
   - Self-contained and scoped to one coherent unit of work
   - Ordered by dependency (earlier tasks must not depend on later ones)
   - Detailed enough for a developer to implement without ambiguity
3. If genuine ambiguities exist in the spec, write them to questions/open_questions.md
{answered_section}
Output each file using exactly this block format:
---FILE: path/relative/to/project---
content
---ENDFILE---

Product Spec:
{spec_content}
"""

    try:
        response_text = invoke_architect(prompt)
        written_files = write_planning_draft(response_text, reset=True)
        state["planning_files"] = written_files
        if not written_files:
            state["builder_status"] = "failed"
            state["planning_status"] = "failed"
            state["task_status"] = "failed"
            state["last_error"] = (
                "Architect agent produced no parseable file blocks in its response."
            )
        elif _draft_open_questions_are_substantive():
            _publish_draft_questions()
            state["builder_status"] = "success"
            state["planning_status"] = "awaiting_input"
            state["task_status"] = "awaiting_input"
            state["last_error"] = (
                "Architect produced open questions. Answer them before tasks are published."
            )
        else:
            state["builder_status"] = "success"
            state["planning_status"] = "draft_created"
            state["task_status"] = "planning"
    except ValueError as e:
        state["builder_status"] = "failed"
        state["planning_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = str(e)
    except Exception as e:
        state["builder_status"] = "failed"
        state["planning_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = f"Architect agent failed: {e}"

    return state
