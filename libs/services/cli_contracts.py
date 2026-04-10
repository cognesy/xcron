"""Central machine-output policy metadata for xcron CLI commands."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CommandContract:
    """Declarative CLI-edge contract for one command or command family."""

    name: str
    default_fields: tuple[str, ...]
    allowed_fields: tuple[str, ...]
    nested_fields: dict[str, tuple[str, ...]] = field(default_factory=dict)
    collection_fields: dict[str, tuple[str, ...]] = field(default_factory=dict)
    list_key: str | None = None
    list_row_fields: tuple[str, ...] = field(default_factory=tuple)
    truncation_limit: int | None = None
    default_hints: tuple[str, ...] = field(default_factory=tuple)


HOME_CONTRACT = CommandContract(
    name="home",
    default_fields=("bin", "description", "project", "schedule", "backend", "manifest", "jobs", "plan_summary", "help"),
    allowed_fields=("bin", "description", "project", "schedule", "backend", "manifest", "jobs", "plan_summary", "plan_changes", "help"),
    nested_fields={"jobs": ("total",)},
    collection_fields={
        "plan_summary": ("kind", "count"),
        "plan_changes": ("kind", "id", "reason"),
    },
    default_hints=(
        "Run `xcron validate` to confirm manifest validity",
        "Run `xcron plan` to preview scheduler changes",
        "Run `xcron status` to inspect actual backend state",
    ),
)

VALIDATE_CONTRACT = CommandContract(
    name="validate",
    default_fields=("project", "manifest", "valid", "jobs", "manifest_hash", "errors", "warnings"),
    allowed_fields=("project", "manifest", "valid", "jobs", "manifest_hash", "errors", "warnings", "warning_messages"),
    default_hints=("Run `xcron validate --help` to review command usage",),
)

PLAN_CONTRACT = CommandContract(
    name="plan",
    default_fields=("backend", "state", "count", "changes"),
    allowed_fields=("backend", "state", "count", "changes", "help"),
    list_key="changes",
    list_row_fields=("kind", "id", "reason"),
    default_hints=(
        "Run `xcron apply` to reconcile the selected manifest",
        "Run `xcron status` to inspect actual deployed backend state",
    ),
)

APPLY_CONTRACT = CommandContract(
    name="apply",
    default_fields=("kind", "target", "outcome", "backend", "count"),
    allowed_fields=("kind", "target", "outcome", "backend", "count", "manifest", "help"),
    default_hints=(
        "Run `xcron status` to confirm deployed backend state",
        "Run `xcron inspect <job-id>` for one detailed post-apply view",
    ),
)

STATUS_CONTRACT = CommandContract(
    name="status",
    default_fields=("backend", "count", "statuses"),
    allowed_fields=("backend", "count", "statuses", "help"),
    list_key="statuses",
    list_row_fields=("kind", "id", "reason"),
    default_hints=(
        "Run `xcron inspect <job-id>` for one detailed job view",
        "Run `xcron apply` to reconcile drift or missing jobs",
    ),
)

INSPECT_CONTRACT = CommandContract(
    name="inspect",
    default_fields=("backend", "job", "status", "desired", "deployed", "snippets"),
    allowed_fields=("backend", "job", "status", "desired", "deployed", "snippets", "help"),
    nested_fields={
        "desired": ("qualified_id", "job_id", "status", "schedule", "enabled", "command", "working_dir", "shell", "overlap", "description", "timezone", "env"),
        "deployed": ("qualified_id", "backend_enabled", "desired_hash", "definition_hash", "label", "artifact_path", "wrapper_path", "stdout_log", "stderr_log", "loaded"),
    },
    truncation_limit=1000,
    default_hints=("Run `xcron status` to compare the full project against backend state",),
)

JOBS_LIST_CONTRACT = CommandContract(
    name="jobs.list",
    default_fields=("manifest", "count", "jobs"),
    allowed_fields=("manifest", "count", "jobs", "help"),
    list_key="jobs",
    list_row_fields=("job_id", "enabled", "schedule", "command"),
    default_hints=(
        "Run `xcron jobs show <job-id>` to inspect one manifest job",
        "Run `xcron apply` to reconcile manifest changes into backend state",
    ),
)

JOBS_SHOW_CONTRACT = CommandContract(
    name="jobs.show",
    default_fields=("manifest", "job", "enabled", "schedule", "command", "working_dir", "shell", "overlap"),
    allowed_fields=("manifest", "job", "enabled", "schedule", "command", "working_dir", "shell", "overlap", "description", "env", "help"),
    default_hints=("Run `xcron inspect <job-id>` for backend-side detail",),
)

JOBS_ADD_CONTRACT = CommandContract(
    name="jobs.add",
    default_fields=("kind", "target", "outcome", "manifest"),
    allowed_fields=("kind", "target", "outcome", "manifest", "help"),
    default_hints=(
        "Run `xcron jobs show <job-id>` to inspect the manifest-side result",
        "Run `xcron apply` to reconcile backend state after manifest edits",
    ),
)

JOBS_REMOVE_CONTRACT = CommandContract(
    name="jobs.remove",
    default_fields=("kind", "target", "outcome", "manifest"),
    allowed_fields=("kind", "target", "outcome", "manifest", "help"),
    default_hints=JOBS_ADD_CONTRACT.default_hints,
)

JOBS_ENABLE_CONTRACT = CommandContract(
    name="jobs.enable",
    default_fields=("kind", "target", "outcome", "manifest"),
    allowed_fields=("kind", "target", "outcome", "manifest", "help"),
    default_hints=JOBS_ADD_CONTRACT.default_hints,
)

JOBS_DISABLE_CONTRACT = CommandContract(
    name="jobs.disable",
    default_fields=("kind", "target", "outcome", "manifest"),
    allowed_fields=("kind", "target", "outcome", "manifest", "help"),
    default_hints=JOBS_ADD_CONTRACT.default_hints,
)

JOBS_UPDATE_CONTRACT = CommandContract(
    name="jobs.update",
    default_fields=("kind", "target", "outcome", "manifest"),
    allowed_fields=("kind", "target", "outcome", "manifest", "help"),
    default_hints=JOBS_ADD_CONTRACT.default_hints,
)

PRUNE_CONTRACT = CommandContract(
    name="prune",
    default_fields=("kind", "target", "outcome", "backend", "count"),
    allowed_fields=("kind", "target", "outcome", "backend", "count", "help"),
    default_hints=("Run `xcron apply` to recreate managed backend state from the manifest",),
)

HOOKS_INSTALL_CONTRACT = CommandContract(
    name="hooks.install",
    default_fields=("kind", "changed", "files"),
    allowed_fields=("kind", "changed", "files"),
)

HOOKS_SESSION_START_CONTRACT = CommandContract(
    name="hooks.session-start",
    default_fields=("bin", "project", "manifest", "backend", "jobs", "plan_summary"),
    allowed_fields=("bin", "project", "manifest", "backend", "jobs", "plan_summary", "help"),
    collection_fields={"plan_summary": ("kind", "count")},
)

HOOKS_SESSION_END_CONTRACT = CommandContract(
    name="hooks.session-end",
    default_fields=("kind", "log"),
    allowed_fields=("kind", "log"),
)

COMMAND_CONTRACTS: dict[str, CommandContract] = {
    contract.name: contract
    for contract in (
        HOME_CONTRACT,
        VALIDATE_CONTRACT,
        PLAN_CONTRACT,
        APPLY_CONTRACT,
        STATUS_CONTRACT,
        INSPECT_CONTRACT,
        JOBS_LIST_CONTRACT,
        JOBS_SHOW_CONTRACT,
        JOBS_ADD_CONTRACT,
        JOBS_REMOVE_CONTRACT,
        JOBS_ENABLE_CONTRACT,
        JOBS_DISABLE_CONTRACT,
        JOBS_UPDATE_CONTRACT,
        PRUNE_CONTRACT,
        HOOKS_INSTALL_CONTRACT,
        HOOKS_SESSION_START_CONTRACT,
        HOOKS_SESSION_END_CONTRACT,
    )
}


def get_command_contract(name: str) -> CommandContract:
    """Return one CLI contract by name."""

    try:
        return COMMAND_CONTRACTS[name]
    except KeyError as exc:
        raise KeyError(f"unknown xcron CLI contract: {name}") from exc


def allowed_request_fields(contract: CommandContract) -> tuple[str, ...]:
    """Return the full set of requestable field names for one contract."""

    fields: list[str] = list(contract.allowed_fields)
    fields.extend(contract.list_row_fields)
    for parent_key, allowed in contract.nested_fields.items():
        fields.append(parent_key)
        fields.extend(f"{parent_key}.{field}" for field in allowed)
    for _, allowed in contract.collection_fields.items():
        fields.extend(allowed)
    return tuple(dict.fromkeys(fields))


def validate_requested_fields(contract: CommandContract, requested_fields: tuple[str, ...]) -> tuple[str, ...]:
    """Validate one requested field list against the command contract."""

    if not requested_fields:
        return requested_fields
    allowed = set(allowed_request_fields(contract))
    invalid = tuple(field for field in requested_fields if field not in allowed)
    if invalid:
        allowed_text = ", ".join(sorted(allowed))
        invalid_text = ", ".join(invalid)
        raise ValueError(f"unknown field selection: {invalid_text}; allowed fields: {allowed_text}")
    return requested_fields


__all__ = [
    "COMMAND_CONTRACTS",
    "CommandContract",
    "get_command_contract",
    "allowed_request_fields",
    "validate_requested_fields",
]
