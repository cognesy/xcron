"""Compatibility import for the reconciliation apply capability."""

from xcron_libs.capabilities.reconciliation.api import apply_project
from xcron_libs.capabilities.reconciliation.contracts import ApplyProjectResult

__all__ = ["ApplyProjectResult", "apply_project"]
