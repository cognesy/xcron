"""Logged subprocess execution for the native scheduler adapters.

`launchctl` and `crontab` are the only processes xcron shells out to, and both
are reconciliation adapters. The generic logging primitives these use stay in
:mod:`xcron_libs.shared.observability`; the subprocess policy does not.
"""

from __future__ import annotations

import subprocess
import time
from typing import Any, Sequence

from xcron_libs.shared.observability import (
    configure_logging,
    elapsed_ms,
    get_logger,
    preview,
    redact_sequence,
)


def run_logged_subprocess(
    command: Sequence[str],
    *,
    event: str,
    check: bool,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run one subprocess and emit structured start/finish/failure logs."""
    config = configure_logging()
    if not config.events.subprocesses:
        return subprocess.run(command, check=check, **kwargs)

    logger = get_logger("xcron.process").bind(
        process_event=event,
        command=redact_sequence(command, config.fields.redact),
    )
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
    config = configure_logging()
    if not config.events.subprocesses:
        return subprocess.check_output(command, **kwargs)

    logger = get_logger("xcron.process").bind(
        process_event=event,
        command=redact_sequence(command, config.fields.redact),
    )
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
