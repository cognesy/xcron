"""Public callable surface of the manifest module.

Outside code imports this module and
:mod:`xcron.capabilities.manifest_yaml.contracts`, and nothing else below this
package. Every manifest write on disk goes through one of the mutation
functions here, so the module stays the single writer of the format it owns.
"""

from __future__ import annotations

from xcron.capabilities.manifest_yaml._editor import (
    add_manifest_job,
    get_manifest_job,
    list_manifest_jobs,
    remove_manifest_job,
    set_manifest_job_enabled,
    update_manifest_job,
)
from xcron.capabilities.manifest_yaml._hashes import (
    build_manifest_hashes,
    hash_normalized_job,
    hash_normalized_job_definition,
    hash_normalized_manifest,
    stable_hash,
)
from xcron.capabilities.manifest_yaml._loader import (
    attach_parsed_manifest,
    load_manifest_data,
    load_project_manifest,
    parse_job_definition,
    parse_project_manifest,
    resolve_manifest_path,
)
from xcron.capabilities.manifest_yaml._schema import (
    load_schema,
    split_validation_messages,
    validate_schema,
    validate_semantics,
)

__all__ = [
    "add_manifest_job",
    "attach_parsed_manifest",
    "build_manifest_hashes",
    "get_manifest_job",
    "hash_normalized_job",
    "hash_normalized_job_definition",
    "hash_normalized_manifest",
    "list_manifest_jobs",
    "load_manifest_data",
    "load_project_manifest",
    "load_schema",
    "parse_job_definition",
    "parse_project_manifest",
    "remove_manifest_job",
    "resolve_manifest_path",
    "set_manifest_job_enabled",
    "split_validation_messages",
    "stable_hash",
    "update_manifest_job",
    "validate_schema",
    "validate_semantics",
]
