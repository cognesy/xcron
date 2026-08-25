"""The native provider's narrow subprocess boundary."""

from __future__ import annotations

import subprocess
from typing import Any, Sequence

from xcron.capabilities.scheduler_native.observability import get_logger

LOGGER = get_logger(__name__)


def run_logged_subprocess(
    command: Sequence[str], *, event: str, check: bool, **kwargs: Any
) -> subprocess.CompletedProcess[str]:
    """Run the native scheduler command without making logging a dependency."""
    LOGGER.debug("subprocess_started", process_event=event, command=tuple(command))
    result = subprocess.run(command, check=check, **kwargs)
    LOGGER.debug("subprocess_finished", process_event=event, returncode=result.returncode)
    return result


def check_output_logged(command: Sequence[str], *, event: str, **kwargs: Any) -> str:
    LOGGER.debug("subprocess_started", process_event=event, command=tuple(command))
    output = subprocess.check_output(command, **kwargs)
    LOGGER.debug("subprocess_finished", process_event=event, returncode=0)
    return output
