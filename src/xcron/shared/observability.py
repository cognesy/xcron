"""Structured logging helpers for xcron actions and backend commands."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import functools
import logging
import sys
import time
from typing import Any, TypeVar

import structlog

from xcron.shared.logging_config import LoggingConfig, load_logging_config


F = TypeVar("F", bound=Callable[..., Any])

_CONFIGURED = False
# The stream object itself, not its ``id()``. Holding the reference keeps a
# replaced stream alive, so a later stream cannot reuse its address and be
# mistaken for the configured one -- which leaves the handlers pointing at a
# closed file and every subsequent log call raising.
_CONFIGURED_STREAM: Any = None
_CONFIGURED_LEVEL_NAME: str | None = None
_CONFIGURED_FORMAT: str | None = None
_CONFIGURED_CONFIG: LoggingConfig | None = None


def configure_logging() -> LoggingConfig:
    """Configure process-wide structured logging once."""
    global _CONFIGURED, _CONFIGURED_CONFIG, _CONFIGURED_FORMAT
    global _CONFIGURED_LEVEL_NAME, _CONFIGURED_STREAM

    config = load_logging_config()
    level_name = config.level
    level = getattr(logging, level_name, logging.INFO)
    log_format = config.format
    stream = sys.stderr
    if (
        _CONFIGURED
        and _CONFIGURED_LEVEL_NAME == level_name
        and _CONFIGURED_FORMAT == log_format
        and _CONFIGURED_STREAM is stream
        and _CONFIGURED_CONFIG == config
    ):
        return config

    renderer: structlog.typing.Processor
    if log_format == "json" or (log_format == "auto" and not sys.stderr.isatty()):
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    # `force` because `basicConfig` is otherwise a no-op once the root logger
    # has a handler, which would leave it writing to whatever stream was
    # current the first time this ran. The guard above means we only get here
    # when something actually changed.
    logging.basicConfig(stream=stream, level=level, format="%(message)s", force=True)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt=config.timestamp),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=stream),
        cache_logger_on_first_use=False,
    )
    _CONFIGURED = True
    _CONFIGURED_LEVEL_NAME = level_name
    _CONFIGURED_FORMAT = log_format
    _CONFIGURED_STREAM = stream
    _CONFIGURED_CONFIG = config
    return config


def get_logger(name: str) -> structlog.typing.FilteringBoundLogger:
    """Return a configured logger for one module or subsystem."""
    configure_logging()
    return structlog.get_logger(name)


def instrument_action(action_name: str) -> Callable[[F], F]:
    """Log action start, finish, and failure with common result fields."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            config = configure_logging()
            if not config.events.actions:
                return func(*args, **kwargs)
            logger = get_logger("xcron.action").bind(action=action_name)
            started = time.perf_counter()
            logger.info("action_started")
            try:
                result = func(*args, **kwargs)
            except Exception:
                logger.exception("action_failed", duration_ms=elapsed_ms(started))
                raise
            logger.info("action_finished", duration_ms=elapsed_ms(started), **result_log_fields(result))
            return result

        return wrapper  # type: ignore[return-value]

    return decorator


def result_log_fields(result: Any) -> dict[str, Any]:
    """Extract a small stable set of fields from action result objects."""
    fields: dict[str, Any] = {}
    for name in ("valid", "backend", "project_id", "state_path", "error"):
        value = getattr(result, name, None)
        if value is not None:
            fields[name] = value
    return fields


def preview(value: Any, *, limit: int = 400) -> str | None:
    """Return a compact preview for subprocess output fields."""
    if value in (None, ""):
        return None
    text = value.decode() if isinstance(value, bytes) else str(value)
    text = text.strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def redact_sequence(values: Sequence[str], patterns: Sequence[str]) -> list[str]:
    """Redact likely sensitive subprocess arguments before logging."""
    redacted: list[str] = []
    redact_next = False
    normalized_patterns = tuple(pattern.lower() for pattern in patterns if pattern)

    for value in values:
        if redact_next:
            redacted.append("[REDACTED]")
            redact_next = False
            continue

        text = str(value)
        flag_name, separator, _remainder = text.partition("=")
        lookup_name = flag_name.lstrip("-").lower()
        if separator and _matches_redaction_pattern(lookup_name, normalized_patterns):
            redacted.append(f"{flag_name}=[REDACTED]")
            continue

        if text.startswith("-") and _matches_redaction_pattern(lookup_name, normalized_patterns):
            redacted.append(text)
            redact_next = True
            continue

        redacted.append(text)

    return redacted


def _matches_redaction_pattern(value: str, patterns: Sequence[str]) -> bool:
    return any(pattern in value for pattern in patterns)


def elapsed_ms(started: float) -> int:
    """Return elapsed milliseconds since one monotonic start point."""
    return int((time.perf_counter() - started) * 1000)
