"""Normalization helpers for xcron domain models."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from libs.domain.models import (
    JobDefinition,
    NormalizedExecutionConfig,
    NormalizedJob,
    NormalizedManifest,
    ProjectManifest,
    build_artifact_id,
    build_qualified_job_id,
    resolve_working_dir,
    stable_env_items,
)


def normalize_job(manifest: ProjectManifest, job: JobDefinition, project_root: Path) -> NormalizedJob:
    """Merge manifest defaults into a deterministic normalized job model."""
    defaults = manifest.defaults
    working_dir = resolve_working_dir(project_root, job.working_dir or defaults.working_dir)
    shell = job.shell or defaults.shell
    env = dict(defaults.env)
    env.update(job.env)
    qualified_id = build_qualified_job_id(manifest.project.id, job.id)
    artifact_id = build_artifact_id(manifest.project.id, job.id)
    execution = NormalizedExecutionConfig(
        command=job.command,
        working_dir=working_dir,
        shell=shell,
        timezone=defaults.timezone,
        env=stable_env_items(env),
        overlap=job.overlap,
    )
    return NormalizedJob(
        project_id=manifest.project.id,
        job_id=job.id,
        qualified_id=qualified_id,
        artifact_id=artifact_id,
        enabled=job.enabled,
        schedule=job.schedule,
        execution=execution,
        description=job.description,
    )


def normalize_manifest(manifest: ProjectManifest, project_root: Path, manifest_path: Path) -> NormalizedManifest:
    """Normalize a project manifest into deterministic job-level state."""
    normalized_jobs = tuple(
        normalize_job(manifest, job, project_root)
        for job in sorted(manifest.jobs, key=lambda item: item.id)
    )
    return NormalizedManifest(
        version=manifest.version,
        project_id=manifest.project.id,
        project_root=str(project_root.resolve()),
        manifest_path=str(manifest_path.resolve()),
        jobs=normalized_jobs,
    )


def normalized_job_ids(jobs: Iterable[NormalizedJob]) -> tuple[str, ...]:
    """Return normalized qualified job identifiers in stable order."""
    return tuple(job.qualified_id for job in jobs)
