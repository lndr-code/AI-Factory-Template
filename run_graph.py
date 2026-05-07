"""
AI Factory Orchestrator - Task Runner

Usage:
    # Run all open tasks from /tasks/ in sorted order:
    python run_graph.py

    # Run a single specific task:
    python run_graph.py --task tasks/01_setup.md

Tasks marked as terminal (filename contains '.done.', '.failed.', or '.blocked.') are skipped.
"""
import argparse
import os
import glob

from orchestrator.external.builder import ExternalBuilderError, run_external_builder
from orchestrator.external.runner import ExternalRunnerError, run_external_preflight

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.getcwd())
TERMINAL_TASK_MARKERS = {
    ".done.": "done",
    ".failed.": "failed",
    ".blocked.": "blocked",
}


def task_lifecycle_status(task_file: str) -> str | None:
    basename = os.path.basename(task_file)
    for marker, status in TERMINAL_TASK_MARKERS.items():
        if marker in basename:
            return status
    return None


def find_open_tasks() -> list[str]:
    """Find all task .md files, sorted by filename, skipping terminal lifecycle files."""
    tasks_dir = os.path.join(PROJECT_ROOT, "tasks")
    all_tasks = sorted(glob.glob(os.path.join(tasks_dir, "*.md")))
    open_tasks = [
        os.path.relpath(t, PROJECT_ROOT).replace("\\", "/")
        for t in all_tasks
        if task_lifecycle_status(t) is None
        and os.path.basename(t) != ".gitkeep"
    ]
    return open_tasks


def run_task(task_file: str):
    print(f"\n{'='*60}")
    print(f"  Running task: {task_file}")
    print(f"{'='*60}")
    terminal_status = task_lifecycle_status(task_file)
    if terminal_status:
        result = {
            "current_task_file": task_file,
            "task_status": terminal_status,
            "final_report": f"Task already marked as {terminal_status}: {task_file}",
        }
        print(f"\n  Result: {result['final_report']}")
        return result
    from orchestrator.graph import app

    result = app.invoke({"current_task_file": task_file})
    print(f"\n  Result: {result.get('final_report', 'No report generated.')}")
    return result


def _has_substantive_content(text: str) -> bool:
    """
    Language-agnostic check: True if the text has non-empty lines that are
    not Markdown headings (#) or HTML comments (<!--).
    Replaces the previous hardcoded German sentinel string check.
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


def check_and_prompt_questions() -> bool:
    questions_file = os.path.join(PROJECT_ROOT, "questions", "open_questions.md")
    if not os.path.exists(questions_file):
        return False
    with open(questions_file, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if not _has_substantive_content(content):
        return False
    print(f"\n[?] The agents have asked questions:\n{content}\n")
    answers = input("Please provide answers (or press Enter to skip): ")
    if answers.strip():
        answers_file = os.path.join(PROJECT_ROOT, "questions", "answered_questions.md")
        os.makedirs(os.path.dirname(answers_file), exist_ok=True)
        with open(answers_file, "a", encoding="utf-8") as af:
            af.write(f"\n## Q:\n{content}\n## A:\n{answers}\n")
        # Reset open_questions.md — language-agnostic empty state
        with open(questions_file, "w", encoding="utf-8") as f:
            f.write("# Open Questions\n")
        return True
    else:
        print("Skipping answers for now.")
        return False


def main():
    parser = argparse.ArgumentParser(description="AI Factory Orchestrator Task Runner")
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="Path to a specific task file relative to PROJECT_ROOT (e.g. tasks/01_setup.md). "
             "If not provided, all open tasks are run in sorted order.",
    )
    parser.add_argument(
        "--external-target",
        type=str,
        default=None,
        help="Run External Mode preflight for a configured target (e.g. idp_pipeline).",
    )
    parser.add_argument(
        "--target-root",
        type=str,
        default=None,
        help="External target checkout path. Defaults to TARGET_ROOT or FACTORY_ROOT/external_targets/<target>.",
    )
    parser.add_argument(
        "--factory-root",
        type=str,
        default=None,
        help="AI Factory root. Defaults to FACTORY_ROOT or the current working directory.",
    )
    parser.add_argument(
        "--external-preflight-only",
        action="store_true",
        help="Run only External Mode open-target and read-receipt checks.",
    )
    parser.add_argument(
        "--external-build",
        action="store_true",
        help="After External Mode preflight, run the configured external builder and then stop before review/validation/patch.",
    )
    parser.add_argument(
        "--external-builder",
        choices=("claude", "codex"),
        default=None,
        help="Override the manifest primary builder for External Mode builds.",
    )
    args = parser.parse_args()

    if args.external_target:
        try:
            result = run_external_preflight(
                target_name=args.external_target,
                factory_root=args.factory_root,
                target_root=args.target_root,
            )
            if args.external_build:
                if not args.task:
                    raise ExternalBuilderError("--external-build requires --task")
                result = run_external_builder(
                    result,
                    task_file=args.task,
                    builder=args.external_builder,
                )
        except ExternalRunnerError as e:
            print(f"External preflight failed: {e}")
            raise SystemExit(1) from e
        except ExternalBuilderError as e:
            print(f"External builder failed: {e}")
            raise SystemExit(1) from e

        if args.external_build:
            print("External build complete.")
            print(f"  Builder:  {result['external_builder']}")
            print(f"  Status:   {result['builder_status']}")
            if result.get("policy_violation"):
                print(f"  Policy:   {result['policy_violation']}")
            print(f"  Report:   {result['external_builder_report_path']}")
        else:
            print("External preflight complete.")
        print(f"  Target:   {result['external_target']}")
        print(f"  Run dir:  {result['run_dir']}")
        print(f"  Receipt:  {result['read_receipt_path']}")
        if result.get("builder_status") in {"failed", "policy_violation"}:
            raise SystemExit(1)
        return

    if args.task:
        result = run_task(args.task)
        check_and_prompt_questions()
        if result.get("task_status") == "failed":
            raise SystemExit(1)
        return

    results = []
    while True:
        tasks = find_open_tasks()

        if not tasks:
            print("No open tasks found. Triggering architect flow...")
            from orchestrator.graph import app

            result = app.invoke({"current_task_file": ""})
            answered = check_and_prompt_questions()
            if result.get("task_status") == "awaiting_input":
                if answered:
                    continue
                print("Planning is waiting for answers. Exiting loop.")
                break
            if result.get("task_status") == "failed":
                print("Architecture step failed. Exiting loop.")
                break
            tasks = find_open_tasks()
            if not tasks:
                print("No open tasks found after architecture step. Exiting loop.")
                break

        task = tasks[0]
        result = run_task(task)
        results.append(result)
        check_and_prompt_questions()
        if result.get("task_status") != "done":
            print("Task did not complete successfully. Exiting loop to avoid repeated retries.")
            break

    print(f"\n{'='*60}")
    print(f"  All tasks complete. {len(results)} task(s) processed.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
