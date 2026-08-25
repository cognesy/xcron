"""Embeddable xcron SDK with no CLI or output-renderer dependency."""

from xcron.contracts import (
    JobCreateRequest,
    JobUpdateField,
    JobUpdateRequest,
    ScheduleRequest,
    XcronOptions,
)
from xcron.sdk.client import Xcron
from xcron.sdk.errors import ClientClosedError, HookError, UnknownBackendError, XcronError

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
