"""Initialize the xcron home directory with a starter schedule manifest."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from libs.services import get_logger, instrument_action
from libs.services.config_loader import MANIFEST_DIR, resolve_xcron_home

LOGGER = get_logger(__name__)

STARTER_MANIFEST = """\
version: 1
project:
  id: my-schedules
defaults:
  working_dir: "~"
  shell: /bin/sh
jobs: []
"""


@dataclass(frozen=True)
class InitHomeResult:
    """Structured result for the init use case."""

    xcron_home: str
    schedules_dir: str
    manifest_path: str
    created: bool


@instrument_action("init_home")
def init_home(*, xcron_home: Path | None = None) -> InitHomeResult:
    """Create ~/.xcron/schedules/ and a starter manifest if absent."""
    home = xcron_home or resolve_xcron_home()
    schedules_dir = home / MANIFEST_DIR
    schedules_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = schedules_dir / "default.yaml"
    if manifest_path.exists():
        LOGGER.info("manifest_exists", manifest_path=str(manifest_path))
        return InitHomeResult(
            xcron_home=str(home),
            schedules_dir=str(schedules_dir),
            manifest_path=str(manifest_path),
            created=False,
        )

    manifest_path.write_text(STARTER_MANIFEST, encoding="utf-8")
    LOGGER.info("manifest_created", manifest_path=str(manifest_path))
    return InitHomeResult(
        xcron_home=str(home),
        schedules_dir=str(schedules_dir),
        manifest_path=str(manifest_path),
        created=True,
    )
