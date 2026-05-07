import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.external.runner import (
    ExternalRunnerError,
    find_deny_glob_matches,
    resolve_factory_root,
    resolve_target_root,
    run_external_preflight,
)


class ExternalRunnerRootTests(unittest.TestCase):
    def test_resolve_factory_root_prefers_parameter_over_env(self) -> None:
        with tempfile.TemporaryDirectory() as env_root, tempfile.TemporaryDirectory() as arg_root:
            with patch.dict(os.environ, {"FACTORY_ROOT": env_root}):
                self.assertEqual(resolve_factory_root(arg_root), os.path.abspath(arg_root))

    def test_resolve_factory_root_uses_env(self) -> None:
        with tempfile.TemporaryDirectory() as env_root:
            with patch.dict(os.environ, {"FACTORY_ROOT": env_root}):
                self.assertEqual(resolve_factory_root(), os.path.abspath(env_root))

    def test_target_root_defaults_under_external_targets(self) -> None:
        with tempfile.TemporaryDirectory() as factory_root:
            target_root = resolve_target_root("idp_pipeline", os.path.abspath(factory_root))

        self.assertTrue(target_root.replace("\\", "/").endswith("external_targets/idp_pipeline"))

    def test_target_root_must_not_equal_factory_root(self) -> None:
        with tempfile.TemporaryDirectory() as factory_root:
            with self.assertRaisesRegex(ExternalRunnerError, "same directory"):
                resolve_target_root("idp_pipeline", os.path.abspath(factory_root), factory_root)

    def test_target_root_must_not_be_inside_sensitive_factory_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as factory_root:
            bad_target = Path(factory_root) / "orchestrator" / "target"
            with self.assertRaisesRegex(ExternalRunnerError, "orchestrator"):
                resolve_target_root("idp_pipeline", os.path.abspath(factory_root), str(bad_target))


class ExternalRunnerDenyGlobTests(unittest.TestCase):
    def test_find_deny_glob_matches_ignores_git_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / ".env").write_text("ignored\n", encoding="utf-8")
            (root / ".env").write_text("secret\n", encoding="utf-8")
            (root / "data").mkdir()
            (root / "data" / "sample.txt").write_text("sample\n", encoding="utf-8")

            matches = find_deny_glob_matches(str(root), (".env", "data/**"))

        self.assertEqual(matches, [".env", "data", "data/sample.txt"])


class ExternalRunnerPreflightTests(unittest.TestCase):
    def test_run_external_preflight_clones_missing_target_and_writes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            factory = root / "factory"
            target = root / "target"
            source.mkdir()
            factory.mkdir()
            _create_target_repo(source)
            _write_manifest(factory, source)

            from orchestrator.external import runner

            real_run_git = runner._run_git

            def fake_run_git(args, cwd):
                if args[0] == "clone":
                    _create_target_repo(Path(args[2]))
                    return subprocess.CompletedProcess(["git", *args], 0, "", "")
                return real_run_git(args, cwd)

            with patch("orchestrator.external.runner._run_git", side_effect=fake_run_git):
                result = run_external_preflight(
                    "idp_pipeline",
                    factory_root=str(factory),
                    target_root=str(target),
                )

            receipt = Path(str(result["read_receipt_path"]))
            self.assertTrue(receipt.exists())
            self.assertEqual(result["external_mode"], True)
            self.assertEqual(result["external_target"], "idp_pipeline")
            self.assertEqual(result["validation_command"], "pytest tests/test_smoke.py -v")

    def test_run_external_preflight_rejects_dirty_existing_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            factory = root / "factory"
            target = root / "target"
            source.mkdir()
            factory.mkdir()
            _create_target_repo(source)
            _create_target_repo(target)
            (target / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            _write_manifest(factory, source)

            with self.assertRaisesRegex(ExternalRunnerError, "clean"):
                run_external_preflight(
                    "idp_pipeline",
                    factory_root=str(factory),
                    target_root=str(target),
                )

    def test_run_external_preflight_rejects_non_git_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            factory = root / "factory"
            target = root / "target"
            source.mkdir()
            factory.mkdir()
            target.mkdir()
            _create_target_repo(source)
            _write_manifest(factory, source)

            with self.assertRaisesRegex(ExternalRunnerError, "not a git repository"):
                run_external_preflight(
                    "idp_pipeline",
                    factory_root=str(factory),
                    target_root=str(target),
                )


def _create_target_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-b", "develop"], cwd=path)
    (path / "docs" / "architecture").mkdir(parents=True)
    (path / "CLAUDE.md").write_text("claude\n", encoding="utf-8")
    (path / "AGENTS.md").write_text("agents\n", encoding="utf-8")
    (path / "docs" / "architecture" / "current_mvp.md").write_text("mvp\n", encoding="utf-8")
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


def _write_manifest(factory_root: Path, source_repo: Path) -> None:
    targets = factory_root / "targets"
    targets.mkdir()
    (targets / "idp_pipeline.yaml").write_text(
        textwrap.dedent(
            f"""
            repo: {source_repo.as_posix()}
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
              command: pytest tests/test_smoke.py -v
              mode: local
              timeout_seconds: 300
            builders:
              primary: claude
              fallback: null
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


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
