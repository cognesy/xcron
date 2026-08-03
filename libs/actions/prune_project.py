"""Compatibility import for the reconciliation prune capability."""

from xcron_libs.capabilities.reconciliation.api import prune_project
from xcron_libs.capabilities.reconciliation.contracts import PruneProjectResult

__all__ = ["PruneProjectResult", "prune_project"]
