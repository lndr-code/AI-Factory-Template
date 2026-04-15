import os
import subprocess
from orchestrator.state import OrchestratorState

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/workspace")


def review_and_commit(state: OrchestratorState) -> OrchestratorState:
    try:
        # 1. Check whether the git repository has changes
        git_status = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            check=True
        )
        state["git_status_output"] = git_status.stdout

        # 2. If there are no changes, nothing to commit
        if not git_status.stdout.strip():
            state["review_status"] = "no_changes"
            return state

        # 3. If changes exist, stage and commit
        state["test_output"] = "Tests skipped — add your test runner here"

        subprocess.run(["git", "add", "."], check=True, cwd=PROJECT_ROOT)
        subprocess.run(
            ["git", "commit", "-m", "Automated builder update"],
            check=True,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )

        # 4. Record commit SHA
        sha_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        state["commit_sha"] = sha_result.stdout.strip()
        state["review_status"] = "success"

    except subprocess.CalledProcessError as e:
        state["review_status"] = "failed"
        state["builder_status"] = "failed"
        state["last_error"] = f"Git operation failed: {e.stderr if e.stderr else str(e)}"
    except Exception as e:
        state["review_status"] = "failed"
        state["builder_status"] = "failed"
        state["last_error"] = str(e)

    return state
