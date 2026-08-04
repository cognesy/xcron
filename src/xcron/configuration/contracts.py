"""Public value types and failures of the configuration module.

This module is one of the two entry points outside code may import; the other
is :mod:`xcron.configuration.api`.
"""

from __future__ import annotations

from xcron.configuration.errors import ConfigurationError
from xcron.configuration.loader import (
    CONFIG_ENV_NAME_VAR,
    CONFIG_NAME,
    CONFIG_PATH_ENV_VAR,
    ENV_SETTINGS,
)
from xcron.configuration.settings import Settings

__all__ = [
    "CONFIG_ENV_NAME_VAR",
    "CONFIG_NAME",
    "CONFIG_PATH_ENV_VAR",
    "ENV_SETTINGS",
    "ConfigurationError",
    "Settings",
]
