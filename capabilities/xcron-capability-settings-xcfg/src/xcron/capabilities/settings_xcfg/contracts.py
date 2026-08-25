"""Public value types and failures of the configuration module.

This module is one of the two entry points outside code may import; the other
is :mod:`xcron.capabilities.settings_xcfg.api`.
"""

from __future__ import annotations

from xcron.capabilities.settings_xcfg.errors import ConfigurationError
from xcron.capabilities.settings_xcfg.loader import (
    CONFIG_ENV_NAME_VAR,
    CONFIG_NAME,
    CONFIG_PATH_ENV_VAR,
    ENV_SETTINGS,
)
from xcron.contracts import Settings

__all__ = [
    "CONFIG_ENV_NAME_VAR",
    "CONFIG_NAME",
    "CONFIG_PATH_ENV_VAR",
    "ENV_SETTINGS",
    "ConfigurationError",
    "Settings",
]
