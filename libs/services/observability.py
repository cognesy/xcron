"""Structured logging helpers for xcron actions and backend commands."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import functools
import logging
import os
import subprocess
import sys
import time
from typing import Any, TypeVar

import structlog


F = TypeVar("F", bound=Callable[..., Any])

_CONFIGURED = False
_CONFIGURED_STREAM_ID: int | None = None
_CONFIGURED_LEVEL_NAME: str | None = None
_CONFIGURED_FORMAT: str | None = None


def configure_logging() -> None:
    """Configure process-wide structured logging once."""
    global _CONFIGURED, _CONFIGURED_FORMAT, _CONFIGURED_LEVEL_NAME, _CONFIGURED_STREAM_ID

    level_name = os.environ.get("XCRON_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log_format = os.environ.get("XCRON_LOG_FORMAT", "auto").lower()
    stream_id = id(sys.stderr)
    if (
        _CONFIGURED
        and _CONFIGURED_LEVEL_NAME == level_name
        and _CONFIGURED_FORMAT == log_format
        and _CONFIGURED_STREAM_ID == stream_id
    ):
        return

    renderer: structlog.typing.Processor
    if log_format == "json" or (log_format == "auto" and not sys.stderr.isatty()):
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    logging.basicConfig(stream=sys.stderr, level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )
    _CONFIGURED = True
    _CONFIGURED_LEVEL_NAME = level_name
    _CONFIGURED_FORMAT = log_format
    _CONFIGURED_STREAM_ID = stream_id


def get_logger(name: str) -> structlog.typing.FilteringBoundLogger:
    """Return a configured logger for one module or subsystem."""
    configure_logging()
    return structlog.get_logger(name)


def instrument_action(action_name: str) -> Callable[[F], F]:
    """Log action start, finish, and failure with common result fields."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            configure_logging()
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


def run_logged_subprocess(
    command: Sequence[str],
    *,
    event: str,
    check: bool,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run one subprocess and emit structured start/finish/failure logs."""
    configure_logging()
    logger = get_logger("xcron.process").bind(process_event=event, command=list(command))
    started = time.perf_counter()
    logger.info("subprocess_started")
    try:
        result = subprocess.run(command, check=check, **kwargs)
    except subprocess.CalledProcessError as exc:
        logger.error(
            "subprocess_failed",
            duration_ms=elapsed_ms(started),
            returncode=exc.returncode,
            stdout_preview=preview(getattr(exc, "stdout", None)),
            stderr_preview=preview(getattr(exc, "stderr", None)),
        )
        raise
    except Exception:
        logger.exception("subprocess_failed", duration_ms=elapsed_ms(started))
        raise

    logger.info(
        "subprocess_finished",
        duration_ms=elapsed_ms(started),
        returncode=result.returncode,
        stdout_preview=preview(getattr(result, "stdout", None)),
        stderr_preview=preview(getattr(result, "stderr", None)),
    )
    return result


def check_output_logged(command: Sequence[str], *, event: str, **kwargs: Any) -> str:
    """Run subprocess.check_output with structured logs."""
    configure_logging()
    logger = get_logger("xcron.process").bind(process_event=event, command=list(command))
    started = time.perf_counter()
    logger.info("subprocess_started")
    try:
        output = subprocess.check_output(command, **kwargs)
    except subprocess.CalledProcessError as exc:
        logger.error(
            "subprocess_failed",
            duration_ms=elapsed_ms(started),
            returncode=exc.returncode,
            stdout_preview=preview(getattr(exc, "output", None)),
            stderr_preview=preview(getattr(exc, "stderr", None)),
        )
        raise
    except Exception:
        logger.exception("subprocess_failed", duration_ms=elapsed_ms(started))
        raise

    logger.info(
        "subprocess_finished",
        duration_ms=elapsed_ms(started),
        returncode=0,
        stdout_preview=preview(output),
    )
    return output


def preview(value: Any, *, limit: int = 400) -> str | None:
    """Return a compact preview for subprocess output fields."""
    if value in (None, ""):
        return None
    text = value.decode() if isinstance(value, bytes) else str(value)
    text = text.strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def elapsed_ms(started: float) -> int:
    """Return elapsed milliseconds since one monotonic start point."""
    return int((time.perf_counter() - started) * 1000)
