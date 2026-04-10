"""Typed CLI response envelopes for xcron's AXI edge."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class PayloadConvertible(BaseModel):
    """Base response model that can be rendered at the CLI edge."""

    model_config = ConfigDict(extra="forbid")

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump()


class ErrorDetail(PayloadConvertible):
    field: str
    issue: str


class ErrorResponse(PayloadConvertible):
    kind: str
    code: str
    message: str
    details: tuple[ErrorDetail, ...] = ()
    help: tuple[str, ...] = ()


class SummaryRow(PayloadConvertible):
    kind: str
    count: int


class PlanChangeRow(PayloadConvertible):
    kind: str
    id: str
    reason: str


class StatusRow(PayloadConvertible):
    kind: str
    id: str
    reason: str


class JobListRow(PayloadConvertible):
    job_id: str
    enabled: bool
    schedule: str
    command: str


class HomeJobsSummary(PayloadConvertible):
    total: int


class HomeResponse(PayloadConvertible):
    bin: str
    description: str
    project: str
    schedule: Optional[str]
    backend: Optional[str]
    manifest: Optional[str]
    jobs: HomeJobsSummary
    plan_summary: tuple[SummaryRow, ...]
    plan_changes: tuple[PlanChangeRow, ...] = ()
    help: tuple[str, ...] = ()


class ValidationSummaryResponse(PayloadConvertible):
    project: str
    manifest: Optional[str]
    valid: bool
    jobs: int
    manifest_hash: str
    errors: int
    warnings: int
    warning_messages: tuple[str, ...] = ()


class PlanResponse(PayloadConvertible):
    backend: Optional[str]
    state: Optional[str]
    count: str
    changes: tuple[PlanChangeRow, ...]
    help: tuple[str, ...] = ()


class StatusResponse(PayloadConvertible):
    backend: Optional[str]
    count: str
    statuses: tuple[StatusRow, ...]
    help: tuple[str, ...] = ()


class InspectResponse(PayloadConvertible):
    backend: Optional[str]
    job: str
    status: str
    desired: dict[str, Any]
    deployed: dict[str, Any]
    snippets: dict[str, Any]
    help: tuple[str, ...] = ()


class JobsListResponse(PayloadConvertible):
    manifest: Optional[str]
    count: str
    jobs: tuple[JobListRow, ...]
    help: tuple[str, ...] = ()


class JobsShowResponse(PayloadConvertible):
    manifest: Optional[str]
    job: str
    enabled: bool
    schedule: str
    command: str
    working_dir: str
    shell: str
    overlap: str
    description: Optional[str] = None
    env: tuple[str, ...] = ()
    help: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True, exclude={"env"} if not self.env else None)


class MutationResponse(PayloadConvertible):
    kind: str
    target: Optional[str]
    outcome: str
    backend: Optional[str] = None
    count: Optional[int] = None
    manifest: Optional[str] = None
    help: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True, exclude={"help"} if not self.help else None)


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
