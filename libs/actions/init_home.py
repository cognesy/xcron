"""Compatibility import for the xcron-home capability."""

from xcron_libs.capabilities.home.api import init_home
from xcron_libs.capabilities.home.contracts import InitHomeResult

__all__ = ["InitHomeResult", "init_home"]
