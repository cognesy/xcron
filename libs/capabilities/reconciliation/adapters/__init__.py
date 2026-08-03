"""Native scheduler adapters owned by the reconciliation module.

Each adapter implements the module's own ``SchedulerBackend`` port. Nothing
outside this module may import these; the registry in
:mod:`xcron_libs.capabilities.reconciliation.registry` is the only construction
site.
"""
