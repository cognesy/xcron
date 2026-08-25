"""The CLI and SDK must invoke the same capability ports with the same intent."""

from __future__ import annotations

import textwrap
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from typer.testing import CliRunner

from xcron.sdk import JobCreateRequest, JobUpdateField, JobUpdateRequest, ScheduleRequest
from xcron_cli.typer_app import app
from xcron.kernel import CapabilityHost
from xcron.sdk.client import Xcron


BACKEND = "cron"

MANIFEST = textwrap.dedent(
    """\
    version: 1
    project:
      id: parity-demo
    defaults:
      working_dir: .
      shell: /bin/sh
    jobs:
      - id: ping_job
        schedule:
          cron: "*/5 * * * *"
        command: echo ping
    """
)


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Prepare deterministic, non-host scheduler inputs for both channels."""
    root = tmp_path / "project"
    (root / "resources" / "schedules").mkdir(parents=True)
    (root / "resources" / "schedules" / "default.yaml").write_text(MANIFEST, encoding="utf-8")
    monkeypatch.setenv("XCRON_MANAGE_CRONTAB", "0")
    monkeypatch.setenv("XCRON_MANAGE_LAUNCHCTL", "0")
    executable = tmp_path / "bin" / "xcron"
    executable.parent.mkdir()
    executable.write_text("", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(executable.parent))
    monkeypatch.chdir(root)
    return root


class RecorderPort:
    """Record public port calls while delegating to the real implementation."""

    def __init__(
        self,
        capability: str,
        target: object,
        events: list[tuple[str, str, tuple[Any, ...], dict[str, Any]]],
    ) -> None:
        self._capability = capability
        self._target = target
        self._events = events

    def __getattr__(self, name: str) -> object:
        member = getattr(self._target, name)
        if not callable(member):
            return member

        def recorded(*args: Any, **kwargs: Any) -> Any:
            self._events.append((self._capability, name, args, kwargs))
            return member(*args, **kwargs)

        return recorded


def _capture_port_calls(
    monkeypatch: pytest.MonkeyPatch,
    operation: Callable[[], Any],
) -> list[tuple[str, str, tuple[Any, ...], dict[str, Any]]]:
    events: list[tuple[str, str, tuple[Any, ...], dict[str, Any]]] = []
    original = CapabilityHost.require

    def require(
        host: CapabilityHost,
        capability: str,
        port: type,
        *,
        port_id: str | None = None,
    ) -> object:
        target = original(host, capability, port, port_id=port_id)
        return RecorderPort(capability, target, events)

    with monkeypatch.context() as scoped:
        scoped.setattr(CapabilityHost, "require", require)
        operation()
    return events


def _normalize(value: Any, replacements: Mapping[str, str]) -> Any:
    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(mode="python"), replacements)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return _normalize(str(value), replacements)
    if isinstance(value, str):
        normalized = value
        for source, replacement in replacements.items():
            normalized = normalized.replace(source, replacement)
        return normalized
    if isinstance(value, (int, float, bool, type(None))):
        return value
    if isinstance(value, Mapping):
        return {str(key): _normalize(item, replacements) for key, item in sorted(value.items())}
    if isinstance(value, frozenset):
        return tuple(sorted((_normalize(item, replacements) for item in value), key=repr))
    if isinstance(value, (list, tuple)):
        return tuple(_normalize(item, replacements) for item in value)
    return type(value).__name__


def _normalized_events(
    events: list[tuple[str, str, tuple[Any, ...], dict[str, Any]]],
    replacements: Mapping[str, str],
) -> tuple[Any, ...]:
    return tuple(
        (capability, method, _normalize(args, replacements), _normalize(kwargs, replacements))
        for capability, method, args, kwargs in events
    )


@dataclass(frozen=True)
class ParityCase:
    """One public operation projected by both channels."""

    label: str
    through_sdk: Callable[[Xcron], Any]
    argv: list[str]
    unscoped: bool = False


CASES: tuple[ParityCase, ...] = (
    ParityCase("validate", lambda client: client.schedules.validate(), ["validate"]),
    ParityCase("plan", lambda client: client.schedules.plan(), ["plan"]),
    ParityCase("status", lambda client: client.schedules.status(), ["status"]),
    ParityCase("apply", lambda client: client.schedules.apply(), ["apply"]),
    ParityCase("prune", lambda client: client.schedules.prune(), ["prune"]),
    ParityCase("inspect", lambda client: client.schedules.inspect("ping_job"), ["inspect", "ping_job"]),
    ParityCase("jobs list", lambda client: client.jobs.list(), ["jobs", "list"]),
    ParityCase("jobs show", lambda client: client.jobs.show("ping_job"), ["jobs", "show", "ping_job"]),
    ParityCase(
        "jobs add",
        lambda client: client.jobs.add(
            JobCreateRequest(job_id="cleanup_job", command="echo cleanup", schedule=ScheduleRequest.every("1h"))
        ),
        ["jobs", "add", "cleanup_job", "--command", "echo cleanup", "--every", "1h"],
    ),
    ParityCase(
        "jobs update",
        lambda client: client.jobs.update(
            "ping_job",
            JobUpdateRequest(
                command="echo refreshed",
                schedule=ScheduleRequest.cron("0 * * * *"),
                env={"MODE": "fast"},
                clear_fields=frozenset({JobUpdateField.DESCRIPTION}),
            ),
        ),
        [
            "jobs",
            "update",
            "ping_job",
            "--command",
            "echo refreshed",
            "--cron",
            "0 * * * *",
            "--env",
            "MODE=fast",
            "--clear-description",
        ],
    ),
    ParityCase("jobs enable", lambda client: client.jobs.enable("ping_job"), ["jobs", "enable", "ping_job"]),
    ParityCase("jobs disable", lambda client: client.jobs.disable("ping_job"), ["jobs", "disable", "ping_job"]),
    ParityCase("jobs remove", lambda client: client.jobs.remove("ping_job"), ["jobs", "remove", "ping_job"]),
    ParityCase("logs list", lambda client: client.operations.list_logs(), ["logs", "list"]),
    ParityCase("logs clear", lambda client: client.operations.clear_logs(), ["logs", "clear"]),
    ParityCase("logs clear --apply", lambda client: client.operations.clear_logs(dry_run=False), ["logs", "clear", "--apply"]),
    ParityCase("logs list --job", lambda client: client.operations.list_logs(job_filter="ping_job"), ["logs", "list", "--job", "ping_job"]),
    ParityCase("hooks install", lambda client: client.hooks.install(), ["hooks", "install"]),
    ParityCase("hooks status", lambda client: client.hooks.status(), ["hooks", "status"]),
    ParityCase("hooks repair", lambda client: client.hooks.repair(), ["hooks", "repair"]),
    ParityCase("hooks session end", lambda client: client.hooks.session_end(), ["hooks", "session-end"]),
    ParityCase("home initialize", lambda client: client.home.initialize(), ["init"], unscoped=True),
    ParityCase("metrics show", lambda client: client.operations.show_metrics(), ["metrics", "show"], unscoped=True),
    ParityCase("metrics reset", lambda client: client.operations.reset_metrics(), ["metrics", "reset"], unscoped=True),
)


@pytest.mark.parametrize("case", CASES, ids=[case.label for case in CASES])
def test_both_channels_reach_the_same_capability_port_with_the_same_request(
    case: ParityCase,
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk_project = project.parent / "sdk-project"
    cli_project = project.parent / "cli-project"
    for target in (sdk_project, cli_project):
        manifest = target / "resources" / "schedules" / "default.yaml"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(MANIFEST, encoding="utf-8")

    sdk_state = project.parent / "sdk-state"
    cli_state = project.parent / "cli-state"
    sdk_home = project.parent / "sdk-home"
    cli_home = project.parent / "cli-home"
    sdk_crontab = project.parent / "sdk-crontab"
    cli_crontab = project.parent / "cli-crontab"
    sdk_crontab.write_text("", encoding="utf-8")
    cli_crontab.write_text("", encoding="utf-8")

    monkeypatch.setenv("XCRON_PROJECT", str(sdk_project))
    monkeypatch.setenv("XCRON_STATE_ROOT", str(sdk_state))
    monkeypatch.setenv("XCRON_HOME", str(sdk_home))
    monkeypatch.setenv("XCRON_CRONTAB_PATH", str(sdk_crontab))

    def through_sdk() -> None:
        if case.unscoped:
            with Xcron.open_unscoped() as client:
                case.through_sdk(client)
        else:
            with Xcron.open(sdk_project, backend=BACKEND) as client:
                case.through_sdk(client)

    sdk_events = _capture_port_calls(monkeypatch, through_sdk)

    monkeypatch.setenv("XCRON_PROJECT", str(cli_project))
    monkeypatch.setenv("XCRON_STATE_ROOT", str(cli_state))
    monkeypatch.setenv("XCRON_HOME", str(cli_home))
    monkeypatch.setenv("XCRON_CRONTAB_PATH", str(cli_crontab))

    def through_cli() -> None:
        result = CliRunner().invoke(app, ["--project", str(cli_project), "--backend", BACKEND, *case.argv])
        assert result.exit_code == 0, result.output

    cli_events = _capture_port_calls(monkeypatch, through_cli)
    replacements = {
        str(sdk_project): "<project>",
        str(cli_project): "<project>",
        str(sdk_state): "<state>",
        str(cli_state): "<state>",
        str(sdk_home): "<home>",
        str(cli_home): "<home>",
        str(sdk_crontab): "<crontab>",
        str(cli_crontab): "<crontab>",
    }

    assert _normalized_events(cli_events, replacements) == _normalized_events(sdk_events, replacements)


def test_the_parity_check_can_fail() -> None:
    """A comparison that cannot come out unequal proves nothing."""
    assert _normalized_events([("metrics", "show", (), {})], {}) != _normalized_events(
        [("metrics", "reset", (), {})], {}
    )
