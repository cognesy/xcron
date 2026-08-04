"""Backend selection and the option normalization a direct caller depends on.

These lived in the architecture file because that is where the scheduler
registry was introduced, but they check behaviour, not structure: a registry
that accepted two backends with one name would be a bug, not a layering
violation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from xcron_libs.capabilities.reconciliation.api import SchedulerRegistry
from xcron_libs.capabilities.reconciliation.contracts import SchedulerRuntimeOptions


def test_scheduler_registry_rejects_duplicate_and_unknown_identities() -> None:
    class First:
        name = "test"

    class Duplicate:
        name = "test"

    with pytest.raises(ValueError, match="duplicate scheduler backend: test"):
        SchedulerRegistry((First(), Duplicate()))

    registry = SchedulerRegistry((First(),))
    with pytest.raises(ValueError, match="unsupported scheduler backend: absent"):
        registry.require("absent")


def test_scheduler_runtime_options_normalize_direct_caller_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A relative path from an embedder resolves against its working directory.

    The CLI always passes absolute paths; a library caller does not have to.
    """
    monkeypatch.chdir(tmp_path)

    options = SchedulerRuntimeOptions.create(
        state_root="state",
        launch_agents_dir=Path("agents"),
        launchctl_domain="gui/501",
        crontab_path="cron/tab",
        manage_launchctl=False,
        manage_crontab=False,
    )

    assert options.state_root == tmp_path / "state"
    assert options.launch_agents_dir == tmp_path / "agents"
    assert options.launchctl_domain == "gui/501"
    assert options.crontab_path == tmp_path / "cron" / "tab"
    assert options.manage_launchctl is False
    assert options.manage_crontab is False
