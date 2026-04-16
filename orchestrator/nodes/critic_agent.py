import os
import glob
from orchestrator.state import OrchestratorState
from orchestrator.llm.roles import invoke_critic
from orchestrator.nodes.architect_agent import PLANNING_DRAFT_DIR

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.getcwd())


def _read_architecture() -> str:
    draft_arch = os.path.join(PLANNING_DRAFT_DIR, "specs", "architecture.md")
    arch_path = draft_arch if os.path.exists(draft_arch) else os.path.join(PROJECT_ROOT, "specs", "architecture.md")
    if not os.path.exists(arch_path):
        return "(architecture.md not found)"
    with open(arch_path, "r", encoding="utf-8") as f:
        return f.read()


def _read_tasks() -> str:
    draft_tasks_dir = os.path.join(PLANNING_DRAFT_DIR, "tasks")
    tasks_dir = draft_tasks_dir if os.path.exists(draft_tasks_dir) else os.path.join(PROJECT_ROOT, "tasks")
    task_files = sorted(glob.glob(os.path.join(tasks_dir, "*.md")))
    sections = []
    for tf in task_files:
        basename = os.path.basename(tf)
        if basename == ".gitkeep" or any(marker in basename for marker in (".done.", ".failed.", ".blocked.")):
            continue
        with open(tf, "r", encoding="utf-8") as f:
            sections.append(f"--- {basename} ---\n{f.read()}")
    return "\n\n".join(sections) if sections else "(no task files found)"


def critic_agent(state: OrchestratorState) -> OrchestratorState:
    """
    GPT-5 Critic: reviews the Architect's initial plan for structural weaknesses,
    gaps, and risks before any implementation begins.
    Uses OpenAI (configurable via OPENAI_CRITIC_MODEL).
    """
    architecture = _read_architecture()
    tasks = _read_tasks()

    prompt = f"""You are a senior technical critic reviewing an AI-generated software architecture and task plan.

Your job is to identify structural weaknesses BEFORE implementation begins — things the developer would discover too late to fix cheaply.

Analyze the following architecture and task list for:
1. Unclear assumptions or missing context that could block implementation
2. Missing edge cases or error paths that are not captured in any task
3. Technical risks (scalability, security, data integrity, coupling)
4. Missing requirements not reflected in any task
5. Task ordering issues (wrong dependencies, missing prerequisite tasks)
6. Oversimplified or underspecified tasks that will cause builder confusion
7. Architectural decisions that may be hard to reverse later

Architecture:
{architecture}

Task Plan:
{tasks}

Respond with a structured critique. For each issue:
- Describe the problem clearly and specifically
- Explain why it matters for implementation
- Suggest a concrete resolution

If the plan is solid, say so clearly — do not invent problems where none exist.

End your response with exactly this line:
CRITIC_SUMMARY: [one-paragraph overall assessment: strong / acceptable / needs significant rework]
"""

    try:
        response_text = invoke_critic(prompt)
        state["critic_feedback"] = response_text
        state["critic_status"] = "completed"
        state["builder_status"] = "success"
    except ValueError as e:
        state["critic_status"] = "failed"
        state["planning_status"] = "failed"
        state["task_status"] = "failed"
        state["builder_status"] = "failed"
        state["last_error"] = str(e)
    except Exception as e:
        state["critic_status"] = "failed"
        state["planning_status"] = "failed"
        state["task_status"] = "failed"
        state["builder_status"] = "failed"
        state["last_error"] = f"Critic agent failed: {e}"

    return state
