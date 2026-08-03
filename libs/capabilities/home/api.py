"""Public callable surface of the xcron home-initialization module.

Outside code imports this module and
:mod:`xcron_libs.capabilities.home.contracts`, and nothing else below this
package.
"""

from __future__ import annotations

from xcron_libs.capabilities.home.actions import init_home

__all__ = ["init_home"]
