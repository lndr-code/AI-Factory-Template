import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.external.builder import run_external_builder
from orchestrator.external.finalize import finalize_external_patch
from orchestrator.external.manifest import load_external_target
from orchestrator.external.runner import ExternalRunnerError, run_external_preflight


class ExternalV0AcceptanceTests(unittest.TestCase):
    def test_a01_manifest_exists_and_loads(self) -> None:
        config = load_external_target("example", factory_root=str(REPO_ROOT))

        self.assertEqual(config.base_branch, "main")
        self.assertEqual(config.validation.command, "pytest tests/ -v")
        self.assertEqual(config.builders.primary, "claude")

    def test_a02_a03_a04_a07_full_flow_creates_patch_without_target_artifacts(self) -> None:
        with acceptance_fixture() as fx:
            state = run_external_preflight(
                "example",
                factory_root=str(fx.factory_root),
                target_root=str(fx.target_root),
            )
            with _mock_builder_modifying("pipeline.py", "changed\n"):
                state = run_external_builder(state, str(fx.task_path), builder="codex")
            state = finalize_external_patch(state)

            patch_path = Path(str(state["changes_patch_path"]))
            self.assertEqual(state["validation_status"], "passed")
            self.assertEqual(state["patch_status"], "created")
            self.assertTrue(patch_path.exists())
            self.assertIn("pipeline.py", patch_path.read_text(encoding="utf-8"))
            self.assertFalse((fx.target_root / "reports").exists())
            self.assertFalse((fx.target_root / "tasks").exists())
            self.assertFalse((fx.target_root / "specs").exists())
            self.assertFalse((fx.target_root / "questions").exists())
            receipt = json.loads(Path(str(state["read_receipt_path"])).read_text(encoding="utf-8"))
            self.assertEqual(
                sorted(receipt["required_read_hashes"]),
                ["AGENTS.md", "CLAUDE.md", "docs/architecture/current_mvp.md"],
            )
            _run(["git", "checkout", "--", "pipeline.py"], cwd=fx.target_root)
            _run(["git", "apply", "--check", str(patch_path)], cwd=fx.target_root)

    def test_a04_validation_failure_blocks_patch(self) -> None:
        with acceptance_fixture(validation_command=_python_command("raise SystemExit(2)")) as fx:
            state = run_external_preflight(
                "example",
                factory_root=str(fx.factory_root),
                target_root=str(fx.target_root),
            )
            with _mock_builder_modifying("pipeline.py", "changed\n"):
                state = run_external_builder(state, str(fx.task_path), builder="codex")
            state = finalize_external_patch(state)

            self.assertEqual(state["validation_status"], "failed")
            self.assertFalse((Path(str(state["run_dir"])) / "changes.patch").exists())

    def test_a05_required_read_change_blocks_patch(self) -> None:
        with acceptance_fixture() as fx:
            state = run_external_preflight(
                "example",
                factory_root=str(fx.factory_root),
                target_root=str(fx.target_root),
            )
            with _mock_builder_modifying("pipeline.py", "changed\n"):
                state = run_external_builder(state, str(fx.task_path), builder="codex")
            (fx.target_root / "AGENTS.md").write_text("changed rules\n", encoding="utf-8")
            state = finalize_external_patch(state)

            self.assertEqual(state["policy_violation"], "required_read_changed")
            self.assertEqual(state["patch_status"], "skipped")
            self.assertFalse((Path(str(state["run_dir"])) / "changes.patch").exists())

    def test_a06_deny_glob_blocks_preflight(self) -> None:
        with acceptance_fixture() as fx:
            (fx.target_root / ".env").write_text("SECRET=1\n", encoding="utf-8")

            with self.assertRaisesRegex(ExternalRunnerError, "deny_globs"):
                run_external_preflight(
                    "example",
                    factory_root=str(fx.factory_root),
                    target_root=str(fx.target_root),
                )

    def test_a08_builder_commit_is_policy_violation(self) -> None:
        with acceptance_fixture() as fx:
            state = run_external_preflight(
                "example",
                factory_root=str(fx.factory_root),
                target_root=str(fx.target_root),
            )
            with _mock_builder_committing():
                state = run_external_builder(state, str(fx.task_path), builder="codex")

            self.assertEqual(state["builder_status"], "policy_violation")
            self.assertEqual(state["policy_violation"], "builder_commit")

    def test_a09_external_uses_manifest_policy_without_gemini_reviewer(self) -> None:
        with acceptance_fixture() as fx:
            state = run_external_preflight(
                "example",
                factory_root=str(fx.factory_root),
                target_root=str(fx.target_root),
            )

            self.assertEqual(state["protected_paths_in_diff"], ["AGENTS.md"])

    def test_external_flow_does_not_mark_factory_task_done(self) -> None:
        with acceptance_fixture() as fx:
            original_task = fx.task_path.read_text(encoding="utf-8")
            state = run_external_preflight(
                "example",
                factory_root=str(fx.factory_root),
                target_root=str(fx.target_root),
            )
            with _mock_builder_modifying("pipeline.py", "changed\n"):
                state = run_external_builder(state, str(fx.task_path), builder="codex")
            state = finalize_external_patch(state)

            self.assertEqual(state["task_status"], "done")
            self.assertEqual(fx.task_path.read_text(encoding="utf-8"), original_task)


class acceptance_fixture:
    def __init__(self, validation_command: str | None = None) -> None:
        self.validation_command = validation_command or _python_command("print('ok')")

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.factory_root = self.root / "factory"
        self.target_root = self.root / "target"
        self.task_path = self.factory_root / "factory_tasks" / "example" / "001_task.md"
        self.factory_root.mkdir()
        self.task_path.parent.mkdir(parents=True)
        self.task_path.write_text("Change pipeline.py.\n", encoding="utf-8")
        _write_manifest(self.factory_root, self.validation_command)
        _create_target_repo(self.target_root)
        return self

    def __exit__(self, exc_type, exc, tb):
        self._tmp.cleanup()


class _mock_builder_modifying:
    def __init__(self, rel_path: str, content: str) -> None:
        self.rel_path = rel_path
        self.content = content

    def __enter__(self):
        self._which = patch("shutil.which", return_value="codex")
        self._run = patch(
            "orchestrator.external.builder._run_builder_command",
            side_effect=self._modify,
        )
        self._which.__enter__()
        self._run.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._run.__exit__(exc_type, exc, tb)
        self._which.__exit__(exc_type, exc, tb)

    def _modify(self, command, prompt, cwd, timeout):
        Path(cwd, self.rel_path).write_text(self.content, encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "builder ok", "")


class _mock_builder_committing:
    def __enter__(self):
        self._which = patch("shutil.which", return_value="codex")
        self._run = patch(
            "orchestrator.external.builder._run_builder_command",
            side_effect=self._commit,
        )
        self._which.__enter__()
        self._run.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._run.__exit__(exc_type, exc, tb)
        self._which.__exit__(exc_type, exc, tb)

    def _commit(self, command, prompt, cwd, timeout):
        path = Path(cwd)
        (path / "pipeline.py").write_text("committed\n", encoding="utf-8")
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
                "bad builder commit",
            ],
            cwd=path,
        )
        return subprocess.CompletedProcess(command, 0, "", "")


def _create_target_repo(path: Path) -> None:
    path.mkdir()
    _run(["git", "init", "-b", "develop"], cwd=path)
    (path / "docs" / "architecture").mkdir(parents=True)
    (path / "CLAUDE.md").write_text("claude\n", encoding="utf-8")
    (path / "AGENTS.md").write_text("agents\n", encoding="utf-8")
    (path / "docs" / "architecture" / "current_mvp.md").write_text("mvp\n", encoding="utf-8")
    (path / "pipeline.py").write_text("original\n", encoding="utf-8")
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
            "init target",
        ],
        cwd=path,
    )


def _write_manifest(factory_root: Path, validation_command: str) -> None:
    targets = factory_root / "targets"
    targets.mkdir()
    (targets / "example.yaml").write_text(
        textwrap.dedent(
            f"""
            repo: unused
            base_branch: develop
            protected_branches:
              - main
            required_read_files:
              - CLAUDE.md
              - AGENTS.md
              - docs/architecture/current_mvp.md
            planning:
              architect_phase: disabled
            task_sources:
              - factory_task_file
            validation:
              command: {validation_command}
              mode: local
              timeout_seconds: 10
            builders:
              primary: codex
              fallback: claude
            commit:
              enabled_from_version: v1
              branch_strategy: agent_branch
              branch_prefixes:
                - feature/agent-
              message_prefix_from_task: true
              push_enabled_from_version: v1
              pr_enabled_from_version: v2
            security:
              deny_globs:
                - .env
                - data/**
              abort_if_deny_glob_present: true
              protected_paths_in_diff:
                - AGENTS.md
              log_redaction:
                drop_fields: [stdout, stderr]
                keep_fields: [exit_code, changed_files]
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _python_command(code: str) -> str:
    escaped = code.replace('"', '\\"')
    return f'python -c "{escaped}"'


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


REPO_ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    unittest.main()
