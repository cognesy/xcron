"""Private best-effort logging helpers with no control-plane dependency."""

from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar


class _StructuredLogger:
    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def debug(self, event: str, **values: Any) -> None:
        self._logger.debug("%s %s", event, values)

    def info(self, event: str, **values: Any) -> None:
        self._logger.info("%s %s", event, values)

    def warning(self, event: str, **values: Any) -> None:
        self._logger.warning("%s %s", event, values)

    def error(self, event: str, **values: Any) -> None:
        self._logger.error("%s %s", event, values)


def get_logger(name: str) -> _StructuredLogger:
    return _StructuredLogger(logging.getLogger(name))


F = TypeVar("F", bound=Callable[..., Any])


def instrument_action(_: str) -> Callable[[F], F]:
    """Keep internal function instrumentation non-invasive and optional."""
    return lambda function: function
