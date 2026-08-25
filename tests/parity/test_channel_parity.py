"""The CLI and the SDK must reach the same use case with the same inputs.

A channel is supposed to be a projection: it decides how a result is rendered,
never what was asked for. The way that promise breaks is quiet — a flag whose
CLI default is the opposite of the SDK's, an option the CLI forgets to pass —
and every test that checks one channel at a time passes right through it.

So the check is comparative. A spy wraps the use case at the seam the SDK calls
it through, the same operation runs once per channel, and the two recorded
calls must be equal. The spy delegates to the real function, so both channels
run for real — `apply` and `prune` included, against a file crontab in a
temporary directory with `launchctl` disabled.

Equality is on a normalized view: composed collaborators (the scheduler
registry, the outcome recorder) are compared by type, because each channel
builds its own and identity would differ for uninteresting reasons. Everything
a caller can actually state — paths, names, backends, filters, flags — is
compared by value.
"""

from __future__ import annotations

import importlib
import textwrap
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import pytest
from pydantic import BaseModel
from typer.testing import CliRunner

from xcron import JobCreateRequest, JobUpdateField, JobUpdateRequest, ScheduleRequest
from xcron.channels.cli.typer_app import app
from xcron.sdk.client import Xcron

#: The one backend that reconciles against a plain file, so a parity check can
#: cover `apply` and `prune` without touching the host.
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
    """A real project, reconciled against a file crontab instead of the host."""
    root = tmp_path / "project"
    (root / "resources" / "schedules").mkdir(parents=True)
    (root / "resources" / "schedules" / "default.yaml").write_text(MANIFEST, encoding="utf-8")

    monkeypatch.setenv("XCRON_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("XCRON_CRONTAB_PATH", str(tmp_path / "crontab"))
    monkeypatch.setenv("XCRON_MANAGE_CRONTAB", "0")
    monkeypatch.setenv("XCRON_MANAGE_LAUNCHCTL", "0")
    monkeypatch.setenv("XCRON_HOME", str(tmp_path / "xcron-home"))
    executable = tmp_path / "bin" / "xcron"
    executable.parent.mkdir()
    executable.write_text("", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(executable.parent))
    monkeypatch.chdir(root)
    return root


class Recorder:
    """Records the call and then makes it, so the channel gets a real result."""

    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        return self._wrapped(*args, **kwargs)

    @property
    def only_call(self) -> tuple[tuple[Any, ...], dict[str, Any]]:
        assert len(self.calls) == 1, f"expected exactly one call, got {len(self.calls)}"
        return self.calls[0]


def _normalize(value: Any) -> Any:
    """Compare stated inputs by value and composed collaborators by type."""
    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(mode="python"))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (str, int, float, bool, type(None), Path)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _normalize(item) for key, item in sorted(value.items())}
    if isinstance(value, frozenset):
        return tuple(sorted((_normalize(item) for item in value), key=repr))
    if isinstance(value, (list, tuple)):
        return tuple(_normalize(item) for item in value)
    return type(value).__name__


def _normalized(call: tuple[tuple[Any, ...], dict[str, Any]]) -> tuple[Any, Any]:
    args, kwargs = call
    return (
        tuple(_normalize(arg) for arg in args),
        {name: _normalize(value) for name, value in sorted(kwargs.items())},
    )


#: (label, patched seam, SDK call, CLI argv). The seam is the name *as the SDK
#: module sees it*, which is where a channel's call actually lands.
PAIRS: tuple[tuple[str, str, str, Callable[[Xcron], Any], list[str]], ...] = (
    (
        "validate",
        "xcron.sdk.schedules",
        "validate_project",
        lambda client: client.schedules.validate(),
        ["validate"],
    ),
    (
        "plan",
        "xcron.sdk.schedules",
        "plan_project",
        lambda client: client.schedules.plan(),
        ["plan"],
    ),
    (
        "status",
        "xcron.sdk.schedules",
        "status_project",
        lambda client: client.schedules.status(),
        ["status"],
    ),
    (
        "apply",
        "xcron.sdk.schedules",
        "apply_project",
        lambda client: client.schedules.apply(),
        ["apply"],
    ),
    (
        "prune",
        "xcron.sdk.schedules",
        "prune_project",
        lambda client: client.schedules.prune(),
        ["prune"],
    ),
    (
        "inspect",
        "xcron.sdk.schedules",
        "inspect_job",
        lambda client: client.schedules.inspect("ping_job"),
        ["inspect", "ping_job"],
    ),
    (
        "jobs list",
        "xcron.sdk.jobs",
        "list_jobs",
        lambda client: client.jobs.list(),
        ["jobs", "list"],
    ),
    (
        "logs list",
        "xcron.sdk.operations",
        "list_logs",
        lambda client: client.operations.list_logs(),
        ["logs", "list"],
    ),
    (
        # The dry-run default is the reason this pair is here: the CLI spells it
        # `--apply` and inverts it, so the two channels state it differently and
        # must still arrive at the same value.
        "logs clear",
        "xcron.sdk.operations",
        "clear_logs",
        lambda client: client.operations.clear_logs(),
        ["logs", "clear"],
    ),
    # Defaults agreeing is only half the claim. These pairs state an option on
    # both sides, which is where a channel drops one silently: a filter that
    # never reaches the use case looks like "no matching jobs", not like a bug.
    (
        "logs clear --apply",
        "xcron.sdk.operations",
        "clear_logs",
        lambda client: client.operations.clear_logs(dry_run=False),
        ["logs", "clear", "--apply"],
    ),
    (
        "logs list --job",
        "xcron.sdk.operations",
        "list_logs",
        lambda client: client.operations.list_logs(job_filter="ping_job"),
        ["logs", "list", "--job", "ping_job"],
    ),
    (
        "jobs show",
        "xcron.sdk.jobs",
        "show_job",
        lambda client: client.jobs.show("ping_job"),
        ["jobs", "show", "ping_job"],
    ),
)


@dataclass(frozen=True)
class ParityCase:
    """One use case that both channels must state identically."""

    label: str
    module: str
    attribute: str
    through_sdk: Callable[[Xcron], Any]
    argv: list[str]
    unscoped: bool = False
    restore_manifest_before_cli: bool = False


CASES: tuple[ParityCase, ...] = tuple(ParityCase(*pair) for pair in PAIRS) + (
    ParityCase(
        "jobs add",
        "xcron.sdk.jobs",
        "add_job",
        lambda client: client.jobs.add(
            JobCreateRequest(
                job_id="cleanup_job",
                command="echo cleanup",
                schedule=ScheduleRequest.every("1h"),
            )
        ),
        ["jobs", "add", "cleanup_job", "--command", "echo cleanup", "--every", "1h"],
        restore_manifest_before_cli=True,
    ),
    ParityCase(
        "jobs update",
        "xcron.sdk.jobs",
        "update_job",
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
    ParityCase(
        "jobs enable",
        "xcron.sdk.jobs",
        "enable_job",
        lambda client: client.jobs.enable("ping_job"),
        ["jobs", "enable", "ping_job"],
    ),
    ParityCase(
        "jobs disable",
        "xcron.sdk.jobs",
        "disable_job",
        lambda client: client.jobs.disable("ping_job"),
        ["jobs", "disable", "ping_job"],
    ),
    ParityCase(
        "jobs remove",
        "xcron.sdk.jobs",
        "remove_job",
        lambda client: client.jobs.remove("ping_job"),
        ["jobs", "remove", "ping_job"],
        restore_manifest_before_cli=True,
    ),
    ParityCase(
        "hooks install",
        "xcron.sdk.hooks",
        "install_agent_hooks",
        lambda client: client.hooks.install(),
        ["hooks", "install"],
    ),
    ParityCase(
        "hooks status",
        "xcron.sdk.hooks",
        "status_agent_hooks",
        lambda client: client.hooks.status(),
        ["hooks", "status"],
    ),
    ParityCase(
        "hooks repair",
        "xcron.sdk.hooks",
        "repair_agent_hooks",
        lambda client: client.hooks.repair(),
        ["hooks", "repair"],
    ),
    ParityCase(
        "hooks session end",
        "xcron.sdk.hooks",
        "record_session_end",
        lambda client: client.hooks.session_end(),
        ["hooks", "session-end"],
    ),
    ParityCase(
        "home initialize",
        "xcron.sdk.home",
        "initialize_workspace",
        lambda client: client.home.initialize(),
        ["init"],
        unscoped=True,
    ),
    ParityCase(
        "metrics show",
        "xcron.sdk.operations",
        "show_metrics",
        lambda client: client.operations.show_metrics(),
        ["metrics", "show"],
        unscoped=True,
    ),
    ParityCase(
        "metrics reset",
        "xcron.sdk.operations",
        "reset_metrics",
        lambda client: client.operations.reset_metrics(),
        ["metrics", "reset"],
        unscoped=True,
    ),
)


@pytest.mark.parametrize(
    "case",
    CASES,
    ids=[case.label for case in CASES],
)
def test_both_channels_reach_the_same_use_case_with_the_same_inputs(
    case: ParityCase,
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seam = importlib.import_module(case.module)
    use_case = getattr(seam, case.attribute)
    manifest_path = project / "resources" / "schedules" / "default.yaml"
    original_manifest = manifest_path.read_text(encoding="utf-8")

    sdk_recorder = Recorder(use_case)
    monkeypatch.setattr(seam, case.attribute, sdk_recorder)
    if case.unscoped:
        with Xcron.open_unscoped() as client:
            case.through_sdk(client)
    else:
        with Xcron.open(project, backend=BACKEND) as client:
            case.through_sdk(client)

    if case.restore_manifest_before_cli:
        manifest_path.write_text(original_manifest, encoding="utf-8")

    cli_recorder = Recorder(use_case)
    monkeypatch.setattr(seam, case.attribute, cli_recorder)
    result = CliRunner().invoke(
        app, ["--project", str(project), "--backend", BACKEND, *case.argv]
    )

    assert result.exit_code == 0, result.output
    assert _normalized(cli_recorder.only_call) == _normalized(sdk_recorder.only_call)


def test_the_parity_check_can_fail() -> None:
    """A comparison that cannot come out unequal proves nothing."""
    one = ((Path("/a"),), {"dry_run": True})
    other = ((Path("/a"),), {"dry_run": False})

    assert _normalized(one) != _normalized(other)


def test_a_composed_collaborator_compares_by_type_not_identity() -> None:
    """Two clients build their own registries; that difference is not a defect."""

    class Registry:
        pass

    assert _normalized(((), {"registry": Registry()})) == _normalized(
        ((), {"registry": Registry()})
    )
