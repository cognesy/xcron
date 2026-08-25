"""Public SDK lifecycle and channel-boundary coverage."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

import pytest

from xcron.sdk import (
    ClientClosedError,
    HookError,
    JobCreateRequest,
    JobUpdateField,
    JobUpdateRequest,
    ScheduleRequest,
    Xcron,
)
from xcron.capabilities.agent_hooks_local.provider import CAPABILITY as AGENT_HOOKS
from xcron.capabilities.jobs_manifest.provider import CAPABILITY as JOBS
from xcron.capabilities.logs_local.provider import CAPABILITY as LOGS
from xcron.capabilities.manifest_yaml.provider import CAPABILITY as MANIFEST
from xcron.capabilities.metrics_local.provider import CAPABILITY as METRICS
from xcron.capabilities.observability_structlog.provider import CAPABILITY as OBSERVABILITY
from xcron.capabilities.scheduler_native.provider import CAPABILITY as SCHEDULER
from xcron.capabilities.settings_xcfg.provider import CAPABILITY as SETTINGS
from xcron.capabilities.workspace_local.provider import CAPABILITY as WORKSPACE
from xcron.contracts import (
    AgentHooksError,
    ApplyProjectResult,
    HookInstallResult,
    HookRequest,
    HookStatusResult,
    InspectJobResult,
    JobLookupRequest,
    PlanChange,
    PlanChangeKind,
    PlanProjectResult,
    ProjectRequest,
    PruneProjectResult,
    ScheduleControlPort,
    StatusProjectResult,
    ValidateProjectResult,
)
from xcron.kernel import Capability, CapabilityDescriptor, CapabilityProvides, CapabilityRegistration, CapabilityRequirement, CapabilityRegistry, CapabilitySelection


SDK_DIR = Path(__file__).resolve().parents[1] / "packages" / "xcron-sdk" / "src" / "xcron" / "sdk"


def _registry(*extra: Capability) -> CapabilityRegistry:
    return CapabilityRegistry(
        (
            WORKSPACE,
            SETTINGS,
            OBSERVABILITY,
            MANIFEST,
            SCHEDULER,
            JOBS,
            LOGS,
            METRICS,
            AGENT_HOOKS,
            *extra,
        )
    )


def _write_project(root: Path) -> Path:
    schedules = root / "resources" / "schedules"
    schedules.mkdir(parents=True)
    (schedules / "default.yaml").write_text(
        """\
version: 1
project:
  id: sdk-demo
defaults:
  working_dir: .
  shell: /bin/sh
jobs:
  - id: hello
    schedule:
      cron: "*/5 * * * *"
    command: echo hello
""",
        encoding="utf-8",
    )
    return root


def test_sdk_exposes_grouped_typed_apis_and_lifecycle(tmp_path: Path) -> None:
    project = _write_project(tmp_path / "project")

    with Xcron.open(project, backend="cron", platform="linux") as client:
        plan = client.schedules.plan()
        jobs = client.jobs.list()

        assert plan.valid is True
        assert plan.backend == "cron"
        assert jobs.valid is True
        assert [job.job_id for job in jobs.jobs] == ["hello"]
        assert client.options.project_path == project.resolve()

    with pytest.raises(ClientClosedError, match="xcron client is closed"):
        client.schedules.plan()

    client.close()


def test_sdk_selects_an_explicit_alternate_schedule_provider(tmp_path: Path) -> None:
    project = _write_project(tmp_path / "project")

    class TestScheduleController:
        def validate(self, request: ProjectRequest, context) -> ValidateProjectResult:
            return ValidateProjectResult(str(context.workspace.root), None, True)

        def plan(self, request, context) -> PlanProjectResult:
            validation = self.validate(request, context)
            return PlanProjectResult(True, validation, "test", None)

        def status(self, request, context) -> StatusProjectResult:
            validation = self.validate(request, context)
            return StatusProjectResult(True, "test", validation)

        def apply(self, request, context) -> ApplyProjectResult:
            plan = self.plan(request, context)
            return ApplyProjectResult(True, "test", plan)

        def prune(self, request, context) -> PruneProjectResult:
            return PruneProjectResult(True, "test", "sdk-demo")

        def inspect(self, request: JobLookupRequest, context) -> InspectJobResult:
            status = self.status(request, context)
            return InspectJobResult(True, "test", status)

    assert isinstance(TestScheduleController(), ScheduleControlPort)
    alternate = Capability(
        CapabilityDescriptor(
            capability="scheduler",
            implementation="test",
            version="0.1.0",
            kernel_api=">=1,<2",
            requires=(CapabilityRequirement("workspace"), CapabilityRequirement("manifest")),
            provides=CapabilityProvides(ports=("scheduler",)),
        ),
        lambda _host: CapabilityRegistration(ports={"scheduler": TestScheduleController()}),
    )

    with Xcron.open(
        project,
        backend="test",
        capability_registry=_registry(alternate),
        selection=CapabilitySelection(scheduler="test"),
    ) as client:
        result = client.schedules.plan()

    assert result.valid is True
    assert result.backend == "test"


def test_sdk_job_mutations_accept_typed_requests(tmp_path: Path) -> None:
    project = _write_project(tmp_path / "project")

    with Xcron.open(project, backend="cron", platform="linux") as client:
        added = client.jobs.add(
            JobCreateRequest(
                job_id="cleanup",
                command="echo cleanup",
                schedule=ScheduleRequest.every("1h"),
                description="Clean temporary files",
                env={"MODE": "safe"},
            )
        )
        updated = client.jobs.update(
            "hello",
            JobUpdateRequest(
                command="echo refreshed",
                schedule=ScheduleRequest.cron("0 * * * *"),
                env={"MODE": "fast"},
                clear_fields=frozenset({JobUpdateField.DESCRIPTION}),
            ),
        )

    assert added.valid is True
    assert added.job is not None
    assert added.job.job_id == "cleanup"
    assert updated.valid is True
    assert updated.job is not None
    assert updated.job.job_id == "hello"


def test_sdk_job_update_requests_reject_empty_or_ambiguous_mutations() -> None:
    with pytest.raises(ValueError, match="at least one update field"):
        JobUpdateRequest()

    with pytest.raises(ValueError, match="cannot update and clear the same fields"):
        JobUpdateRequest(
            description="updated",
            clear_fields=frozenset({JobUpdateField.DESCRIPTION}),
        )


def test_apply_preserves_selected_backend_name_for_schedule_errors(tmp_path: Path) -> None:
    project = _write_project(tmp_path / "project")

    class ConstrainedScheduleController:
        def validate(self, request: ProjectRequest, context) -> ValidateProjectResult:
            return ValidateProjectResult(str(context.workspace.root), None, True)

        def plan(self, request, context) -> PlanProjectResult:
            validation = self.validate(request, context)
            return PlanProjectResult(
                True,
                validation,
                "constrained",
                None,
                changes=(
                PlanChange(
                    kind=PlanChangeKind.ERROR,
                    qualified_id="sdk-demo.hello",
                    reason="schedule is unsupported by constrained backend",
                ),
            )
            )

        def status(self, request, context) -> StatusProjectResult:
            validation = self.validate(request, context)
            return StatusProjectResult(True, "constrained", validation)

        def apply(self, request, context) -> ApplyProjectResult:
            return ApplyProjectResult(False, "constrained", self.plan(request, context))

        def prune(self, request, context) -> PruneProjectResult:
            return PruneProjectResult(True, "constrained", "sdk-demo")

        def inspect(self, request: JobLookupRequest, context) -> InspectJobResult:
            return InspectJobResult(True, "constrained", self.status(request, context))

    assert isinstance(ConstrainedScheduleController(), ScheduleControlPort)
    alternate = Capability(
        CapabilityDescriptor(
            capability="scheduler",
            implementation="constrained",
            version="0.1.0",
            kernel_api=">=1,<2",
            requires=(CapabilityRequirement("workspace"), CapabilityRequirement("manifest")),
            provides=CapabilityProvides(ports=("scheduler",)),
        ),
        lambda _host: CapabilityRegistration(ports={"scheduler": ConstrainedScheduleController()}),
    )

    with Xcron.open(
        project,
        backend="constrained",
        capability_registry=_registry(alternate),
        selection=CapabilitySelection(scheduler="constrained"),
    ) as client:
        result = client.schedules.apply()

    assert result.valid is False
    assert result.backend == "constrained"
    assert result.plan_result.backend == "constrained"


def test_sdk_modules_do_not_import_cli_or_renderers() -> None:
    forbidden = (
        "xcron_cli",
        "typer",
        "rich",
    )

    assert SDK_DIR.is_dir()
    for path in SDK_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        imports.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not any(name.startswith(forbidden) for name in imports), path


def test_sdk_translates_agent_hooks_failures(tmp_path: Path) -> None:
    class FailingAgentHooks:
        def install(self, request: HookRequest, context) -> HookInstallResult:
            raise AgentHooksError("missing xcron")

        def status(self, request: HookRequest, context) -> HookStatusResult:
            raise AgentHooksError("missing xcron")

        def repair(self, request: HookRequest, context) -> HookInstallResult:
            raise AgentHooksError("missing xcron")

        def record_session_end(self, request: ProjectRequest, context):
            raise AgentHooksError("missing xcron")

    alternate = Capability(
        CapabilityDescriptor(
            capability="agent-hooks",
            implementation="failing",
            version="0.1.0",
            kernel_api=">=1,<2",
            provides=CapabilityProvides(ports=("agent-hooks",)),
        ),
        lambda _host: CapabilityRegistration(ports={"agent-hooks": FailingAgentHooks()}),
    )

    with Xcron.open(
        tmp_path,
        capability_registry=_registry(alternate),
        selection=CapabilitySelection(**{"agent-hooks": "failing"}),
    ) as client:
        with pytest.raises(HookError, match="missing xcron"):
            client.hooks.status()


def test_importing_public_sdk_does_not_load_cli_or_response_modules() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import xcron; "
                "forbidden = {'typer', 'xcron_cli', "
                "'xcron_cli.responses'}; "
                "loaded = forbidden.intersection(sys.modules); "
                "assert not loaded, sorted(loaded)"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_public_sdk_methods_have_explicit_return_types() -> None:
    assert SDK_DIR.is_dir()
    for path in SDK_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue
                assert node.returns is not None, f"{path}:{node.lineno} {node.name}"
