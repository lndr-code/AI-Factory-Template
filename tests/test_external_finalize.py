import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.external.finalize import finalize_external_patch
from orchestrator.external.read_receipt import build_read_receipt


class ExternalFinalizeTests(unittest.TestCase):
    def test_successful_validation_writes_patch_and_report(self) -> None:
        with finalize_fixture() as fx:
            (fx.target_root / "README.md").write_text("changed\n", encoding="utf-8")

            result = finalize_external_patch(fx.state)

            patch_path = Path(str(result["changes_patch_path"]))
            self.assertEqual(result["validation_status"], "passed")
            self.assertEqual(result["patch_status"], "created")
            self.assertEqual(result["task_status"], "done")
            self.assertTrue(patch_path.exists())
            self.assertIn("README.md", patch_path.read_text(encoding="utf-8"))
            self.assertTrue((fx.run_dir / "validation.log").exists())
            self.assertTrue((fx.run_dir / "report.md").exists())
            dirty = subprocess.run(
                ["git", "diff", "--quiet"],
                cwd=fx.target_root,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(dirty.returncode, 0)
            _run(["git", "checkout", "--", "README.md"], cwd=fx.target_root)
            _run(["git", "apply", "--check", str(patch_path)], cwd=fx.target_root)

    def test_failed_validation_does_not_write_patch(self) -> None:
        with finalize_fixture(validation_command=_python_command("raise SystemExit(2)")) as fx:
            (fx.target_root / "README.md").write_text("changed\n", encoding="utf-8")

            result = finalize_external_patch(fx.state)

            self.assertEqual(result["validation_status"], "failed")
            self.assertEqual(result["patch_status"], "skipped")
            self.assertFalse((fx.run_dir / "changes.patch").exists())
            self.assertTrue((fx.run_dir / "validation.log").exists())

    def test_validation_timeout_does_not_write_patch(self) -> None:
        with finalize_fixture() as fx:
            fx.state["validation_timeout_seconds"] = 1
            fx.state["validation_command"] = _python_command("import time; time.sleep(5)")
            (fx.target_root / "README.md").write_text("changed\n", encoding="utf-8")

            result = finalize_external_patch(fx.state)

            self.assertEqual(result["validation_status"], "failed")
            self.assertIn("timed out", result["last_error"])
            self.assertFalse((fx.run_dir / "changes.patch").exists())

    def test_empty_diff_sets_no_changes(self) -> None:
        with finalize_fixture() as fx:
            result = finalize_external_patch(fx.state)

            self.assertEqual(result["validation_status"], "passed")
            self.assertEqual(result["patch_status"], "no_changes")
            self.assertEqual(result["task_status"], "failed")
            self.assertFalse((fx.run_dir / "changes.patch").exists())

    def test_factory_artifact_in_diff_sets_policy_violation(self) -> None:
        with finalize_fixture() as fx:
            reports = fx.target_root / "reports"
            reports.mkdir()
            (reports / "session-report.md").write_text("baseline\n", encoding="utf-8")
            _run(["git", "add", "."], cwd=fx.target_root)
            _run(
                [
                    "git",
                    "-c",
                    "user.name=Test User",
                    "-c",
                    "user.email=test@example.com",
                    "commit",
                    "-m",
                    "add report baseline",
                ],
                cwd=fx.target_root,
            )
            (reports / "session-report.md").write_text("bad\n", encoding="utf-8")

            result = finalize_external_patch(fx.state)

            self.assertEqual(result["validation_status"], "passed")
            self.assertEqual(result["patch_status"], "policy_violation")
            self.assertEqual(result["policy_violation"], "external_artifact_in_patch")
            self.assertFalse((fx.run_dir / "changes.patch").exists())

    def test_non_successful_builder_status_skips_finalizer(self) -> None:
        with finalize_fixture() as fx:
            fx.state["builder_status"] = "failed"

            result = finalize_external_patch(fx.state)

            self.assertEqual(result["finalize_status"], "skipped")
            self.assertEqual(result["task_status"], "failed")

    def test_patch_check_failure_marks_patch_failed(self) -> None:
        with finalize_fixture() as fx:
            (fx.target_root / "README.md").write_text("changed\n", encoding="utf-8")
            with patch(
                "orchestrator.external.finalize._run_git",
                side_effect=_fail_apply_check_once,
            ):
                result = finalize_external_patch(fx.state)

            self.assertEqual(result["patch_status"], "failed")
            self.assertIn("cannot apply", result["last_error"])


class finalize_fixture:
    def __init__(self, validation_command: str | None = None) -> None:
        self.validation_command = validation_command or _python_command("print('ok')")

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.target_root = self.root / "target"
        self.run_dir = self.root / "factory" / "runs" / "run-1"
        self.target_root.mkdir(parents=True)
        self.run_dir.mkdir(parents=True)
        _create_git_repo(self.target_root)
        self.state = {
            "external_mode": True,
            "external_target": "example",
            "external_builder": "codex",
            "builder_status": "success",
            "build_status": "success",
            "target_root": str(self.target_root),
            "run_dir": str(self.run_dir),
            "validation_command": self.validation_command,
            "validation_timeout_seconds": 10,
            "required_read_hashes": build_read_receipt(
                str(self.target_root),
                ("CLAUDE.md", "AGENTS.md", "docs/architecture/current_mvp.md"),
            ),
        }
        return self

    def __exit__(self, exc_type, exc, tb):
        self._tmp.cleanup()


def _fail_apply_check_once(args, cwd, check=True):
    if args[:4] == ["apply", "--check", "--cached", "--ignore-whitespace"]:
        return subprocess.CompletedProcess(["git", *args], 1, "", "cannot apply patch")

    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def _create_git_repo(path: Path) -> None:
    _run(["git", "init", "-b", "develop"], cwd=path)
    (path / "docs" / "architecture").mkdir(parents=True)
    (path / "CLAUDE.md").write_text("claude\n", encoding="utf-8")
    (path / "AGENTS.md").write_text("agents\n", encoding="utf-8")
    (path / "docs" / "architecture" / "current_mvp.md").write_text("mvp\n", encoding="utf-8")
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


def _python_command(code: str) -> str:
    escaped = code.replace('"', '\\"')
    return f'python -c "{escaped}"'


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
