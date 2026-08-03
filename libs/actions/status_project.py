"""Compatibility import for the reconciliation status capability."""

from xcron_libs.capabilities.reconciliation.api import status_project
from xcron_libs.capabilities.reconciliation.contracts import StatusProjectResult

__all__ = ["StatusProjectResult", "status_project"]
