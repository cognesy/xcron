"""Conformance checks for the independent native scheduler control provider."""

from __future__ import annotations

import json
from pathlib import Path
import plistlib
import subprocess

import pytest

from xcron.capabilities.manifest_yaml.provider import CAPABILITY as MANIFEST
from xcron.capabilities.manifest_yaml.provider import YamlManifestProvider
from xcron.capabilities.scheduler_native.adapters import launchd
from xcron.capabilities.scheduler_native.ports import DeploymentPlan, SchedulerRuntimeOptions
from xcron.capabilities.scheduler_native.provider import CAPABILITY as SCHEDULER
from xcron.capabilities.scheduler_native.registry import SchedulerRegistry
from xcron.capabilities.scheduler_native.service import NativeScheduleController
from xcron.capabilities.workspace_local.provider import CAPABILITY as WORKSPACE
from xcron.capabilities.workspace_local.provider import LocalWorkspaceProvider
from xcron.contracts import (
    InvocationContext,
    JobLookupRequest,
    NormalizedJob,
    OutcomeSink,
    PlanChange,
    ProjectState,
    ProjectRequest,
    ProjectWorkspace,
    ScheduleControlPort,
    SchedulerRequest,
    SchedulerInspection,
    Settings,
    UnknownSchedulerBackendError,
    XcronOptions,
)
from xcron.kernel import CapabilityHost, CapabilityRegistry


MANIFEST_TEXT = """\
version: 1
project:
  id: native-provider
defaults:
  working_dir: .
  shell: /bin/sh
jobs:
  - id: archive
    command: echo archive
    schedule:
      cron: "0 * * * *"
"""


class BrokenSink:
    def record(self, counter: str, amount: int = 1) -> None:
        raise RuntimeError(f"unavailable metrics for {counter}:{amount}")


def _workspace(tmp_path: Path, manifest: str = MANIFEST_TEXT) -> ProjectWorkspace:
    schedules = tmp_path / "resources" / "schedules"
    schedules.mkdir(parents=True)
    (schedules / "default.yaml").write_text(manifest, encoding="utf-8")
    return ProjectWorkspace(
        tmp_path,
        schedules,
        tmp_path / "config.yaml",
        tmp_path / "marker.toml",
        None,
    )


def _context(
    workspace: ProjectWorkspace,
    *,
    backend: str,
    state_root: Path,
    crontab_path: Path | None = None,
    launch_agents_dir: Path | None = None,
    event_sink: OutcomeSink | None = None,
) -> InvocationContext:
    options = XcronOptions.create(
        workspace.root,
        backend=backend,
        state_root=state_root,
        crontab_path=crontab_path,
        launch_agents_dir=launch_agents_dir,
        launchctl_domain="gui/test",
        manage_launchctl=False,
    )
    return InvocationContext(
        options=options,
        workspace=workspace,
        settings=Settings(
            state_root=state_root,
            crontab_path=crontab_path,
            launch_agents_dir=launch_agents_dir,
            launchctl_domain="gui/test",
            manage_launchctl=False,
        ),
        event_sink=event_sink or BrokenSink(),
    )


def test_provider_reconciles_every_cron_flow_without_a_metrics_provider(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    state_root = tmp_path / "state"
    crontab_path = tmp_path / "crontab"
    crontab_path.write_text("# externally owned entry\n", encoding="utf-8")
    context = _context(
        workspace,
        backend="cron",
        state_root=state_root,
        crontab_path=crontab_path,
    )
    host = CapabilityHost(CapabilityRegistry((WORKSPACE, MANIFEST, SCHEDULER)))
    scheduler = host.require("scheduler", ScheduleControlPort)
    request = SchedulerRequest(backend="cron", state_root=state_root, crontab_path=crontab_path)

    validation = scheduler.validate(ProjectRequest(), context)
    planned = scheduler.plan(request, context)
    applied = scheduler.apply(request, context)
    status = scheduler.status(request, context)

    assert validation.valid is True
    assert planned.changes[0].kind.value == "create"
    assert applied.valid is True
    assert status.valid is True
    assert status.statuses[0].kind.value == "ok"
    assert "# BEGIN XCRON project=native-provider backend=cron" in crontab_path.read_text(encoding="utf-8")
    wrapper = state_root / "projects" / "native-provider" / "wrappers" / "native-provider.archive.sh"
    state = state_root / "projects" / "native-provider" / "project-state.json"
    assert wrapper.exists()
    assert state.exists()
    wrapper_text = wrapper.read_text(encoding="utf-8")
    for line in wrapper_text.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("xcron "), line
        assert "import xcron" not in stripped, line

    ran = subprocess.run(
        ["/bin/sh", str(wrapper)],
        env={
            "HOME": str(tmp_path / "no-xcron-home"),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONPATH": "",
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert ran.returncode == 0, ran.stderr
    assert "archive" in (state.parent / "logs" / "native-provider.archive.out.log").read_text(
        encoding="utf-8"
    )

    payload_text = state.read_text(encoding="utf-8")
    payload = json.loads(payload_text)
    assert set(payload) == {"project_id", "backend", "manifest_hash", "updated_at", "jobs"}
    assert set(payload["jobs"][0]) == {
        "qualified_id", "job_id", "artifact_id", "backend", "enabled", "desired_hash",
        "definition_hash", "observed_hash", "label", "artifact_path", "wrapper_path",
        "stdout_log_path", "stderr_log_path", "event_log_path", "last_applied_at",
    }
    assert payload_text == json.dumps(payload, indent=2, sort_keys=True)

    inspected = scheduler.inspect(JobLookupRequest(job_identifier="archive"), context)
    assert inspected.valid is True
    assert inspected.inspection is not None
    assert inspected.inspection.raw_entry is not None

    pruned = scheduler.prune(request, context)
    assert pruned.valid is True
    assert not wrapper.exists()
    assert not state.exists()
    assert crontab_path.read_text(encoding="utf-8") == "# externally owned entry\n"
    assert host.freeze().ids() == ("manifest:yaml", "workspace:local", "scheduler:native")


class FakeScheduler:
    """A package-local scheduler adapter that never reaches the host scheduler."""

    name = "fake"

    def __init__(self) -> None:
        self.applied: list[DeploymentPlan] = []
        self.pruned: list[str] = []

    def collect_project_state(
        self, project_id: str, *, options: SchedulerRuntimeOptions
    ) -> ProjectState:
        return ProjectState(project_id=project_id, backend=self.name, manifest_hash=None)

    def inspect_project(
        self,
        project_id: str,
        *,
        options: SchedulerRuntimeOptions,
        include_native_detail: bool = False,
    ) -> tuple[SchedulerInspection, ...]:
        return ()

    def apply(self, deployment: DeploymentPlan, *, options: SchedulerRuntimeOptions) -> ProjectState:
        self.applied.append(deployment)
        return ProjectState(
            project_id=deployment.plan.manifest.project_id,
            backend=self.name,
            manifest_hash=deployment.manifest_hash,
        )

    def prune_project(
        self, project_id: str, *, options: SchedulerRuntimeOptions
    ) -> tuple[SchedulerInspection, ...]:
        self.pruned.append(project_id)
        return ()

    def schedule_errors(self, jobs: tuple[NormalizedJob, ...]) -> tuple[PlanChange, ...]:
        return ()


def test_provider_accepts_a_fake_backend_through_its_scheduler_port(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    fake = FakeScheduler()
    controller = NativeScheduleController(
        LocalWorkspaceProvider(),
        YamlManifestProvider(),
        scheduler_registry=SchedulerRegistry((fake,)),
    )
    assert isinstance(controller, ScheduleControlPort)
    context = _context(workspace, backend="fake", state_root=tmp_path / "state")
    request = SchedulerRequest(backend="fake", state_root=tmp_path / "state")

    planned = controller.plan(request, context)
    status = controller.status(request, context)
    applied = controller.apply(request, context)
    pruned = controller.prune(request, context)

    assert [change.kind.value for change in planned.changes] == ["create"]
    assert [entry.kind.value for entry in status.statuses] == ["missing"]
    assert applied.valid is True
    assert len(fake.applied) == 1
    assert fake.applied[0].plan.manifest.project_id == "native-provider"
    assert fake.pruned == ["native-provider"]
    assert pruned.valid is True

    with pytest.raises(UnknownSchedulerBackendError):
        controller.status(SchedulerRequest(backend="absent"), context)


def test_provider_reconciles_launchd_artifacts_without_touching_host_launchctl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    state_root = tmp_path / "state"
    agents_dir = tmp_path / "LaunchAgents"

    def fake_launchctl(command, *, check, **kwargs):
        return subprocess.CompletedProcess(command, 1 if command[1] == "print" else 0, "", "")

    monkeypatch.setattr(launchd, "run_logged_subprocess", fake_launchctl)
    context = _context(
        workspace,
        backend="launchd",
        state_root=state_root,
        launch_agents_dir=agents_dir,
    )
    host = CapabilityHost(CapabilityRegistry((WORKSPACE, MANIFEST, SCHEDULER)))
    scheduler = host.require("scheduler", ScheduleControlPort)
    request = SchedulerRequest(
        backend="launchd",
        state_root=state_root,
        launch_agents_dir=agents_dir,
        launchctl_domain="gui/test",
        manage_launchctl=False,
    )

    applied = scheduler.apply(request, context)
    status = scheduler.status(request, context)
    inspected = scheduler.inspect(JobLookupRequest(job_identifier="native-provider.archive"), context)
    plist_path = agents_dir / "com.xcron.native-provider.archive.plist"

    assert applied.valid is True
    assert status.statuses[0].kind.value == "ok"
    assert inspected.valid is True
    assert plist_path.exists()
    plist_payload = plistlib.loads(plist_path.read_bytes())
    assert plist_payload["Label"] == "com.xcron.native-provider.archive"
    assert plist_payload["EnvironmentVariables"]["XCRON_QUALIFIED_ID"] == "native-provider.archive"
    assert plist_payload["ProgramArguments"] == [
        str(state_root / "projects" / "native-provider" / "wrappers" / "native-provider.archive.sh")
    ]

    pruned = scheduler.prune(request, context)
    assert pruned.valid is True
    assert not plist_path.exists()


def test_launchd_inspection_degrades_when_launchctl_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_launchctl(*_arguments, **_kwargs):
        raise FileNotFoundError("launchctl")

    monkeypatch.setattr(launchd, "run_logged_subprocess", missing_launchctl)

    assert launchd.read_disabled_labels("gui/test") == set()
    assert launchd.read_launchd_service_status("com.xcron.demo.job", "gui/test", include_output=True) == (
        False,
        None,
    )
