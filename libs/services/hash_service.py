"""Stable hashing for normalized xcron state."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from libs.domain.models import NormalizedJob, NormalizedManifest


@dataclass(frozen=True)
class ManifestHashes:
    """Stable hashes for one normalized project manifest."""

    manifest_hash: str
    job_hashes: dict[str, str]
    job_definition_hashes: dict[str, str]


def hash_normalized_job_definition(job: NormalizedJob) -> str:
    """Hash one normalized job deterministically, excluding enabled state."""
    payload = {
        "project_id": job.project_id,
        "job_id": job.job_id,
        "qualified_id": job.qualified_id,
        "artifact_id": job.artifact_id,
        "schedule": {
            "kind": job.schedule.kind.value,
            "value": job.schedule.value,
        },
        "execution": {
            "command": job.execution.command,
            "working_dir": job.execution.working_dir,
            "shell": job.execution.shell,
            "timezone": job.execution.timezone,
            "env": list(job.execution.env),
            "overlap": job.execution.overlap.value,
        },
        "description": job.description,
    }
    return stable_hash(payload)


def hash_normalized_job(job: NormalizedJob) -> str:
    """Hash one normalized job deterministically, including enabled state."""
    payload = {
        "definition_hash": hash_normalized_job_definition(job),
        "enabled": job.enabled,
    }
    return stable_hash(payload)


def hash_normalized_manifest(manifest: NormalizedManifest) -> str:
    """Hash one normalized manifest deterministically."""
    payload = {
        "version": manifest.version,
        "project_id": manifest.project_id,
        "project_root": manifest.project_root,
        "manifest_path": manifest.manifest_path,
        "jobs": [
            {
                "qualified_id": job.qualified_id,
                "hash": hash_normalized_job(job),
            }
            for job in manifest.jobs
        ],
    }
    return stable_hash(payload)


def build_manifest_hashes(manifest: NormalizedManifest) -> ManifestHashes:
    """Compute project and per-job hashes from normalized state."""
    job_hashes = {job.qualified_id: hash_normalized_job(job) for job in manifest.jobs}
    job_definition_hashes = {job.qualified_id: hash_normalized_job_definition(job) for job in manifest.jobs}
    manifest_payload = {
        "version": manifest.version,
        "project_id": manifest.project_id,
        "project_root": manifest.project_root,
        "manifest_path": manifest.manifest_path,
        "job_hashes": job_hashes,
    }
    return ManifestHashes(
        manifest_hash=stable_hash(manifest_payload),
        job_hashes=job_hashes,
        job_definition_hashes=job_definition_hashes,
    )


def stable_hash(payload: object) -> str:
    """Serialize payload deterministically and return a SHA-256 digest."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
