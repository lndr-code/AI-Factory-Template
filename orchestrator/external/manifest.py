from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import yaml

SUPPORTED_EXTERNAL_BUILDERS = frozenset({"claude", "codex"})


class ManifestError(ValueError):
    """Raised when an external target manifest is missing or invalid."""


@dataclass(frozen=True)
class PlanningConfig:
    architect_phase: str


@dataclass(frozen=True)
class ValidationConfig:
    command: str
    mode: str
    timeout_seconds: int


@dataclass(frozen=True)
class BuilderConfig:
    primary: str
    fallback: str | None


@dataclass(frozen=True)
class CommitConfig:
    enabled_from_version: str
    branch_strategy: str
    branch_prefixes: tuple[str, ...]
    message_prefix_from_task: bool
    push_enabled_from_version: str
    pr_enabled_from_version: str


@dataclass(frozen=True)
class SecurityConfig:
    deny_globs: tuple[str, ...]
    abort_if_deny_glob_present: bool
    protected_paths_in_diff: tuple[str, ...]
    log_redaction_drop_fields: tuple[str, ...]
    log_redaction_keep_fields: tuple[str, ...]


@dataclass(frozen=True)
class ExternalTargetConfig:
    name: str
    manifest_path: str
    repo: str
    base_branch: str
    protected_branches: tuple[str, ...]
    required_read_files: tuple[str, ...]
    planning: PlanningConfig
    task_sources: tuple[str, ...]
    validation: ValidationConfig
    builders: BuilderConfig
    commit: CommitConfig
    security: SecurityConfig


def load_external_target(
    name: str,
    factory_root: str | None = None,
) -> ExternalTargetConfig:
    """Load and validate targets/<name>.yaml for External Mode v0."""
    if not name or any(separator in name for separator in ("/", "\\")):
        raise ManifestError(f"Invalid external target name: {name!r}")

    root = factory_root or os.getcwd()
    manifest_path = os.path.join(root, "targets", f"{name}.yaml")
    if not os.path.exists(manifest_path):
        raise ManifestError(f"External target manifest not found: {manifest_path}")

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ManifestError(f"Invalid YAML in external target manifest {manifest_path}: {e}") from e

    if not isinstance(raw, dict):
        raise ManifestError(f"External target manifest must be a mapping: {manifest_path}")

    for field in (
        "repo",
        "base_branch",
        "protected_branches",
        "required_read_files",
        "planning",
        "task_sources",
        "validation",
        "builders",
        "commit",
        "security",
    ):
        _require(raw, field)

    planning = _load_planning(raw["planning"])
    validation = _load_validation(raw["validation"])
    builders = _load_builders(raw["builders"])
    commit = _load_commit(raw["commit"])
    security = _load_security(raw["security"])
    task_sources = _string_tuple(raw, "task_sources")

    if "factory_task_file" not in task_sources:
        raise ManifestError("task_sources must include 'factory_task_file' for External Mode v0")

    return ExternalTargetConfig(
        name=name,
        manifest_path=_slash_path(manifest_path),
        repo=_non_empty_string(raw, "repo"),
        base_branch=_non_empty_string(raw, "base_branch"),
        protected_branches=_string_tuple(raw, "protected_branches"),
        required_read_files=_path_tuple(raw, "required_read_files"),
        planning=planning,
        task_sources=task_sources,
        validation=validation,
        builders=builders,
        commit=commit,
        security=security,
    )


def _load_planning(raw: Any) -> PlanningConfig:
    data = _mapping(raw, "planning")
    architect_phase = _non_empty_string(data, "architect_phase", prefix="planning")
    if architect_phase != "disabled":
        raise ManifestError("planning.architect_phase must be 'disabled' for External Mode v0")
    return PlanningConfig(architect_phase=architect_phase)


def _load_validation(raw: Any) -> ValidationConfig:
    data = _mapping(raw, "validation")
    command = _non_empty_string(data, "command", prefix="validation")
    mode = _non_empty_string(data, "mode", prefix="validation")
    if mode != "local":
        raise ManifestError("validation.mode must be 'local' for External Mode v0")
    timeout = data.get("timeout_seconds")
    if not isinstance(timeout, int) or timeout <= 0:
        raise ManifestError("validation.timeout_seconds must be a positive integer")
    return ValidationConfig(command=command, mode=mode, timeout_seconds=timeout)


def _load_builders(raw: Any) -> BuilderConfig:
    data = _mapping(raw, "builders")
    primary = _non_empty_string(data, "primary", prefix="builders")
    if primary not in SUPPORTED_EXTERNAL_BUILDERS:
        raise ManifestError("builders.primary must be one of: claude, codex")
    if "fallback" not in data:
        raise ManifestError("Missing required manifest field: builders.fallback")
    fallback = data["fallback"]
    if fallback is not None:
        if not isinstance(fallback, str) or not fallback.strip():
            raise ManifestError("builders.fallback must be a builder name or null")
        fallback = fallback.strip()
        if fallback not in SUPPORTED_EXTERNAL_BUILDERS:
            raise ManifestError("builders.fallback must be one of: claude, codex, null")
        if fallback == primary:
            raise ManifestError("builders.fallback must differ from builders.primary")
    return BuilderConfig(primary=primary, fallback=fallback)


def _load_commit(raw: Any) -> CommitConfig:
    data = _mapping(raw, "commit")
    enabled_from = _non_empty_string(data, "enabled_from_version", prefix="commit")
    if enabled_from == "v0":
        raise ManifestError("commit.enabled_from_version must be later than v0")
    strategy = _non_empty_string(data, "branch_strategy", prefix="commit")
    if strategy != "agent_branch":
        raise ManifestError("commit.branch_strategy must be 'agent_branch'")
    prefixes = _string_tuple(data, "branch_prefixes", prefix="commit")
    if not prefixes:
        raise ManifestError("commit.branch_prefixes must contain at least one prefix")
    message_prefix = data.get("message_prefix_from_task")
    if not isinstance(message_prefix, bool):
        raise ManifestError("commit.message_prefix_from_task must be a boolean")
    push_from = _non_empty_string(data, "push_enabled_from_version", prefix="commit")
    pr_from = _non_empty_string(data, "pr_enabled_from_version", prefix="commit")
    return CommitConfig(
        enabled_from_version=enabled_from,
        branch_strategy=strategy,
        branch_prefixes=prefixes,
        message_prefix_from_task=message_prefix,
        push_enabled_from_version=push_from,
        pr_enabled_from_version=pr_from,
    )


def _load_security(raw: Any) -> SecurityConfig:
    data = _mapping(raw, "security")
    deny_globs = _path_tuple(data, "deny_globs", prefix="security")
    abort = data.get("abort_if_deny_glob_present")
    if not isinstance(abort, bool):
        raise ManifestError("security.abort_if_deny_glob_present must be a boolean")
    protected = _path_tuple(data, "protected_paths_in_diff", prefix="security")
    log_redaction = _mapping(_require(data, "log_redaction", prefix="security"), "security.log_redaction")
    return SecurityConfig(
        deny_globs=deny_globs,
        abort_if_deny_glob_present=abort,
        protected_paths_in_diff=protected,
        log_redaction_drop_fields=_string_tuple(log_redaction, "drop_fields", prefix="security.log_redaction"),
        log_redaction_keep_fields=_string_tuple(log_redaction, "keep_fields", prefix="security.log_redaction"),
    )


def _mapping(raw: Any, name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ManifestError(f"{name} must be a mapping")
    return raw


def _require(data: dict[str, Any], field: str, prefix: str | None = None) -> Any:
    if field not in data:
        dotted = f"{prefix}.{field}" if prefix else field
        raise ManifestError(f"Missing required manifest field: {dotted}")
    return data[field]


def _non_empty_string(data: dict[str, Any], field: str, prefix: str | None = None) -> str:
    value = _require(data, field, prefix=prefix)
    if not isinstance(value, str) or not value.strip():
        dotted = f"{prefix}.{field}" if prefix else field
        raise ManifestError(f"{dotted} must be a non-empty string")
    return value.strip()


def _string_tuple(data: dict[str, Any], field: str, prefix: str | None = None) -> tuple[str, ...]:
    value = _require(data, field, prefix=prefix)
    dotted = f"{prefix}.{field}" if prefix else field
    if not isinstance(value, list):
        raise ManifestError(f"{dotted} must be a list of strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ManifestError(f"{dotted} must be a list of non-empty strings")
        result.append(item.strip())
    return tuple(result)


def _path_tuple(data: dict[str, Any], field: str, prefix: str | None = None) -> tuple[str, ...]:
    return tuple(_slash_path(path) for path in _string_tuple(data, field, prefix=prefix))


def _slash_path(path: str) -> str:
    return path.replace("\\", "/")
