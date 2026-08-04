"""Settings layering, one test per adjacent pair of layers.

A layering bug produces a working program with the wrong values in it, so the
tests are written to fail on a reordering rather than on a total absence: each
one sets the *same* key in two adjacent layers and asserts which wins.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from xcron_libs.configuration.api import environment_overrides, load_settings
from xcron_libs.configuration.contracts import (
    CONFIG_ENV_NAME_VAR,
    CONFIG_PATH_ENV_VAR,
    ConfigurationError,
    ENV_SETTINGS,
    Settings,
)


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


@pytest.fixture()
def user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the XDG user layer somewhere this test owns."""
    root = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(root))
    return root / "xcron" / "config.yaml"


def test_the_packaged_default_is_the_base(tmp_path: Path) -> None:
    settings = load_settings(environ={})

    assert settings == Settings()
    assert settings.manage_launchctl is True
    assert settings.state_root is None


def test_the_user_config_beats_the_packaged_default(user_config: Path) -> None:
    _write(user_config, "launchctl_domain: gui/from-user\n")

    settings = load_settings(environ={"XDG_CONFIG_HOME": str(user_config.parents[1])})

    assert settings.launchctl_domain == "gui/from-user"


def test_the_workspace_config_beats_the_user_config(tmp_path: Path, user_config: Path) -> None:
    _write(user_config, "launchctl_domain: gui/from-user\n")
    workspace = _write(tmp_path / "ws" / "config.yaml", "launchctl_domain: gui/from-workspace\n")

    settings = load_settings(
        workspace_config_path=workspace,
        environ={"XDG_CONFIG_HOME": str(user_config.parents[1])},
    )

    assert settings.launchctl_domain == "gui/from-workspace"


def test_the_environment_beats_the_workspace_config(tmp_path: Path) -> None:
    workspace = _write(tmp_path / "ws" / "config.yaml", "launchctl_domain: gui/from-workspace\n")

    settings = load_settings(
        workspace_config_path=workspace,
        environ={"XCRON_LAUNCHCTL_DOMAIN": "gui/from-env"},
    )

    assert settings.launchctl_domain == "gui/from-env"


def test_a_layer_that_sets_one_key_leaves_its_siblings_alone(
    tmp_path: Path, user_config: Path
) -> None:
    """Deep merge, not replacement — the classic hand-rolled-loader bug."""
    _write(user_config, "launchctl_domain: gui/from-user\ncrontab_path: /tmp/from-user\n")
    workspace = _write(tmp_path / "ws" / "config.yaml", "crontab_path: /tmp/from-workspace\n")

    settings = load_settings(
        workspace_config_path=workspace,
        environ={"XDG_CONFIG_HOME": str(user_config.parents[1])},
    )

    assert settings.crontab_path == Path("/tmp/from-workspace")
    assert settings.launchctl_domain == "gui/from-user"


def test_an_absent_workspace_config_simply_contributes_nothing(tmp_path: Path) -> None:
    settings = load_settings(workspace_config_path=tmp_path / "nothing-here.yaml", environ={})

    assert settings == Settings()


def test_an_explicit_file_replaces_the_base_rather_than_merging_over_it(tmp_path: Path) -> None:
    explicit = _write(tmp_path / "explicit.yaml", "manage_crontab: false\n")

    settings = load_settings(config_path=explicit, environ={})

    assert settings.manage_crontab is False
    assert settings.manage_launchctl is True  # the model default, not the packaged file


def test_the_config_environment_variable_names_an_explicit_file(tmp_path: Path) -> None:
    explicit = _write(tmp_path / "explicit.yaml", "launchctl_domain: gui/explicit\n")

    settings = load_settings(environ={CONFIG_PATH_ENV_VAR: str(explicit)})

    assert settings.launchctl_domain == "gui/explicit"


def test_a_named_file_that_is_missing_is_an_error_not_a_silent_default(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="config file not found"):
        load_settings(environ={CONFIG_PATH_ENV_VAR: str(tmp_path / "absent.yaml")})


def test_selecting_an_unknown_named_environment_fails(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        load_settings(environ={CONFIG_ENV_NAME_VAR: "no-such-environment"})


def test_an_unknown_key_is_rejected_rather_than_ignored(tmp_path: Path) -> None:
    """`extra="forbid"`: a typo fails loudly and names the field."""
    explicit = _write(tmp_path / "typo.yaml", "manage_lanchctl: false\n")

    with pytest.raises(ConfigurationError, match="manage_lanchctl"):
        load_settings(config_path=explicit, environ={})


def test_a_value_of_the_wrong_type_is_rejected(tmp_path: Path) -> None:
    explicit = _write(tmp_path / "wrong.yaml", "manage_crontab: sometimes\n")

    with pytest.raises(ConfigurationError, match="manage_crontab"):
        load_settings(config_path=explicit, environ={})


def test_every_published_variable_reaches_its_setting() -> None:
    """The mapping table is the environment contract; nothing may drift off it."""
    settings = load_settings(
        environ={
            "XCRON_STATE_ROOT": "/tmp/state",
            "XCRON_LAUNCH_AGENTS_DIR": "/tmp/agents",
            "XCRON_LAUNCHCTL_DOMAIN": "gui/501",
            "XCRON_CRONTAB_PATH": "/tmp/crontab",
            "XCRON_MANAGE_LAUNCHCTL": "0",
            "XCRON_MANAGE_CRONTAB": "0",
        }
    )

    assert set(ENV_SETTINGS.values()) == set(Settings.model_fields)
    assert settings == Settings(
        state_root=Path("/tmp/state"),
        launch_agents_dir=Path("/tmp/agents"),
        launchctl_domain="gui/501",
        crontab_path=Path("/tmp/crontab"),
        manage_launchctl=False,
        manage_crontab=False,
    )


@pytest.mark.parametrize("value", ["0", "false", "False", "no", "NO"])
def test_the_historic_false_values_still_turn_a_flag_off(value: str) -> None:
    """Copied from the CLI helper this replaced; exported variables must not shift."""
    assert environment_overrides({"XCRON_MANAGE_CRONTAB": value}) == {"manage_crontab": "false"}


@pytest.mark.parametrize("value", ["1", "true", "yes", "anything"])
def test_every_other_non_empty_value_turns_a_flag_on(value: str) -> None:
    assert environment_overrides({"XCRON_MANAGE_CRONTAB": value}) == {"manage_crontab": "true"}


def test_an_empty_variable_is_the_same_as_an_unset_one() -> None:
    assert environment_overrides({"XCRON_STATE_ROOT": ""}) == {}
    assert load_settings(environ={"XCRON_STATE_ROOT": ""}).state_root is None


def test_settings_are_frozen_so_nothing_downstream_can_edit_them() -> None:
    settings = load_settings(environ={})

    with pytest.raises(Exception):
        settings.manage_crontab = False
