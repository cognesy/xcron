"""Public native-scheduler compatibility surface built from xcron contracts."""

from xcron.contracts import (
    ApplyProjectResult,
    DeployedJobState,
    InspectField,
    InspectJobResult,
    InspectSnippet,
    PlanChange,
    PlanChangeKind,
    PlanProjectResult,
    ProjectPlan,
    ProjectState,
    PruneProjectResult,
    SchedulerInspection,
    StatusEntry,
    StatusKind,
    StatusProjectResult,
    UnknownSchedulerBackendError,
    ValidateProjectResult,
)
from xcron.capabilities.scheduler_native.ports import (
    DeploymentPlan,
    NullOutcomeRecorder,
    OutcomeRecorder,
    SchedulerBackend,
    SchedulerRuntimeOptions,
)

__all__ = [
    "ApplyProjectResult", "DeployedJobState", "DeploymentPlan", "InspectField",
    "InspectJobResult", "InspectSnippet", "NullOutcomeRecorder", "OutcomeRecorder",
    "PlanChange", "PlanChangeKind", "PlanProjectResult", "ProjectPlan", "ProjectState",
    "PruneProjectResult", "SchedulerBackend", "SchedulerInspection",
    "SchedulerRuntimeOptions", "StatusEntry", "StatusKind", "StatusProjectResult",
    "UnknownSchedulerBackendError", "ValidateProjectResult",
]
