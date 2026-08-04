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
from pathlib import Path
from typing import Any, Callable

import pytest
from typer.testing import CliRunner

from xcron_cli.typer_app import app
from xcron_libs.sdk.client import Xcron

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
    if isinstance(value, (str, int, float, bool, type(None), Path)):
        return value
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
        "xcron_libs.sdk.schedules",
        "validate_project",
        lambda client: client.schedules.validate(),
        ["validate"],
    ),
    (
        "plan",
        "xcron_libs.sdk.schedules",
        "plan_project",
        lambda client: client.schedules.plan(),
        ["plan"],
    ),
    (
        "status",
        "xcron_libs.sdk.schedules",
        "status_project",
        lambda client: client.schedules.status(),
        ["status"],
    ),
    (
        "apply",
        "xcron_libs.sdk.schedules",
        "apply_project",
        lambda client: client.schedules.apply(),
        ["apply"],
    ),
    (
        "prune",
        "xcron_libs.sdk.schedules",
        "prune_project",
        lambda client: client.schedules.prune(),
        ["prune"],
    ),
    (
        "inspect",
        "xcron_libs.sdk.schedules",
        "inspect_job",
        lambda client: client.schedules.inspect("ping_job"),
        ["inspect", "ping_job"],
    ),
    (
        "jobs list",
        "xcron_libs.sdk.jobs",
        "list_jobs",
        lambda client: client.jobs.list(),
        ["jobs", "list"],
    ),
    (
        "logs list",
        "xcron_libs.sdk.operations",
        "list_logs",
        lambda client: client.operations.list_logs(),
        ["logs", "list"],
    ),
    (
        # The dry-run default is the reason this pair is here: the CLI spells it
        # `--apply` and inverts it, so the two channels state it differently and
        # must still arrive at the same value.
        "logs clear",
        "xcron_libs.sdk.operations",
        "clear_logs",
        lambda client: client.operations.clear_logs(),
        ["logs", "clear"],
    ),
    # Defaults agreeing is only half the claim. These pairs state an option on
    # both sides, which is where a channel drops one silently: a filter that
    # never reaches the use case looks like "no matching jobs", not like a bug.
    (
        "logs clear --apply",
        "xcron_libs.sdk.operations",
        "clear_logs",
        lambda client: client.operations.clear_logs(dry_run=False),
        ["logs", "clear", "--apply"],
    ),
    (
        "logs list --job",
        "xcron_libs.sdk.operations",
        "list_logs",
        lambda client: client.operations.list_logs(job_filter="ping_job"),
        ["logs", "list", "--job", "ping_job"],
    ),
    (
        "jobs show",
        "xcron_libs.sdk.jobs",
        "show_job",
        lambda client: client.jobs.show("ping_job"),
        ["jobs", "show", "ping_job"],
    ),
)


@pytest.mark.parametrize(
    ("label", "module", "attribute", "through_sdk", "argv"),
    PAIRS,
    ids=[pair[0] for pair in PAIRS],
)
def test_both_channels_reach_the_same_use_case_with_the_same_inputs(
    label: str,
    module: str,
    attribute: str,
    through_sdk: Callable[[Xcron], Any],
    argv: list[str],
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seam = importlib.import_module(module)
    use_case = getattr(seam, attribute)

    sdk_recorder = Recorder(use_case)
    monkeypatch.setattr(seam, attribute, sdk_recorder)
    with Xcron.open(project, backend=BACKEND) as client:
        through_sdk(client)

    cli_recorder = Recorder(use_case)
    monkeypatch.setattr(seam, attribute, cli_recorder)
    result = CliRunner().invoke(
        app, ["--project", str(project), "--backend", BACKEND, *argv]
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
