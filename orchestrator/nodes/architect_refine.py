import os
import glob
from orchestrator.state import OrchestratorState
from orchestrator.llm.roles import invoke_architect
from orchestrator.file_blocks import copy_tree_contents, reset_directory
from orchestrator.nodes.architect_agent import (
    PLANNING_DRAFT_DIR,
    _draft_open_questions_are_substantive,
    _publish_draft_questions,
    _read_answered_questions,
    write_planning_draft,
)

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.getcwd())


def _clear_open_tasks() -> None:
    tasks_dir = os.path.join(PROJECT_ROOT, "tasks")
    os.makedirs(tasks_dir, exist_ok=True)
    for task_path in glob.glob(os.path.join(tasks_dir, "*.md")):
        basename = os.path.basename(task_path)
        if basename == ".gitkeep" or ".done." in basename or ".failed." in basename or ".blocked." in basename:
            continue
        os.remove(task_path)


def _list_files(src_dir: str) -> list[str]:
    files: list[str] = []
    if not os.path.exists(src_dir):
        return files
    for root, _, filenames in os.walk(src_dir):
        for filename in filenames:
            files.append(os.path.relpath(os.path.join(root, filename), src_dir).replace("\\", "/"))
    return files


def _publish_refined_plan() -> list[str]:
    published: list[str] = []
    specs_src = os.path.join(PLANNING_DRAFT_DIR, "specs")
    tasks_src = os.path.join(PLANNING_DRAFT_DIR, "tasks")
    questions_src = os.path.join(PLANNING_DRAFT_DIR, "questions")

    spec_files = _list_files(specs_src)
    task_files = _list_files(tasks_src)
    if "architecture.md" not in spec_files:
        raise RuntimeError("Refined plan did not include specs/architecture.md.")
    if not any(path.endswith(".md") for path in task_files):
        raise RuntimeError("Refined plan did not include any task .md files.")

    published.extend(f"specs/{p}" for p in copy_tree_contents(specs_src, os.path.join(PROJECT_ROOT, "specs")))

    _clear_open_tasks()
    published.extend(f"tasks/{p}" for p in copy_tree_contents(tasks_src, os.path.join(PROJECT_ROOT, "tasks")))

    if os.path.exists(questions_src):
        published.extend(f"questions/{p}" for p in copy_tree_contents(questions_src, os.path.join(PROJECT_ROOT, "questions")))

    reset_directory(PLANNING_DRAFT_DIR)
    return published


def architect_refine(state: OrchestratorState) -> OrchestratorState:
    """
    Architect Refinement: incorporates the Critic's feedback to produce an improved,
    consolidated architecture and task structure.
    Uses Gemini Pro (same role as initial architect, configurable via GEMINI_ARCHITECT_MODEL).
    """
    spec_path = os.path.join(PROJECT_ROOT, "specs", "product_spec.md")
    draft_arch_path = os.path.join(PLANNING_DRAFT_DIR, "specs", "architecture.md")
    arch_path = draft_arch_path if os.path.exists(draft_arch_path) else os.path.join(PROJECT_ROOT, "specs", "architecture.md")
    critic_feedback = state.get("critic_feedback", "")

    try:
        with open(spec_path, "r", encoding="utf-8") as f:
            spec_content = f.read()
    except Exception as e:
        state["builder_status"] = "failed"
        state["planning_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = f"Could not read product spec for refinement: {e}"
        return state

    current_arch = ""
    if os.path.exists(arch_path):
        with open(arch_path, "r", encoding="utf-8") as f:
            current_arch = f.read()

    answered = _read_answered_questions()
    answered_section = (
        f"\n\nPreviously answered clarifying questions:\n{answered}\n"
        if answered else ""
    )

    prompt = f"""You are the Lead Architect. You previously produced an initial architecture and task plan.
A senior critic has now reviewed your plan and provided specific feedback. Your job is to incorporate
that feedback and produce an improved, consolidated architecture and task plan.

Original Product Spec:
{spec_content}

Your Initial Architecture:
{current_arch}

Critic Feedback:
{critic_feedback}
{answered_section}
Instructions:
- Keep what the critic confirmed as solid
- Fix what the critic flagged as problematic
- Add missing tasks, clarify ambiguous ones, reorder if dependencies were wrong
- Do not over-engineer — stay focused on what the spec requires
- Every task must still be self-contained, ordered by dependency, and clearly scoped

Output each updated file using exactly:
---FILE: path/relative/to/project---
content
---ENDFILE---

Produce at minimum:
- specs/architecture.md (updated, improved version)
- All task files tasks/01_*.md, tasks/02_*.md, ... (revised as needed — rewrite the full set)
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
                "Architect refinement produced no parseable file blocks in its response."
            )
        elif _draft_open_questions_are_substantive():
            _publish_draft_questions()
            state["builder_status"] = "success"
            state["planning_status"] = "awaiting_input"
            state["task_status"] = "awaiting_input"
            state["last_error"] = (
                "Architect refinement produced open questions. Answer them before tasks are published."
            )
        else:
            published = _publish_refined_plan()
            state["builder_status"] = "success"
            state["planning_status"] = "published"
            state["task_status"] = "planned"
            state["planning_files"] = published
    except ValueError as e:
        state["builder_status"] = "failed"
        state["planning_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = str(e)
    except Exception as e:
        state["builder_status"] = "failed"
        state["planning_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = f"Architect refinement failed: {e}"

    return state
