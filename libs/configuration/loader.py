"""Compose settings from packaged defaults, files, and the environment.

This is the only module in xcron that imports `xcfg`, and the only one that
reads a settings environment variable. Both facts are enforced by a contract
test — the value of "resolved once" collapses the moment a second reader
appears downstream and starts disagreeing.

Layer order, later winning:

1. the packaged ``config.default.yaml`` shipped beside this file
2. a named env config (``XCRON_ENV=<name>``), layered over the default
3. the user config at ``${XDG_CONFIG_HOME}/xcron/config.yaml``
4. the workspace config at ``<workspace>/config.yaml``
5. the flat ``XCRON_*`` environment variables listed in :data:`ENV_SETTINGS`

An explicit file — the ``config_path`` argument or ``XCRON_CONFIG`` — replaces
layers 1 and 2 outright rather than merging over them.

Command-line flags and SDK keyword arguments are deliberately *not* a layer
here. They are applied by the composition root over the result, so a flag
always beats configuration without this module needing to know a flag exists.

xcron's environment contract is flat and predates this module
(``XCRON_STATE_ROOT``, not ``XCRON_HOST__STATE_ROOT``), so `xcfg`'s own nested
env layer stays disabled and :data:`ENV_SETTINGS` maps the published names onto
settings keys explicitly. That mapping table *is* the contract; adding a
variable means adding a row.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from xcfg import ConfigLoader, ConfigSpec
from xcfg import ConfigError as XcfgConfigError

from xcron_libs.configuration.errors import ConfigurationError
from xcron_libs.configuration.settings import Settings

#: Filename of the user and workspace configuration files.
CONFIG_NAME = "config.yaml"

#: Environment variable naming an explicit configuration file.
CONFIG_PATH_ENV_VAR = "XCRON_CONFIG"

#: Environment variable selecting a packaged named configuration.
CONFIG_ENV_NAME_VAR = "XCRON_ENV"

#: Published environment variable -> settings key. The published names are flat
#: by history; the settings keys are the model's field names.
ENV_SETTINGS: dict[str, str] = {
    "XCRON_STATE_ROOT": "state_root",
    "XCRON_LAUNCH_AGENTS_DIR": "launch_agents_dir",
    "XCRON_LAUNCHCTL_DOMAIN": "launchctl_domain",
    "XCRON_CRONTAB_PATH": "crontab_path",
    "XCRON_MANAGE_LAUNCHCTL": "manage_launchctl",
    "XCRON_MANAGE_CRONTAB": "manage_crontab",
}

#: Settings keys whose environment value is a flag rather than a string.
_FLAG_SETTINGS = frozenset({"manage_launchctl", "manage_crontab"})

#: Values that turn a flag off. Every other non-empty value turns it on. This
#: set is copied from the CLI helper this module replaced, so adopting layered
#: configuration did not quietly re-interpret anyone's exported variables.
_FALSE_VALUES = frozenset({"0", "false", "False", "no", "NO"})

SPEC = ConfigSpec(
    config_root=Path(__file__).resolve().parent / "resources" / "config",
    config_name=CONFIG_NAME,
    app_name="xcron",
    config_env_var=CONFIG_PATH_ENV_VAR,
    env_name_var=CONFIG_ENV_NAME_VAR,
    env_extends_default=True,
    # Disabled on purpose: see the module docstring. `ENV_SETTINGS` is the
    # environment layer, and it is xcron's to define.
    env_prefix="",
    # Disabled on purpose: the workspace module resolves the project root, so
    # the loader must never walk up from the working directory and find a
    # different one.
    project_dir="",
)

LOADER = ConfigLoader(SPEC, Settings)


def environment_overrides(environ: Mapping[str, str]) -> dict[str, str]:
    """Translate the published flat variables into settings overrides.

    An unset or empty variable contributes nothing, so exporting ``XCRON_STATE_ROOT=``
    is the same as not exporting it — the behaviour callers already relied on.
    """
    overrides: dict[str, str] = {}
    for variable, key in ENV_SETTINGS.items():
        raw = environ.get(variable)
        if not raw:
            continue
        if key in _FLAG_SETTINGS:
            overrides[key] = "false" if raw in _FALSE_VALUES else "true"
        else:
            overrides[key] = raw
    return overrides


def load_settings(
    *,
    workspace_config_path: Path | None = None,
    config_path: Path | None = None,
    env_name: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """Compose and validate the effective settings for one invocation.

    `workspace_config_path` is the workspace layer, named directly because the
    workspace module resolved it; passing ``None`` omits that layer.
    """
    env = dict(os.environ if environ is None else environ)
    try:
        return LOADER.load(
            config_path=config_path,
            env_name=env_name,
            environ=env,
            project_path=workspace_config_path,
            overrides=environment_overrides(env),
        )
    except XcfgConfigError as exc:
        raise ConfigurationError(str(exc)) from exc


__all__ = [
    "CONFIG_ENV_NAME_VAR",
    "CONFIG_NAME",
    "CONFIG_PATH_ENV_VAR",
    "ENV_SETTINGS",
    "environment_overrides",
    "load_settings",
]
