"""Load one project's xcron manifest from disk."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from libs.domain.models import (
    DefaultsConfig,
    JobDefinition,
    OverlapPolicy,
    ProjectConfig,
    ProjectManifest,
    ScheduleDefinition,
    ScheduleKind,
)

XCRON_HOME_ENV_VAR = "XCRON_HOME"
MANIFEST_DIR = Path("schedules")
LEGACY_MANIFEST_DIR = Path("resources/schedules")
MANIFEST_SUFFIXES = (".yaml", ".yml")


class ManifestLoadError(Exception):
    """Base exception for project manifest loading problems."""


class ProjectResolutionError(ManifestLoadError):
    """Raised when the requested project path is invalid."""


class ManifestNotFoundError(ManifestLoadError):
    """Raised when the project manifest is missing."""


class AmbiguousManifestSelectionError(ManifestLoadError):
    """Raised when more than one schedule manifest exists but none was selected."""


class ManifestParseError(ManifestLoadError):
    """Raised when YAML cannot be parsed into a mapping."""


@dataclass(frozen=True)
class LoadedManifestDocument:
    """Manifest document loaded from one project root."""

    project_root: Path
    manifest_path: Path
    raw_data: Mapping[str, Any]
    manifest: ProjectManifest | None = None


def resolve_xcron_home(env: dict[str, str] | None = None) -> Path:
    """Return the xcron home directory (~/.xcron by default, XCRON_HOME override)."""
    env_map = os.environ if env is None else env
    override = env_map.get(XCRON_HOME_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".xcron").resolve()


def _has_schedules(directory: Path) -> bool:
    """Check whether a directory contains a schedules/ or resources/schedules/ subdir."""
    return (directory / MANIFEST_DIR).is_dir() or (directory / LEGACY_MANIFEST_DIR).is_dir()


def resolve_project_root(project_path: str | Path | None = None) -> Path:
    """Resolve the target project root.

    Priority: explicit --project > cwd (if it has schedules/) > ~/.xcron
    """
    if project_path is not None:
        candidate = Path(project_path).expanduser()
    else:
        cwd = Path.cwd()
        candidate = cwd if _has_schedules(cwd) else resolve_xcron_home()
    resolved = candidate.resolve()
    if not resolved.exists():
        raise ProjectResolutionError(f"project path does not exist: {resolved}")
    if not resolved.is_dir():
        raise ProjectResolutionError(f"project path is not a directory: {resolved}")
    return resolved


def resolve_manifest_dir(project_root: Path) -> Path:
    """Resolve the schedules directory for one project."""
    primary = (project_root / MANIFEST_DIR).resolve()
    if primary.exists():
        return primary
    legacy = (project_root / LEGACY_MANIFEST_DIR).resolve()
    if legacy.exists():
        return legacy
    return primary


def resolve_manifest_path(project_root: Path, schedule_name: str | None = None) -> Path:
    """Resolve one manifest path from the project schedules directory."""
    manifest_dir = resolve_manifest_dir(project_root)
    if not manifest_dir.exists():
        raise ManifestNotFoundError(f"schedule directory not found: {manifest_dir}")
    if not manifest_dir.is_dir():
        raise ManifestNotFoundError(f"schedule directory is not a directory: {manifest_dir}")

    if schedule_name:
        manifest_name = schedule_name if Path(schedule_name).suffix in MANIFEST_SUFFIXES else f"{schedule_name}.yaml"
        manifest_path = manifest_dir / manifest_name
        if not manifest_path.exists():
            raise ManifestNotFoundError(f"schedule manifest not found: {manifest_path}")
        if not manifest_path.is_file():
            raise ManifestNotFoundError(f"schedule manifest is not a file: {manifest_path}")
        return manifest_path.resolve()

    candidates = tuple(sorted(path for path in manifest_dir.iterdir() if path.is_file() and path.suffix in MANIFEST_SUFFIXES))
    if not candidates:
        raise ManifestNotFoundError(f"no schedule manifests found under: {manifest_dir}")
    if len(candidates) > 1:
        available = ", ".join(path.stem for path in candidates)
        raise AmbiguousManifestSelectionError(
            f"multiple schedule manifests found under {manifest_dir}; choose one with --schedule. Available: {available}"
        )
    return candidates[0].resolve()


def load_manifest_data(manifest_path: Path) -> Mapping[str, Any]:
    """Read YAML from disk and require a mapping-shaped document."""
    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            raw_data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ManifestParseError(f"invalid YAML in {manifest_path}: {exc}") from exc

    if raw_data is None:
        raise ManifestParseError(f"manifest is empty: {manifest_path}")
    if not isinstance(raw_data, Mapping):
        raise ManifestParseError(f"manifest root must be a mapping: {manifest_path}")
    return raw_data


def parse_project_manifest(raw_data: Mapping[str, Any]) -> ProjectManifest:
    """Convert validated manifest data into raw domain models."""
    defaults_data = raw_data.get("defaults") or {}
    jobs_data = raw_data.get("jobs") or []

    defaults = DefaultsConfig(
        working_dir=str(defaults_data.get("working_dir", DefaultsConfig.working_dir)),
        shell=str(defaults_data.get("shell", DefaultsConfig.shell)),
        timezone=defaults_data.get("timezone"),
        env={str(key): str(value) for key, value in (defaults_data.get("env") or {}).items()},
    )

    jobs = tuple(parse_job_definition(job_data) for job_data in jobs_data)
    project = ProjectConfig(id=str(raw_data["project"]["id"]))
    return ProjectManifest(
        version=int(raw_data["version"]),
        project=project,
        defaults=defaults,
        jobs=jobs,
    )


def parse_job_definition(job_data: Mapping[str, Any]) -> JobDefinition:
    """Convert one job mapping into a raw job model."""
    schedule_data = job_data["schedule"]
    if "cron" in schedule_data:
        schedule = ScheduleDefinition(kind=ScheduleKind.CRON, value=str(schedule_data["cron"]))
    else:
        schedule = ScheduleDefinition(kind=ScheduleKind.EVERY, value=str(schedule_data["every"]))

    overlap = OverlapPolicy(str(job_data.get("overlap", OverlapPolicy.ALLOW.value)))
    return JobDefinition(
        id=str(job_data["id"]),
        description=job_data.get("description"),
        enabled=bool(job_data.get("enabled", True)),
        schedule=schedule,
        command=str(job_data["command"]),
        working_dir=job_data.get("working_dir"),
        shell=job_data.get("shell"),
        env={str(key): str(value) for key, value in (job_data.get("env") or {}).items()},
        overlap=overlap,
    )


def load_project_manifest(
    project_path: str | Path | None = None,
    schedule_name: str | None = None,
) -> LoadedManifestDocument:
    """Load one project's manifest document from disk without semantic parsing."""
    project_root = resolve_project_root(project_path)
    manifest_path = resolve_manifest_path(project_root, schedule_name=schedule_name)
    raw_data = load_manifest_data(manifest_path)
    return LoadedManifestDocument(
        project_root=project_root,
        manifest_path=manifest_path,
        raw_data=raw_data,
    )


def attach_parsed_manifest(document: LoadedManifestDocument) -> LoadedManifestDocument:
    """Return a loaded document with its raw data parsed into domain models."""
    return LoadedManifestDocument(
        project_root=document.project_root,
        manifest_path=document.manifest_path,
        raw_data=document.raw_data,
        manifest=parse_project_manifest(document.raw_data),
    )
