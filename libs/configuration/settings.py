"""The settings model — xcron's own, validated strictly.

`extra="forbid"` is the point of this file. Without it a typo in a config file
is silently ignored and the default applies, which is the failure mode that
costs an afternoon. With it, ``manage_lanchctl: false`` fails loudly and names
the field.

Every field here is host and scheduler policy. Nothing that identifies *which*
workspace is in scope appears in this model.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    """Effective host and scheduler settings for one invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Machine-local root for derived state. ``None`` means "let the workspace
    #: module derive the platform default".
    state_root: Path | None = None

    #: Directory launchd agent plists are written to, when unset the backend
    #: uses its platform default.
    launch_agents_dir: Path | None = None

    #: launchd domain target, e.g. ``gui/501``.
    launchctl_domain: str | None = None

    #: crontab file the cron backend reads and writes.
    crontab_path: Path | None = None

    #: Whether the launchd backend may call ``launchctl``. False makes apply a
    #: file-only operation, which is what the integration lanes need.
    manage_launchctl: bool = True

    #: Whether the cron backend may install the rendered crontab.
    manage_crontab: bool = True


__all__ = ["Settings"]
