"""Contract and layering checks for the xcfg settings provider wheel."""

from __future__ import annotations

from xcron.capabilities.settings_xcfg.provider import CAPABILITY
from xcron.contracts import ProjectWorkspace, SettingsPort, XcronOptions
from xcron.kernel import CapabilityHost, CapabilityRegistry


def test_provider_composes_only_the_explicit_environment(tmp_path) -> None:
    """The host reaches xcfg through the stable settings port."""
    host = CapabilityHost(CapabilityRegistry((CAPABILITY,)))
    provider = host.require("settings", SettingsPort)

    settings = provider.compose(
        None,
        XcronOptions.create(),
        environ={
            "XCRON_STATE_ROOT": str(tmp_path / "state"),
            "XCRON_MANAGE_CRONTAB": "0",
        },
    )

    assert settings.state_root == tmp_path / "state"
    assert settings.manage_crontab is False
    assert host.freeze().ids() == ("settings:xcfg",)


def test_workspace_config_layer_is_supplied_as_data(tmp_path) -> None:
    """A resolved workspace chooses its config without provider path discovery."""
    config = tmp_path / "config.yaml"
    config.write_text("manage_launchctl: false\n", encoding="utf-8")
    workspace = ProjectWorkspace(
        root=tmp_path,
        manifest_dir=tmp_path / "schedules",
        config_path=config,
        marker_path=tmp_path / "marker.toml",
        marker=None,
    )
    provider = CapabilityHost(CapabilityRegistry((CAPABILITY,))).require("settings", SettingsPort)

    settings = provider.compose(workspace, XcronOptions.create(), environ={})

    assert settings.manage_launchctl is False
