import os
import subprocess
import shutil
from orchestrator.state import OrchestratorState
from orchestrator.git_utils import get_head_sha

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.getcwd())
CLAUDE_TIMEOUT = int(os.environ.get("CLAUDE_TIMEOUT", "600"))


def _read_answered_questions() -> str:
    path = os.path.join(PROJECT_ROOT, "questions", "answered_questions.md")
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _parse_context_files(content: str) -> list[str]:
    """Extract the context_files list from YAML frontmatter."""
    if not content.startswith("---"):
        return []
    end = content.find("\n---", 3)
    if end == -1:
        return []
    fm = content[3:end]
    in_context = False
    files: list[str] = []
    for line in fm.splitlines():
        if line.strip().startswith("context_files:"):
            in_context = True
            continue
        if in_context:
            stripped = line.strip()
            if stripped.startswith("-"):
                files.append(stripped[1:].strip().strip("\"'"))
            elif stripped and not stripped.startswith("#"):
                break
    return files


def _load_context_files_for_task(task_file: str) -> str:
    """Read context_files from task frontmatter and return their contents as a block."""
    full_path = os.path.join(PROJECT_ROOT, task_file)
    if not os.path.exists(full_path):
        return ""
    with open(full_path, "r", encoding="utf-8") as f:
        task_content = f.read()
    paths = _parse_context_files(task_content)
    if not paths:
        return ""
    sections = []
    for rel in paths:
        abs_path = os.path.join(PROJECT_ROOT, rel)
        if os.path.exists(abs_path):
            with open(abs_path, "r", encoding="utf-8") as f:
                sections.append(f"### {rel}\n{f.read().strip()}")
    if not sections:
        return ""
    return "Context files specified in task:\n\n" + "\n\n".join(sections) + "\n\n"


def build_with_claude(state: OrchestratorState) -> OrchestratorState:
    """
    Primary builder: invokes Claude Code CLI to implement the current task.
    Does NOT commit — the orchestrator commits only after Gemini review approval.
    """
    if state.get("builder_status") == "failed":
        return state

    task_file = state.get("current_task_file")
    if not task_file:
        state["builder_status"] = "failed"
        state["build_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = "No current_task_file in state"
        return state

    claude_path = shutil.which("claude")
    if not claude_path:
        state["builder_status"] = "failed"
        state["build_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = "claude binary not found in PATH"
        return state

    # Issue 7: prepend reviewer feedback on retry so Claude knows what to fix
    feedback_section = ""
    retry_feedback = state.get("retry_feedback") or state.get("review_feedback")
    if retry_feedback:
        feedback_section = (
            "IMPORTANT — Reviewer feedback from the previous attempt that must be addressed:\n"
            f"{retry_feedback}\n\n"
        )

    # include answered questions as additional context
    answered = _read_answered_questions()
    answered_section = (
        f"Context — previously answered clarifying questions:\n{answered}\n\n"
        if answered else ""
    )

    # Load only context_files from task frontmatter; fall back to full specs/ dir instruction
    context_section = _load_context_files_for_task(task_file)
    if context_section:
        specs_instruction = f"Loaded context files are provided above — use them as your primary reference.\n"
    else:
        specs_instruction = f"Before implementing, read {PROJECT_ROOT}/specs/ for architecture and requirements.\n"

    prompt = (
        f"{feedback_section}"
        f"{answered_section}"
        f"{context_section}"
        f"You are the implementation agent for this repository.\n"
        f"Workspace: {PROJECT_ROOT}\n"
        f"Task file: {os.path.join(PROJECT_ROOT, task_file)}\n"
        f"\n"
        f"{specs_instruction}"
        f"\n"
        f"Rules:\n"
        f"- Implement only what the task describes — do not touch unrelated files\n"
        f"- Follow the architecture and specs in /specs/\n"
        f"- Keep changes minimal, coherent, and well-organized\n"
        f"- Write a brief implementation summary to {PROJECT_ROOT}/reports/session-report.md\n"
        f"- Do NOT create a git commit — the orchestrator commits only after review approval\n"
    )

    env = os.environ.copy()
    env["CLAUDE_CODE_BUBBLEWRAP"] = "1"

    try:
        head_before = get_head_sha()
        result = subprocess.run(
            [claude_path, "--dangerously-skip-permissions"],
            input=prompt,
            text=True,
            capture_output=True,
            cwd=PROJECT_ROOT,
            env=env,
            timeout=CLAUDE_TIMEOUT,
        )

        state["claude_stdout"] = result.stdout
        state["claude_stderr"] = result.stderr

        head_after = get_head_sha()
        if head_after != head_before:
            state["builder_status"] = "policy_violation"
            state["build_status"] = "policy_violation"
            state["task_status"] = "failed"
            state["policy_violation"] = "builder_commit"
            state["last_error"] = (
                "Builder created a git commit. Builders must leave commits to the orchestrator."
            )
            return state

        if result.returncode == 0:
            state["builder_status"] = "success"
            state["build_status"] = "success"
        else:
            state["builder_status"] = "failed"
            state["build_status"] = "failed"
            state["task_status"] = "failed"
            state["last_error"] = f"Claude CLI exited with code {result.returncode}"

    except subprocess.TimeoutExpired:
        state["builder_status"] = "failed"
        state["build_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = f"Claude CLI timed out after {CLAUDE_TIMEOUT}s"
    except Exception as e:
        state["builder_status"] = "failed"
        state["build_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = str(e)

    return state
