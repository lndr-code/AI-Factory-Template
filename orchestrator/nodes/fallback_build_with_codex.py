import os
from orchestrator.state import OrchestratorState
from orchestrator.file_blocks import write_file_blocks

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.getcwd())
FALLBACK_BUILDER_ALLOWED_ROOTS = tuple(
    root.strip()
    for root in os.environ.get(
        "BUILDER_FILE_ALLOWED_ROOTS",
        "app,src,tests,test,public,assets,static,docs",
    ).split(",")
    if root.strip()
)
FALLBACK_BUILDER_PROTECTED_ROOTS = (".git", ".agent", "orchestrator")
FALLBACK_BUILDER_PROTECTED_PATHS = (
    ".gitignore",
    ".env",
    ".env.example",
    "run_graph.py",
    "Dockerfile",
    "docker-compose.yml",
    "entrypoint.sh",
    "requirements.txt",
)


def fallback_build_with_codex(state: OrchestratorState) -> OrchestratorState:
    """
    Optional fallback builder using the OpenAI API (GPT-4o or configured model).
    Only active when CODEX_ENABLED=true is set in the environment.

    Note (interim): This fallback uses a file-block protocol (---FILE: ... ---ENDFILE---)
    to receive file contents from the model. This is not equivalent to the Claude Code CLI
    agentic loop — it is a pragmatic degraded fallback. A proper OpenAI Assistants API
    integration is a future improvement.
    """
    if os.environ.get("CODEX_ENABLED", "false").lower() != "true":
        state["builder_status"] = "failed"
        state["build_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = (
            "Codex fallback is disabled. "
            "Set CODEX_ENABLED=true and provide OPENAI_API_KEY to enable it."
        )
        return state

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        state["builder_status"] = "failed"
        state["build_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = "CODEX_ENABLED=true but OPENAI_API_KEY is not set."
        return state

    task_file = state.get("current_task_file", "")
    task_content = ""
    if task_file:
        try:
            with open(os.path.join(PROJECT_ROOT, task_file), "r", encoding="utf-8") as f:
                task_content = f.read()
        except Exception:
            pass

    try:
        from openai import OpenAI  # deferred import — only needed when fallback is enabled

        client = OpenAI(api_key=api_key)
        model = os.environ.get("OPENAI_BUILDER_MODEL", "gpt-4o")

        prompt = (
            f"You are a fallback implementation agent for this repository.\n"
            f"Workspace: {PROJECT_ROOT}\n"
            f"\n"
            f"Task to implement:\n"
            f"{task_content}\n"
            f"\n"
            f"Before implementing, read {PROJECT_ROOT}/specs/ for architecture and requirements.\n"
            f"\n"
            f"Rules:\n"
            f"- Follow the architecture and specs in /specs/\n"
            f"- Keep changes minimal and coherent\n"
            f"- Write files only under: {', '.join(FALLBACK_BUILDER_ALLOWED_ROOTS)}\n"
            f"- Write a brief summary to {PROJECT_ROOT}/reports/session-report.md\n"
            f"- Do NOT create a git commit — the orchestrator commits only after review approval\n"
            f"\n"
            f"Output every file you create or modify using exactly this format:\n"
            f"---FILE: path/relative/to/project---\n"
            f"content\n"
            f"---ENDFILE---\n"
        )

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = response.choices[0].message.content or ""

        # The fallback model can only write application files by default. Template
        # runtime and orchestrator files remain protected even if the allowlist is widened.
        written_files = write_file_blocks(
            response_text,
            PROJECT_ROOT,
            FALLBACK_BUILDER_ALLOWED_ROOTS,
            FALLBACK_BUILDER_PROTECTED_ROOTS,
            FALLBACK_BUILDER_PROTECTED_PATHS,
        )
        files_written = len(written_files)

        state["codex_stdout"] = f"Files written: {files_written}"

        if files_written > 0:
            state["builder_status"] = "success"
            state["build_status"] = "success"
        else:
            state["builder_status"] = "failed"
            state["build_status"] = "failed"
            state["task_status"] = "failed"
            state["last_error"] = "Codex fallback produced no parseable file blocks."

    except Exception as e:
        state["builder_status"] = "failed"
        state["build_status"] = "failed"
        state["task_status"] = "failed"
        state["last_error"] = f"Codex fallback failed: {e}"

    return state
