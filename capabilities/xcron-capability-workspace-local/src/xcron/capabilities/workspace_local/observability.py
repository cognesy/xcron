"""Dependency-free events until the host wires the observability provider."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
import json
import logging
from typing import Any, TypeVar


F = TypeVar("F", bound=Callable[..., Any])


class _EventLogger:
    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def info(self, event: str, **fields: object) -> None:
        self._logger.info(_event_payload(event, "info", fields))

    def warning(self, event: str, **fields: object) -> None:
        self._logger.warning(_event_payload(event, "warning", fields))


def get_logger(name: str) -> _EventLogger:
    return _EventLogger(name)


def instrument_action(action_name: str) -> Callable[[F], F]:
    def decorate(function: F) -> F:
        @wraps(function)
        def invoke(*args: Any, **kwargs: Any) -> Any:
            return function(*args, **kwargs)

        return invoke  # type: ignore[return-value]

    return decorate


def _event_payload(event: str, level: str, fields: dict[str, object]) -> str:
    """Keep pre-host workspace advisories structured on the process stderr."""
    return json.dumps({"event": event, "level": level, **fields}, default=str, sort_keys=True)
