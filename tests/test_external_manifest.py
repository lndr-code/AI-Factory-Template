import tempfile
import textwrap
import unittest
from pathlib import Path

from orchestrator.external.manifest import ManifestError, load_external_target


VALID_MANIFEST = """
repo: git@github.com:lndr-code/idp_pipeline.git
base_branch: develop
protected_branches:
  - main
required_read_files:
  - CLAUDE.md
  - AGENTS.md
  - docs\\architecture\\current_mvp.md
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
    - data\\**
  abort_if_deny_glob_present: true
  protected_paths_in_diff:
    - .github\\workflows\\**
  log_redaction:
    drop_fields: [stdout, stderr]
    keep_fields: [exit_code, changed_files]
"""


class ExternalManifestTests(unittest.TestCase):
    def test_loads_valid_manifest(self) -> None:
        with manifest_root(VALID_MANIFEST) as root:
            config = load_external_target("idp_pipeline", factory_root=str(root))

        self.assertEqual(config.name, "idp_pipeline")
        self.assertEqual(config.repo, "git@github.com:lndr-code/idp_pipeline.git")
        self.assertEqual(config.planning.architect_phase, "disabled")
        self.assertEqual(config.builders.primary, "claude")
        self.assertIsNone(config.builders.fallback)
        self.assertEqual(config.required_read_files[-1], "docs/architecture/current_mvp.md")
        self.assertEqual(config.security.deny_globs[-1], "data/**")

    def test_missing_required_field_fails(self) -> None:
        manifest = VALID_MANIFEST.replace("repo: git@github.com:lndr-code/idp_pipeline.git\n", "")
        with manifest_root(manifest) as root:
            with self.assertRaisesRegex(ManifestError, "repo"):
                load_external_target("idp_pipeline", factory_root=str(root))

    def test_architect_phase_must_be_disabled(self) -> None:
        manifest = VALID_MANIFEST.replace("architect_phase: disabled", "architect_phase: enabled")
        with manifest_root(manifest) as root:
            with self.assertRaisesRegex(ManifestError, "planning\\.architect_phase"):
                load_external_target("idp_pipeline", factory_root=str(root))

    def test_primary_builder_must_be_claude(self) -> None:
        manifest = VALID_MANIFEST.replace("primary: claude", "primary: codex")
        with manifest_root(manifest) as root:
            with self.assertRaisesRegex(ManifestError, "builders\\.primary"):
                load_external_target("idp_pipeline", factory_root=str(root))

    def test_fallback_builder_must_be_null(self) -> None:
        manifest = VALID_MANIFEST.replace("fallback: null", "fallback: codex")
        with manifest_root(manifest) as root:
            with self.assertRaisesRegex(ManifestError, "builders\\.fallback"):
                load_external_target("idp_pipeline", factory_root=str(root))

    def test_validation_command_must_not_be_empty(self) -> None:
        manifest = VALID_MANIFEST.replace("command: pytest tests/test_smoke.py -v", "command: ''")
        with manifest_root(manifest) as root:
            with self.assertRaisesRegex(ManifestError, "validation\\.command"):
                load_external_target("idp_pipeline", factory_root=str(root))


class manifest_root:
    def __init__(self, manifest_text: str) -> None:
        self._manifest_text = manifest_text
        self._tmp: tempfile.TemporaryDirectory[str] | None = None

    def __enter__(self) -> Path:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        targets = root / "targets"
        targets.mkdir()
        (targets / "idp_pipeline.yaml").write_text(
            textwrap.dedent(self._manifest_text).strip() + "\n",
            encoding="utf-8",
        )
        return root

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._tmp is not None:
            self._tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
