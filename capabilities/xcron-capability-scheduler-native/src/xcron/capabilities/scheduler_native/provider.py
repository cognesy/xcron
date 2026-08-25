"""Installed native scheduler capability entry point."""

from __future__ import annotations

from xcron.capabilities.scheduler_native.service import NativeScheduleController
from xcron.contracts import ManifestPort, ScheduleControlPort, WorkspacePort
from xcron.kernel import Capability, CapabilityDescriptor, CapabilityProvides, CapabilityRegistration, CapabilityRequirement


DESCRIPTOR = CapabilityDescriptor(
    capability="scheduler",
    implementation="native",
    version="0.1.1",
    kernel_api=">=1,<2",
    requires=(CapabilityRequirement("workspace"), CapabilityRequirement("manifest")),
    provides=CapabilityProvides(
        ports=("scheduler",),
        cli_paths=("validate", "plan", "status", "inspect", "apply", "prune"),
    ),
)


def _build(host) -> CapabilityRegistration:
    return CapabilityRegistration(
        ports={
            "scheduler": NativeScheduleController(
                host.require("workspace", WorkspacePort),
                host.require("manifest", ManifestPort),
            )
        },
        cli_paths={name: None for name in DESCRIPTOR.provides.cli_paths},
    )


CAPABILITY = Capability(DESCRIPTOR, _build)
