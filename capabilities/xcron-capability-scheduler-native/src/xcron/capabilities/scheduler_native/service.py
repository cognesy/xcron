"""Contract-port implementation of the complete native scheduler control flow."""

from __future__ import annotations

from pathlib import Path
import plistlib

from xcron.capabilities.scheduler_native.domain import build_project_plan, build_status_entries
from xcron.capabilities.scheduler_native.layout import RuntimeLayout
from xcron.capabilities.scheduler_native.ports import DeploymentPlan, SchedulerRuntimeOptions
from xcron.capabilities.scheduler_native.registry import SchedulerRegistry, default_backend_for_current_platform, default_scheduler_registry
from xcron.capabilities.scheduler_native.state_store import delete_project_state, load_project_state, resolve_project_state_path
from xcron.contracts import (
    ApplyProjectResult,
    InspectField,
    InspectJobResult,
    InspectSnippet,
    InvocationContext,
    JobLookupRequest,
    ManifestPort,
    PlanChange,
    PlanChangeKind,
    PlanProjectResult,
    ProjectRequest,
    PruneProjectResult,
    ScheduleControlPort,
    SchedulerInspection,
    SchedulerRequest,
    StatusEntry,
    StatusProjectResult,
    ValidateProjectResult,
    ValidationMessage,
    WorkspacePort,
)


class NativeScheduleController:
    """Own reconciliation while obtaining all foreign decisions through ports."""

    def __init__(
        self,
        workspace: WorkspacePort,
        manifest: ManifestPort,
        *,
        scheduler_registry: SchedulerRegistry | None = None,
    ) -> None:
        self._manifest = manifest
        self._layout = RuntimeLayout(workspace)
        self._registry = scheduler_registry or default_scheduler_registry(self._layout)

    def validate(self, request: ProjectRequest, context: InvocationContext) -> ValidateProjectResult:
        """Load, validate, normalize, and hash the selected desired state."""
        try:
            document = self._manifest.load(request, context)
            report = self._manifest.validate(document, context)
        except Exception as error:
            root = _project_root(request, context)
            return ValidateProjectResult(
                project_root=str(root),
                manifest_path=None,
                valid=False,
                errors=(ValidationMessage(level="error", path="/", message=str(error)),),
            )
        if not report.valid or report.normalized_manifest is None:
            return ValidateProjectResult(
                project_root=str(document.project_root),
                manifest_path=str(document.manifest_path),
                valid=False,
                errors=report.errors,
                warnings=report.warnings,
            )
        normalized = report.normalized_manifest
        return ValidateProjectResult(
            project_root=str(document.project_root),
            manifest_path=str(document.manifest_path),
            valid=True,
            warnings=report.warnings,
            normalized_manifest=normalized,
            hashes=self._manifest.hashes(normalized),
        )

    def plan(self, request: SchedulerRequest, context: InvocationContext) -> PlanProjectResult:
        validation = self.validate(request, context)
        if not validation.valid or validation.normalized_manifest is None or validation.hashes is None:
            return PlanProjectResult(valid=False, validation=validation, backend=None, state_path=None)
        backend = self._backend(request, context)
        options = self._options(request, context)
        state = load_project_state(
            validation.normalized_manifest.project_id,
            backend,
            layout=self._layout,
            state_root=options.state_root,
        )
        plan = build_project_plan(
            validation.normalized_manifest,
            backend,
            validation.hashes.manifest_hash,
            dict(validation.hashes.job_hashes),
            dict(validation.hashes.job_definition_hashes),
            state,
        )
        schedule_errors = self._registry.require(backend).schedule_errors(validation.normalized_manifest.jobs)
        if schedule_errors:
            plan = type(plan)(plan.backend, plan.manifest, plan.changes + schedule_errors, plan.state)
        return PlanProjectResult(
            valid=True,
            validation=validation,
            backend=backend,
            state_path=str(resolve_project_state_path(validation.normalized_manifest.project_id, layout=self._layout, state_root=options.state_root)),
            changes=plan.changes,
            plan=plan,
        )

    def status(self, request: SchedulerRequest, context: InvocationContext) -> StatusProjectResult:
        _record(context, "status.calls")
        validation = self.validate(request, context)
        if not validation.valid or validation.normalized_manifest is None or validation.hashes is None:
            _record(context, "status.failed")
            return StatusProjectResult(valid=False, backend=None, validation=validation)
        backend = self._backend(request, context)
        options = self._options(request, context)
        scheduler = self._registry.require(backend)
        actual_state = scheduler.collect_project_state(validation.normalized_manifest.project_id, options=options)
        inspections = scheduler.inspect_project(validation.normalized_manifest.project_id, options=options)
        plan = build_project_plan(
            validation.normalized_manifest,
            backend,
            validation.hashes.manifest_hash,
            dict(validation.hashes.job_hashes),
            dict(validation.hashes.job_definition_hashes),
            actual_state,
        )
        _record(context, "status.succeeded")
        return StatusProjectResult(
            valid=True,
            backend=backend,
            validation=validation,
            plan=plan,
            statuses=build_status_entries(plan),
            inspections=tuple(inspections),
        )

    def apply(self, request: SchedulerRequest, context: InvocationContext) -> ApplyProjectResult:
        _record(context, "apply.calls")
        status = self.status(request, context)
        if not status.valid or status.backend is None or status.plan is None:
            _record(context, "apply.failed")
            return ApplyProjectResult(
                valid=False,
                backend=None,
                plan_result=PlanProjectResult(False, status.validation, None, None),
            )
        options = self._options(request, context)
        validation = status.validation
        if validation.normalized_manifest is None or validation.hashes is None:
            raise RuntimeError("valid native status unexpectedly lacks deployment data")
        plan_result = PlanProjectResult(
            valid=True,
            validation=validation,
            backend=status.backend,
            state_path=str(resolve_project_state_path(validation.normalized_manifest.project_id, layout=self._layout, state_root=options.state_root)),
            changes=status.plan.changes,
            plan=status.plan,
        )
        scheduler = self._registry.require(status.backend)
        if scheduler.schedule_errors(status.plan.manifest.jobs):
            _record(context, "apply.failed")
            return ApplyProjectResult(False, status.backend, plan_result)
        deployment = DeploymentPlan(
            backend=status.backend,
            plan=status.plan,
            state_path=plan_result.state_path or "",
            manifest_hash=validation.hashes.manifest_hash,
            job_hashes=validation.hashes.job_hashes,
            job_definition_hashes=validation.hashes.job_definition_hashes,
        )
        applied_state = scheduler.apply(deployment, options=options)
        _record(context, "apply.succeeded")
        _record(context, "jobs.applied", len(applied_state.jobs))
        return ApplyProjectResult(True, status.backend, plan_result, applied_state)

    def prune(self, request: SchedulerRequest, context: InvocationContext) -> PruneProjectResult:
        validation = self.validate(request, context)
        if not validation.valid or validation.normalized_manifest is None:
            return PruneProjectResult(False, None, None, error="project validation failed")
        backend = self._backend(request, context)
        options = self._options(request, context)
        project_id = validation.normalized_manifest.project_id
        removed = self._registry.require(backend).prune_project(project_id, options=options)
        delete_project_state(project_id, layout=self._layout, state_root=options.state_root)
        return PruneProjectResult(True, backend, project_id, tuple(removed))

    def inspect(self, request: JobLookupRequest, context: InvocationContext) -> InspectJobResult:
        scheduler_request = SchedulerRequest(
            project_path=request.project_path,
            schedule_name=request.schedule_name,
            backend=context.options.backend,
            state_root=context.options.state_root,
            platform=context.options.platform,
            launch_agents_dir=context.options.launch_agents_dir,
            launchctl_domain=context.options.launchctl_domain,
            crontab_path=context.options.crontab_path,
            manage_launchctl=context.options.manage_launchctl,
            manage_crontab=context.options.manage_crontab,
        )
        status = self.status(scheduler_request, context)
        if not status.valid or status.plan is None or status.backend is None:
            return InspectJobResult(False, None, status, error="project validation failed")
        desired = next((job for job in status.plan.manifest.jobs if job.job_id == request.job_identifier or job.qualified_id == request.job_identifier), None)
        target = desired.qualified_id if desired is not None else request.job_identifier
        entry = next((item for item in status.statuses if item.qualified_id == target), None)
        inspections = self._registry.require(status.backend).inspect_project(
            status.validation.normalized_manifest.project_id,
            options=self._options(scheduler_request, context),
            include_native_detail=True,
        )
        inspection = next((item for item in inspections if item.qualified_id in (request.job_identifier, target)), None)
        if desired is None and inspection is None:
            return InspectJobResult(False, status.backend, status, error=f"job not found in desired manifest or deployed backend: {request.job_identifier}")
        return InspectJobResult(
            True,
            status.backend,
            status,
            desired_job=desired,
            status_entry=entry,
            desired_fields=_desired_fields(desired, entry),
            deployed_fields=_deployed_fields(inspection),
            snippets=_snippets(inspection),
            inspection=inspection,
        )

    def _backend(self, request: SchedulerRequest, context: InvocationContext) -> str:
        return request.backend or context.options.backend or default_backend_for_current_platform(request.platform or context.options.platform)

    def _options(self, request: SchedulerRequest, context: InvocationContext) -> SchedulerRuntimeOptions:
        options = context.options
        settings = context.settings
        return SchedulerRuntimeOptions.create(
            state_root=request.state_root or options.state_root or settings.state_root,
            launch_agents_dir=request.launch_agents_dir or options.launch_agents_dir or settings.launch_agents_dir,
            launchctl_domain=request.launchctl_domain or options.launchctl_domain or settings.launchctl_domain,
            crontab_path=request.crontab_path or options.crontab_path or settings.crontab_path,
            manage_launchctl=request.manage_launchctl and options.manage_launchctl and settings.manage_launchctl,
            manage_crontab=request.manage_crontab and options.manage_crontab and settings.manage_crontab,
            layout=self._layout,
        )


def _record(context: InvocationContext, counter: str, amount: int = 1) -> None:
    try:
        context.event_sink.record(counter, amount)
    except Exception:
        return None


def _project_root(request: ProjectRequest, context: InvocationContext) -> Path:
    if context.workspace is not None:
        return context.workspace.root
    return (request.project_path or context.options.project_path or Path.cwd()).expanduser().resolve()


def _desired_fields(job, entry: StatusEntry | None) -> tuple[InspectField, ...]:
    if job is None:
        return ()
    fields = [
        InspectField("qualified_id", job.qualified_id), InspectField("job_id", job.job_id),
        InspectField("status", entry.kind.value if entry else "unknown"),
        InspectField("schedule", f"{job.schedule.kind.value}={job.schedule.value}"),
        InspectField("enabled", str(job.enabled)), InspectField("command", job.execution.command),
        InspectField("working_dir", job.execution.working_dir), InspectField("shell", job.execution.shell),
        InspectField("overlap", job.execution.overlap.value),
    ]
    if job.description:
        fields.append(InspectField("description", job.description))
    if job.execution.timezone is not None:
        fields.append(InspectField("timezone", job.execution.timezone))
    if job.execution.env:
        fields.append(InspectField("env", ", ".join(f"{key}={value}" for key, value in job.execution.env)))
    return tuple(fields)


def _deployed_fields(inspection: SchedulerInspection | None) -> tuple[InspectField, ...]:
    if inspection is None:
        return ()
    fields = [
        InspectField("qualified_id", inspection.qualified_id), InspectField("backend_enabled", str(inspection.enabled)),
        InspectField("desired_hash", str(inspection.desired_hash or "n/a")),
    ]
    for name, value in (("definition_hash", inspection.definition_hash), ("label", inspection.label), ("artifact_path", inspection.artifact_path), ("wrapper_path", inspection.wrapper_path), ("stdout_log", inspection.stdout_log_path), ("stderr_log", inspection.stderr_log_path), ("event_log", inspection.event_log_path), ("loaded", inspection.loaded)):
        if value is not None:
            fields.append(InspectField(name, str(value)))
    return tuple(fields)


def _snippets(inspection: SchedulerInspection | None) -> tuple[InspectSnippet, ...]:
    if inspection is None:
        return ()
    snippets: list[InspectSnippet] = []
    if inspection.raw_entry is not None:
        snippets.append(InspectSnippet("raw_entry", inspection.raw_entry))
    if inspection.raw_plist is not None:
        snippets.append(InspectSnippet("raw_plist", plistlib.dumps(dict(inspection.raw_plist), fmt=plistlib.FMT_XML, sort_keys=True).decode("utf-8")))
    if inspection.launchctl_print:
        snippets.append(InspectSnippet("launchctl_print", inspection.launchctl_print))
    return tuple(snippets)


assert isinstance(NativeScheduleController.__new__(NativeScheduleController), ScheduleControlPort)
