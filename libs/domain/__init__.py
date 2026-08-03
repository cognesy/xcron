"""Manifest value types and normalization for xcron.

Desired-vs-deployed diffing is not here: it belongs to the reconciliation
module, which owns that decision. This package stays a leaf that no capability
depends on in the wrong direction.
"""

from xcron_libs.domain.models import (
    DEFAULT_SHELL,
    DEFAULT_WORKING_DIR,
    SUPPORTED_EVERY_SUFFIXES,
    DefaultsConfig,
    JobDefinition,
    NormalizedExecutionConfig,
    NormalizedJob,
    NormalizedManifest,
    OverlapPolicy,
    ProjectConfig,
    ProjectManifest,
    ScheduleDefinition,
    ScheduleKind,
    build_artifact_id,
    build_qualified_job_id,
)
from xcron_libs.domain.normalization import normalize_job, normalize_manifest, normalized_job_ids

__all__ = [
    "DEFAULT_SHELL",
    "DEFAULT_WORKING_DIR",
    "SUPPORTED_EVERY_SUFFIXES",
    "DefaultsConfig",
    "JobDefinition",
    "NormalizedExecutionConfig",
    "NormalizedJob",
    "NormalizedManifest",
    "OverlapPolicy",
    "ProjectConfig",
    "ProjectManifest",
    "ScheduleDefinition",
    "ScheduleKind",
    "build_artifact_id",
    "build_qualified_job_id",
    "normalize_job",
    "normalize_manifest",
    "normalized_job_ids",
]
