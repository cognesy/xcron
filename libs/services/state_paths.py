"""Location of xcron's machine-local derived state root.

Only *where* derived state lives is shared. What is written into it belongs to
the module that owns the file: reconciliation owns ``project-state.json``,
operations owns logs and metrics.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys


STATE_ENV_VAR = "XCRON_STATE_ROOT"


def resolve_state_root(
    platform: str | None = None,
    home: Path | None = None,
    env: dict[str, str] | None = None,
) -> Path:
    """Resolve the machine-local derived state root for xcron."""
    env_map = os.environ if env is None else env
    override = env_map.get(STATE_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()

    selected_home = Path.home() if home is None else Path(home)
    selected = sys.platform if platform is None else platform
    if selected.startswith(("darwin", "linux")):
        return (selected_home / ".xcron").resolve()
    raise ValueError(f"unsupported platform for xcron prototype: {selected}")


def resolve_project_state_dir(project_id: str, state_root: Path | None = None) -> Path:
    """Resolve the per-project derived state directory."""
    root = resolve_state_root() if state_root is None else Path(state_root).expanduser().resolve()
    return root / "projects" / project_id
