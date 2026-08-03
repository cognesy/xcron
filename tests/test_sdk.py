"""Public SDK lifecycle and channel-boundary coverage."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

import pytest

from xcron_libs import ClientClosedError, HookError, Xcron
from xcron_libs.capabilities.agent_hooks.contracts import ExecutableNotFoundError
from xcron_libs.capabilities.reconciliation import SchedulerRegistry
from xcron_libs.domain import PlanChange, PlanChangeKind, ProjectState


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


def test_sdk_accepts_an_explicit_scheduler_registry(tmp_path: Path) -> None:
    project = _write_project(tmp_path / "project")

    class TestScheduler:
        name = "test"

        def schedule_errors(self, jobs):
            return tuple()

    registry = SchedulerRegistry((TestScheduler(),))
    with Xcron.open(project, backend="test", scheduler_registry=registry) as client:
        result = client.schedules.plan()

    assert result.valid is True
    assert result.backend == "test"


def test_apply_preserves_injected_backend_name_for_schedule_errors(tmp_path: Path) -> None:
    project = _write_project(tmp_path / "project")

    class ConstrainedScheduler:
        name = "constrained"

        def collect_project_state(self, project_id, *, options):
            return ProjectState(
                project_id=project_id,
                backend=self.name,
                manifest_hash=None,
            )

        def inspect_project(self, project_id, *, options, include_native_detail=False):
            return tuple()

        def schedule_errors(self, jobs):
            job = jobs[0]
            return (
                PlanChange(
                    kind=PlanChangeKind.ERROR,
                    qualified_id=job.qualified_id,
                    reason="schedule is unsupported by constrained backend",
                    desired_job=job,
                ),
            )

        def apply(self, deployment, *, options):
            raise AssertionError("apply must not run when schedule validation fails")

    registry = SchedulerRegistry((ConstrainedScheduler(),))
    with Xcron.open(
        project,
        backend="constrained",
        scheduler_registry=registry,
    ) as client:
        result = client.schedules.apply()

    assert result.valid is False
    assert result.backend == "constrained"
    assert result.plan_result.backend == "constrained"


def test_sdk_modules_do_not_import_cli_or_renderers() -> None:
    sdk_dir = Path(__file__).resolve().parents[1] / "libs" / "sdk"
    forbidden = (
        "xcron_cli",
        "typer",
        "rich",
        "xcron_libs.services.cli_contracts",
        "xcron_libs.services.cli_mappers",
        "xcron_libs.services.cli_responses",
        "xcron_libs.services.toon_renderer",
        "xcron_libs.services.tmux_renderer",
    )

    for path in sdk_dir.glob("*.py"):
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


def test_sdk_translates_agent_hooks_failures(monkeypatch, tmp_path: Path) -> None:
    import importlib

    hooks_module = importlib.import_module("xcron_libs.sdk.hooks")

    def fail(*_args, **_kwargs):
        raise ExecutableNotFoundError("missing xcron")

    monkeypatch.setattr(hooks_module, "status_agent_hooks", fail)
    with Xcron.open(tmp_path) as client:
        with pytest.raises(HookError, match="missing xcron"):
            client.hooks.status()


def test_importing_public_sdk_does_not_load_cli_or_response_modules() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import xcron_libs; "
                "forbidden = {'typer', 'xcron_cli', "
                "'xcron_libs.services.cli_responses'}; "
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
    sdk_dir = Path(__file__).resolve().parents[1] / "libs" / "sdk"

    for path in sdk_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue
                assert node.returns is not None, f"{path}:{node.lineno} {node.name}"
