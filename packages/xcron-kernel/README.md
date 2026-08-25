# xcron kernel

`xcron-kernel` is the intentionally capability-neutral host for xcron
providers. It contributes to the native PEP 420 `xcron` namespace, and owns the descriptor vocabulary,
entry-point discovery, explicit provider selection, dependency validation,
lazy port construction, lifecycle, and package-contained resource lookup.

It does not name a scheduler, a manifest format, a workspace, a logging
implementation, a CLI framework, or any xcron capability. A lean installation
containing only this wheel can report an absent provider safely; it cannot
accidentally import an application implementation.

Providers advertise a `Capability` value through the
`xcron.capabilities` entry-point group. The descriptor declares its replaceable
capability and implementation identity, kernel API range, dependency claims,
and port/contribution claims. `CapabilityHost` validates all installed choices
before use and never silently selects between competing implementations.

Local development commands are available through `just` in this directory or
through `just ops packages <lane> xcron-kernel` from the workspace root.
