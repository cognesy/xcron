"""Embeddable xcron SDK with no CLI or output-renderer dependency."""

from xcron.sdk.client import Xcron
from xcron.sdk.errors import ClientClosedError, HookError, UnknownBackendError, XcronError
from xcron.capabilities.jobs.contracts import (
    JobCreateRequest,
    JobUpdateField,
    JobUpdateRequest,
    ScheduleRequest,
)
from xcron.sdk.options import XcronOptions

__all__ = [
    "ClientClosedError",
    "HookError",
    "JobCreateRequest",
    "JobUpdateField",
    "JobUpdateRequest",
    "ScheduleRequest",
    "UnknownBackendError",
    "Xcron",
    "XcronError",
    "XcronOptions",
]
