"""Installed entry point and public xcfg-backed settings-port adapter."""

from __future__ import annotations

import os
from typing import Mapping

from xcron.capabilities.settings_xcfg.loader import load_settings
from xcron.contracts import ProjectWorkspace, Settings, SettingsPort, XcronOptions
from xcron.kernel import (
    AssetDeclaration,
    Capability,
    CapabilityDescriptor,
    CapabilityProvides,
    CapabilityRegistration,
)


class XcfgSettingsProvider:
    """Compose strict settings from the caller's explicit environment snapshot."""

    def compose(
        self,
        workspace: ProjectWorkspace | None,
        options: XcronOptions,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> Settings:
        del options
        return load_settings(
            workspace_config_path=None if workspace is None else workspace.config_path,
            environ=os.environ if environ is None else environ,
        )


DESCRIPTOR = CapabilityDescriptor(
    capability="settings",
    implementation="xcfg",
    version="0.1.4",
    kernel_api=">=1,<2",
    provides=CapabilityProvides(ports=("settings",), assets=("config-default",)),
    assets=(AssetDeclaration("config-default", "resources/config/config.default.yaml"),),
)


def _build(_: object) -> CapabilityRegistration:
    return CapabilityRegistration(
        ports={"settings": XcfgSettingsProvider()},
        assets={"config-default": "resources/config/config.default.yaml"},
    )


CAPABILITY = Capability(DESCRIPTOR, _build)

assert isinstance(XcfgSettingsProvider(), SettingsPort)
