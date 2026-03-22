"""Schema and semantic validation for xcron manifests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import jsonschema
import yaml

from libs.domain.models import ProjectManifest, ScheduleKind, SUPPORTED_EVERY_SUFFIXES, resolve_working_dir


CRON_FIELD_PATTERN = re.compile(r"^[0-9A-Za-z*/,\-]+$")
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "resources" / "schemas" / "schedules.schema.yaml"


@dataclass(frozen=True)
class ValidationMessage:
    """Structured validation message emitted by schema or semantic checks."""

    level: str
    path: str
    message: str


def load_schema(schema_path: Path | None = None) -> Mapping[str, Any]:
    """Load the JSON Schema document used to validate schedule manifests."""
    target = SCHEMA_PATH if schema_path is None else Path(schema_path)
    with target.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, Mapping):
        raise ValueError(f"schema root must be a mapping: {target}")
    return loaded


def validate_schema(raw_data: Mapping[str, Any], schema: Mapping[str, Any] | None = None) -> tuple[ValidationMessage, ...]:
    """Validate manifest data against the static JSON Schema."""
    validator = jsonschema.Draft202012Validator(load_schema() if schema is None else schema)
    messages = []
    for error in sorted(validator.iter_errors(raw_data), key=lambda item: (list(item.absolute_path), item.message)):
        path = "/" + "/".join(str(part) for part in error.absolute_path)
        messages.append(
            ValidationMessage(
                level="error",
                path=path or "/",
                message=error.message,
            )
        )
    return tuple(messages)


def validate_semantics(manifest: ProjectManifest, project_root: Path) -> tuple[ValidationMessage, ...]:
    """Validate manifest rules that live above the static schema layer."""
    messages: list[ValidationMessage] = []
    seen_job_ids: set[str] = set()

    defaults = manifest.defaults
    if not defaults.shell.strip():
        messages.append(ValidationMessage(level="error", path="/defaults/shell", message="defaults.shell must not be empty"))
    if defaults.timezone is not None:
        validate_timezone(defaults.timezone, "/defaults/timezone", messages)

    for index, job in enumerate(manifest.jobs):
        job_path = f"/jobs/{index}"
        if job.id in seen_job_ids:
            messages.append(ValidationMessage(level="error", path=f"{job_path}/id", message=f"duplicate job id: {job.id}"))
        seen_job_ids.add(job.id)

        if not job.command.strip():
            messages.append(ValidationMessage(level="error", path=f"{job_path}/command", message="command must not be empty"))
        if job.shell is not None and not job.shell.strip():
            messages.append(ValidationMessage(level="error", path=f"{job_path}/shell", message="shell must not be empty"))

        validate_schedule(job.schedule.kind, job.schedule.value, f"{job_path}/schedule", messages)

        working_dir_value = job.working_dir or defaults.working_dir
        resolved_working_dir = Path(resolve_working_dir(project_root, working_dir_value))
        if not resolved_working_dir.exists():
            messages.append(
                ValidationMessage(
                    level="error",
                    path=f"{job_path}/working_dir",
                    message=f"working directory does not exist: {resolved_working_dir}",
                )
            )
        elif not resolved_working_dir.is_dir():
            messages.append(
                ValidationMessage(
                    level="error",
                    path=f"{job_path}/working_dir",
                    message=f"working directory is not a directory: {resolved_working_dir}",
                )
            )

    return tuple(messages)


def validate_schedule(kind: ScheduleKind, value: str, path: str, messages: list[ValidationMessage]) -> None:
    """Validate schedule semantics beyond the JSON Schema."""
    if kind is ScheduleKind.CRON:
        fields = value.split()
        if len(fields) != 5:
            messages.append(
                ValidationMessage(
                    level="error",
                    path=f"{path}/cron",
                    message="cron expressions must contain exactly 5 fields in xcron v1",
                )
            )
            return
        invalid_fields = [field for field in fields if not CRON_FIELD_PATTERN.fullmatch(field)]
        if invalid_fields:
            messages.append(
                ValidationMessage(
                    level="error",
                    path=f"{path}/cron",
                    message=f"cron expression contains unsupported field syntax: {', '.join(invalid_fields)}",
                )
            )
        return

    suffix = value[-1:]
    if suffix not in SUPPORTED_EVERY_SUFFIXES:
        messages.append(
            ValidationMessage(
                level="error",
                path=f"{path}/every",
                message=f"unsupported every suffix: {suffix}",
            )
        )


def validate_timezone(timezone: str, path: str, messages: list[ValidationMessage]) -> None:
    """Validate that an IANA timezone exists locally."""
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        messages.append(ValidationMessage(level="error", path=path, message=f"unknown timezone: {timezone}"))


def split_validation_messages(messages: Sequence[ValidationMessage]) -> tuple[tuple[ValidationMessage, ...], tuple[ValidationMessage, ...]]:
    """Split a mixed validation result into errors and warnings."""
    errors = tuple(message for message in messages if message.level == "error")
    warnings = tuple(message for message in messages if message.level != "error")
    return errors, warnings
