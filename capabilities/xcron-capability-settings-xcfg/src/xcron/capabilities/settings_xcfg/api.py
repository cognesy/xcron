"""Public callable surface of the configuration module.

Outside code imports this module and
:mod:`xcron.capabilities.settings_xcfg.contracts`, and nothing else below this package.
"""

from __future__ import annotations

from xcron.capabilities.settings_xcfg.loader import environment_overrides, load_settings

__all__ = ["environment_overrides", "load_settings"]
