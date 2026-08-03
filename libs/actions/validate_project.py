"""Compatibility import for the reconciliation validation capability."""

from xcron_libs.capabilities.reconciliation.validation import (
    ValidateProjectResult,
    build_failed_result,
    validate_project,
)

__all__ = ["ValidateProjectResult", "build_failed_result", "validate_project"]
