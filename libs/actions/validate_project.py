"""Compatibility import for the reconciliation validation capability."""

from xcron_libs.capabilities.reconciliation.api import validate_project
from xcron_libs.capabilities.reconciliation.contracts import ValidateProjectResult

__all__ = ["ValidateProjectResult", "validate_project"]
