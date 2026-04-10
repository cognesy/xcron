"""Typed CLI response envelopes for xcron's AXI edge."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class PayloadConvertible:
    """Mixin for response models that can become TOON payloads."""

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ErrorDetail(PayloadConvertible):
    field: str
    issue: str


@dataclass(frozen=True)
class ErrorResponse(PayloadConvertible):
    kind: str
    code: str
    message: str
    details: tuple[ErrorDetail, ...] = field(default_factory=tuple)
    help: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SummaryRow(PayloadConvertible):
    kind: str
    count: int


@dataclass(frozen=True)
class PlanChangeRow(PayloadConvertible):
    kind: str
    id: str
    reason: str


@dataclass(frozen=True)
class StatusRow(PayloadConvertible):
    kind: str
    id: str
    reason: str


@dataclass(frozen=True)
class JobListRow(PayloadConvertible):
    job_id: str
    enabled: bool
    schedule: str
    command: str


@dataclass(frozen=True)
class HomeJobsSummary(PayloadConvertible):
    total: int


@dataclass(frozen=True)
class HomeResponse(PayloadConvertible):
    bin: str
    description: str
    project: str
    schedule: str | None
    backend: str | None
    manifest: str | None
    jobs: HomeJobsSummary
    plan_summary: tuple[SummaryRow, ...]
    plan_changes: tuple[PlanChangeRow, ...] = field(default_factory=tuple)
    help: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ValidationSummaryResponse(PayloadConvertible):
    project: str
    manifest: str | None
    valid: bool
    jobs: int
    manifest_hash: str
    errors: int
    warnings: int
    warning_messages: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PlanResponse(PayloadConvertible):
    backend: str | None
    state: str | None
    count: str
    changes: tuple[PlanChangeRow, ...]
    help: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class StatusResponse(PayloadConvertible):
    backend: str | None
    count: str
    statuses: tuple[StatusRow, ...]
    help: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class InspectResponse(PayloadConvertible):
    backend: str | None
    job: str
    status: str
    desired: dict[str, Any]
    deployed: dict[str, Any]
    snippets: dict[str, Any]
    help: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class JobsListResponse(PayloadConvertible):
    manifest: str | None
    count: str
    jobs: tuple[JobListRow, ...]
    help: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class JobsShowResponse(PayloadConvertible):
    manifest: str | None
    job: str
    enabled: bool
    schedule: str
    command: str
    working_dir: str
    shell: str
    overlap: str
    description: str | None = None
    env: tuple[str, ...] = field(default_factory=tuple)
    help: tuple[str, ...] = field(default_factory=tuple)

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        if payload["description"] is None:
            payload.pop("description")
        if not payload["env"]:
            payload.pop("env")
        return payload


@dataclass(frozen=True)
class MutationResponse(PayloadConvertible):
    kind: str
    target: str | None
    outcome: str
    backend: str | None = None
    count: int | None = None
    manifest: str | None = None
    help: tuple[str, ...] = field(default_factory=tuple)

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        return {key: value for key, value in payload.items() if value is not None and value != ()}


__all__ = [
    "ErrorDetail",
    "ErrorResponse",
    "HomeJobsSummary",
    "HomeResponse",
    "InspectResponse",
    "JobListRow",
    "JobsListResponse",
    "JobsShowResponse",
    "MutationResponse",
    "PayloadConvertible",
    "PlanChangeRow",
    "PlanResponse",
    "StatusResponse",
    "StatusRow",
    "SummaryRow",
    "ValidationSummaryResponse",
]
