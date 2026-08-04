"""Public value types and failures of the manifest module.

Every result, message, and typed error a caller can observe when reading,
validating, hashing, or editing a schedule manifest is declared here.
"""

from __future__ import annotations

from xcron.capabilities.manifest._editor import (
    ManifestEditError,
    ManifestEditValidationError,
    ManifestJobAlreadyExistsError,
    ManifestJobNotFoundError,
    ManifestMutationResult,
)
from xcron.capabilities.manifest._hashes import ManifestHashes, WRAPPER_RENDERER_VERSION
from xcron.capabilities.manifest._loader import (
    AmbiguousManifestSelectionError,
    LoadedManifestDocument,
    MANIFEST_SUFFIXES,
    ManifestLoadError,
    ManifestNotFoundError,
    ManifestParseError,
)
from xcron.capabilities.manifest._schema import SCHEMA_PACKAGE, ValidationMessage

__all__ = [
    "AmbiguousManifestSelectionError",
    "LoadedManifestDocument",
    "MANIFEST_SUFFIXES",
    "ManifestEditError",
    "ManifestEditValidationError",
    "ManifestHashes",
    "ManifestJobAlreadyExistsError",
    "ManifestJobNotFoundError",
    "ManifestLoadError",
    "ManifestMutationResult",
    "ManifestNotFoundError",
    "ManifestParseError",
    "SCHEMA_PACKAGE",
    "ValidationMessage",
    "WRAPPER_RENDERER_VERSION",
]
