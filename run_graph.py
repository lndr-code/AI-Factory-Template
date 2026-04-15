"""
AI Factory Orchestrator - Task Runner

Usage:
    # Run all open tasks from /tasks/ in sorted order:
    python run_graph.py

    # Run a single specific task:
    python run_graph.py --task tasks/01_setup.md

Tasks marked as done (filename contains '.done.') are automatically skipped.
"""
import argparse
import os
import glob

from orchestrator.graph import app

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/workspace")


def find_open_tasks() -> list[str]:
    """Find all task .md files, sorted by filename, skipping .done. files."""
    tasks_dir = os.path.join(PROJECT_ROOT, "tasks")
    all_tasks = sorted(glob.glob(os.path.join(tasks_dir, "*.md")))
    open_tasks = [
        os.path.relpath(t, PROJECT_ROOT).replace("\\", "/")
        for t in all_tasks
        if ".done." not in os.path.basename(t) and os.path.basename(t) != ".gitkeep"
    ]
    return open_tasks


def run_task(task_file: str):
    print(f"\n{'='*60}")
    print(f"  Running task: {task_file}")
    print(f"{'='*60}")
    result = app.invoke({"current_task_file": task_file})
    print(f"\n  Result: {result.get('final_report', 'No report generated.')}")
    return result


def main():
    parser = argparse.ArgumentParser(description="AI Factory Orchestrator Task Runner")
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="Path to a specific task file relative to PROJECT_ROOT (e.g. tasks/01_setup.md). "
             "If not provided, all open tasks are run in sorted order."
    )
    args = parser.parse_args()

    if args.task:
        tasks = [args.task]
    else:
        tasks = find_open_tasks()
        if not tasks:
            print("No open tasks found in /tasks/. Add .md files to get started.")
            return
        print(f"\nFound {len(tasks)} open task(s):")
        for t in tasks:
            print(f"  - {t}")

    results = []
    for task in tasks:
        result = run_task(task)
        results.append(result)

    print(f"\n{'='*60}")
    print(f"  All tasks complete. {len(results)} task(s) processed.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
