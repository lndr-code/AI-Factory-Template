import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.external.builder import build_external_prompt, run_external_builder


class ExternalBuilderPromptTests(unittest.TestCase):
    def test_prompt_uses_required_read_hashes_and_run_dir_summary(self) -> None:
        with builder_fixture() as fx:
            prompt = build_external_prompt(fx.state, str(fx.task_path))

        self.assertIn(f"Workspace: {fx.target_root.as_posix()}", prompt)
        self.assertIn(f"Run dir: {fx.run_dir.as_posix()}", prompt)
        self.assertIn(f"Task file: {fx.task_path.as_posix()}", prompt)
        self.assertIn("CLAUDE.md: hash-claude", prompt)
        self.assertIn("AGENTS.md: hash-agents", prompt)
        self.assertIn("docs/architecture/current_mvp.md: hash-mvp", prompt)
        self.assertIn(f"{fx.run_dir.as_posix()}/builder_summary.md", prompt)
        self.assertNotIn("reports/session-report.md", prompt)
        self.assertNotIn("Before implementing, read /specs/", prompt)


class ExternalBuilderExecutionTests(unittest.TestCase):
    def test_codex_command_uses_exec_workspace_write_and_run_dir_access(self) -> None:
        calls = []
        with builder_fixture() as fx:
            with patch("shutil.which", return_value="codex"), patch(
                "orchestrator.external.builder._run_builder_command",
                side_effect=lambda command, prompt, cwd, timeout: calls.append(
                    (command, prompt, cwd, timeout)
                )
                or subprocess.CompletedProcess(command, 0, "out", "err"),
            ):
                result = run_external_builder(fx.state, str(fx.task_path), builder="codex")

            command, _prompt, cwd, timeout = calls[0]
            self.assertEqual(result["builder_status"], "success")
            self.assertIn("exec", command)
            self.assertIn("--cd", command)
            self.assertIn(str(fx.target_root), command)
            self.assertIn("--add-dir", command)
            self.assertIn(str(fx.run_dir), command)
            self.assertIn("--sandbox", command)
            self.assertIn("workspace-write", command)
            self.assertIn("--ask-for-approval", command)
            self.assertIn("never", command)
            self.assertIn("--output-last-message", command)
            self.assertNotIn("--approval-mode", command)
            self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)
            self.assertEqual(cwd, str(fx.target_root))
            self.assertEqual(timeout, 600)
            self.assertEqual((fx.run_dir / "codex_stdout.log").read_text(encoding="utf-8"), "out")
            self.assertEqual((fx.run_dir / "codex_stderr.log").read_text(encoding="utf-8"), "err")
            self.assertNotIn("codex_stdout", result)
            self.assertNotIn("codex_stderr", result)

    def test_claude_command_uses_target_root_cwd(self) -> None:
        calls = []
        with builder_fixture() as fx:
            with patch("shutil.which", return_value="claude"), patch(
                "orchestrator.external.builder._run_builder_command",
                side_effect=lambda command, prompt, cwd, timeout: calls.append(
                    (command, prompt, cwd, timeout)
                )
                or subprocess.CompletedProcess(command, 0, "", ""),
            ):
                result = run_external_builder(fx.state, str(fx.task_path), builder="claude")

            command, _prompt, cwd, _timeout = calls[0]

        self.assertEqual(result["builder_status"], "success")
        self.assertEqual(command[0], "claude")
        self.assertEqual(cwd, str(fx.target_root))

    def test_nonzero_exit_marks_builder_failed(self) -> None:
        with builder_fixture() as fx:
            with patch("shutil.which", return_value="codex"), patch(
                "orchestrator.external.builder._run_builder_command",
                return_value=subprocess.CompletedProcess(["codex"], 2, "out", "bad"),
            ):
                result = run_external_builder(fx.state, str(fx.task_path), builder="codex")
            self.assertEqual(result["builder_status"], "failed")
            self.assertIn("exited with code 2", result["last_error"])
            self.assertTrue((fx.run_dir / "report.md").exists())

    def test_head_change_marks_policy_violation(self) -> None:
        with builder_fixture() as fx:
            with patch("shutil.which", return_value="codex"), patch(
                "orchestrator.external.builder._get_head_sha",
                side_effect=["before", "after"],
            ), patch(
                "orchestrator.external.builder._run_builder_command",
                return_value=subprocess.CompletedProcess(["codex"], 0, "", ""),
            ), patch(
                "orchestrator.external.builder._git_status_paths",
                return_value=[],
            ):
                result = run_external_builder(fx.state, str(fx.task_path), builder="codex")

        self.assertEqual(result["builder_status"], "policy_violation")
        self.assertEqual(result["policy_violation"], "builder_commit")

    def test_target_factory_artifact_marks_policy_violation(self) -> None:
        with builder_fixture() as fx:
            def create_artifact(command, prompt, cwd, timeout):
                reports = Path(cwd) / "reports"
                reports.mkdir()
                (reports / "session-report.md").write_text("bad\n", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("shutil.which", return_value="codex"), patch(
                "orchestrator.external.builder._run_builder_command",
                side_effect=create_artifact,
            ):
                result = run_external_builder(fx.state, str(fx.task_path), builder="codex")

        self.assertEqual(result["builder_status"], "policy_violation")
        self.assertEqual(result["policy_violation"], "idp_artifact_created")
        self.assertIn("reports", result["last_error"])


class builder_fixture:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.factory_root = self.root / "factory"
        self.target_root = self.root / "target"
        self.run_dir = self.factory_root / "runs" / "run-1"
        self.factory_root.mkdir()
        self.target_root.mkdir()
        self.run_dir.mkdir(parents=True)
        self.task_path = self.factory_root / "factory_tasks" / "idp_pipeline" / "001_task.md"
        self.task_path.parent.mkdir(parents=True)
        self.task_path.write_text("Implement the task.\n", encoding="utf-8")
        _create_git_repo(self.target_root)
        self.state = {
            "external_mode": True,
            "external_target": "idp_pipeline",
            "factory_root": str(self.factory_root),
            "target_root": str(self.target_root),
            "run_id": "run-1",
            "run_dir": str(self.run_dir),
            "manifest_path": str(self.factory_root / "targets" / "idp_pipeline.yaml"),
            "external_builder_primary": "codex",
            "external_builder_fallback": "claude",
            "required_read_hashes": {
                "CLAUDE.md": "hash-claude",
                "AGENTS.md": "hash-agents",
                "docs/architecture/current_mvp.md": "hash-mvp",
            },
        }
        return self

    def __exit__(self, exc_type, exc, tb):
        self._tmp.cleanup()


def _create_git_repo(path: Path) -> None:
    _run(["git", "init", "-b", "develop"], cwd=path)
    (path / "README.md").write_text("target\n", encoding="utf-8")
    _run(["git", "add", "."], cwd=path)
    _run(
        [
            "git",
            "-c",
            "user.name=Test User",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "init",
        ],
        cwd=path,
    )


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
