# Contract catalogue

<!-- markdownlint-disable MD013 -->

## Contract design rules

Contracts describe what another package may rely on, not the internal object
graph of the first provider. They live in `xcron.contracts`, use immutable
Pydantic/dataclass values and `@runtime_checkable` protocols, and do not import
an implementation. Every port has a conformance kit in `xcron-testing`.

Port methods receive explicit values (`InvocationContext`, request models, or
workspace handles) rather than asking the provider to read process environment
or re-resolve settings. This preserves xcron's current one-time composition
rule while making the composition provider-independent.

## Kernel contracts

```python
@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    capability: str              # e.g. "manifest"
    implementation: str          # e.g. "yaml"
    version: str
    kernel_api: SpecifierSet
    requires: tuple[CapabilityRequirement, ...]
    provides: CapabilityProvides
    assets: tuple[AssetDeclaration, ...]

@runtime_checkable
class Capability(Protocol):
    descriptor: CapabilityDescriptor

    def register(self, registry: CapabilityRegistry) -> None: ...

class CapabilityHostProtocol(Protocol):
    def require(self, capability: str, port: type[PortT]) -> PortT: ...
```

`CapabilityProvides` declares named port IDs, SDK group IDs, CLI command paths,
and resource/schema IDs before registration. The registry rejects a descriptor
whose registration claims more or less. `CapabilityHost.require` validates the
returned object structurally against the requested runtime-checkable protocol
and caches it once per frozen host.

`CapabilitySelection` maps a capability name to one implementation. A single
installed implementation selects itself; zero or multiple implementations fail
loudly. The `xcron.capabilities` entry-point group carries only trusted package
metadata installed by the environment, never paths from project files.

## Shared domain and invocation contracts

`xcron.contracts.domain` takes ownership of the current schedule and normalized
value models:

- `ProjectManifest`, `ProjectConfig`, `DefaultsConfig`, `JobDefinition`,
  `ScheduleDefinition`, `OverlapPolicy`;
- `NormalizedManifest`, `NormalizedJob`, `NormalizedExecutionConfig`, stable
  job/artifact identities, and duration/cron validation values;
- `ValidationMessage`, `ValidationReport`, and typed public error taxonomy;
- `XcronOptions` and immutable `InvocationContext`.

The contracts package deliberately does not parse YAML, compute a deployment
plan, invoke a scheduler, write a file, or read environment variables.

`InvocationContext` is assembled by the SDK from stable contracts:

```python
@dataclass(frozen=True, slots=True)
class InvocationContext:
    options: XcronOptions
    workspace: ProjectWorkspace | None
    settings: XcronSettings
    event_sink: OutcomeSink
```

Unscoped calls (`init`, metrics) carry `workspace=None` as they do today.
`OutcomeSink` defaults to kernel `NullOutcomeSink`, guaranteeing metrics cannot
become a control-plane prerequisite.

## Product port catalogue

| Capability | Public port | Required operations and compatibility duty |
| --- | --- | --- |
| `workspace` | `WorkspacePort` | Resolve a marked/legacy workspace, initialize home, resolve state and runtime paths. Preserve marker schema, path precedence, and non-overwrite init behavior. |
| `settings` | `SettingsPort` | Compose immutable `XcronSettings` from supplied workspace/options/environment snapshot. Preserve layer order and strict error behavior. |
| `observability` | `ObservabilityPort` | Configure event/log adapter from settings and expose a capability-neutral logger/event sink factory. No action or storage policy. |
| `manifest` | `ManifestPort` | Load, validate, normalize, hash, and atomically edit one schedule manifest. Preserve YAML schema and formatting/editor behavior. |
| `scheduler` | `ScheduleControlPort` | Validate, plan, status, apply, prune, and inspect using typed requests/results. Preserve durable state, wrappers, backend ownership markers, and degraded rules. |
| `jobs` | `JobManagementPort` | List/show/create/update/enable/disable/remove jobs using typed request models. Mutate YAML only through `ManifestPort`; never scheduler artifacts. |
| `logs` | `LogPort` | List and safely clear only owned wrapper logs. Preserve dry-run default and path containment. |
| `metrics` | `MetricsPort`, `OutcomeSink` | Show/reset counters and absorb best-effort action outcomes. A store error must not fail its caller. |
| `agent-hooks` | `AgentHooksPort` | Install/status/repair agent hook files and record session events with typed idempotent results. Preserve unrelated payload data. |

Each value previously exported from a current `capabilities/*/contracts.py` is
assigned to exactly one of these contract modules. The migration task includes
an explicit export inventory so no private action result becomes accidentally
public and no existing typed SDK request becomes an untyped mapping.

## Request/result and error rules

- Public requests are frozen Pydantic models with `extra="forbid"`; the typed
  job request models added in the current SDK remain the baseline.
- Public results retain stable fields and permit additive fields only. CLI
  response models remain channel-private projections, not provider contracts.
- Capability startup/resolution failures use a stable `CapabilityError` code
  family: `capability_unavailable`, `capability_ambiguous`,
  `capability_incompatible`, `capability_cycle`, `capability_collision`, and
  `capability_malformed`.
- Domain/provider failures retain their existing typed meaning
  (`ManifestLoadError`, `WorkspaceResolutionError`, scheduler failure, etc.)
  but relocate their definitions to contracts when a caller needs to catch
  them.
- A provider may return a declared typed failure result when that is the
  current product contract, but must not return `dict[str, Any]` as an escape
  hatch.

## CLI contribution contract

The CLI receives a frozen list of `CliContribution` values. A contribution
contains a unique command path, owning capability descriptor, help key, and a
factory that produces a CLI adapter. The adapter lives in a channel-facing
subpackage of the same capability wheel or in `xcron-cli`; it may import Typer,
but it calls only the capability’s public port. Domain provider code cannot
import `xcron.channels`.

The aggregate default contributes the existing command paths:

```text
init
validate, plan, status, inspect, apply, prune
jobs list|show|add|update|enable|disable|remove
logs list|clear
metrics show|reset
hooks install|status|repair
```

Hidden hook session callbacks remain SDK/integration operations and are not
silently promoted to a public CLI command.
