# Target architecture

<!-- markdownlint-disable MD013 -->

## Distribution workspace

The repository becomes a single `uv` workspace. Each item below has its own
`pyproject.toml`, `README.md`, `src/`, `tests/`, and, where needed,
`resources/`, `config/`, `docs/`, and `capability.toml` descriptor source.

```text
.
├── pyproject.toml                         # uv workspace and aggregate dev tooling
├── packages/
│   ├── xcron-kernel/                      # host mechanics and generic errors only
│   ├── xcron-contracts/                   # typed values, ports, descriptor vocabulary
│   ├── xcron-sdk/                         # typed client and application groups
│   ├── xcron-cli/                         # Typer/AXI channel and help rendering
│   ├── xcron-testing/                     # fixtures, contract conformance, install probes
│   └── xcron/                             # aggregate/meta distribution
├── capabilities/
│   ├── xcron-capability-workspace-local/
│   ├── xcron-capability-settings-xcfg/
│   ├── xcron-capability-observability-structlog/
│   ├── xcron-capability-manifest-yaml/
│   ├── xcron-capability-scheduler-native/
│   ├── xcron-capability-jobs-manifest/
│   ├── xcron-capability-logs-local/
│   ├── xcron-capability-metrics-local/
│   └── xcron-capability-agent-hooks-local/
├── specs/                                 # normative capability records and schemas
├── tests/compatibility/                   # aggregate/lean black-box compatibility corpus
└── docs/plans/contract-first-capability-packages/
```

The aggregate `xcron` distribution depends on the default provider set. Its
`cli` extra adds `xcron-cli`; installing `xcron` alone remains an embeddable
SDK without Typer, Rich, or TOON. `xcron-cli` alone owns the console-script
entry point. Version 1 of the workspace releases the packages in lockstep,
even though their boundaries allow later independent cadence.

## Repository operations catalogue

Runtime provider packages are operated through the existing, separate `ops/`
catalogue. Each operation capability is a self-contained micropackage with a
versioned manifest, README, safe local Justfile, and optional scripts,
schemas, tests, and skills. `ops/ops.yaml` explicitly maps an operational
interface to its active provider; `ops/control` validates ownership,
dependencies, provider mapping, command/skill parity, and safe delegation.

The `ops/packages` capability is the workspace-facing adapter. It discovers
package-local Justfiles and delegates `list`, `check`, `test`, `build`, and
`doctor` without copying their implementations. This preserves a vital
distinction: application capability selection is a typed kernel concern;
repository self-service selection is static, audited metadata. Neither is a
dynamic service locator.

## Import topology

`xcron-kernel` owns `xcron/__init__.py` and extends the path with
`pkgutil.extend_path`. `xcron.capabilities` has no `__init__.py` in any
distribution: it is a PEP 420 namespace. Each provider wheel publishes a
disjoint subtree:

```text
xcron.kernel.*
xcron.contracts.*
xcron.sdk.*
xcron.channels.cli.*
xcron.capabilities.workspace_local.*
xcron.capabilities.manifest_yaml.*
...
```

This lets both a lean installation and the aggregate package import the same
`xcron` root without two copies of a module or collisions between provider
wheels. No provider may own `xcron/__init__.py`, `xcron/kernel`,
`xcron/contracts`, `xcron/sdk`, or another provider's subtree.

## Minimal kernel

`xcron.kernel` is intentionally small and names no product capability. It owns
only:

- `Capability`, `CapabilityDescriptor`, `CapabilitySelection`,
  `CapabilityRegistry`, `CapabilityHost`, and `CapabilitySnapshot` mechanics;
- installed entry-point discovery for `xcron.capabilities`;
- semantic-version/API-range validation, dependency-DAG ordering, deterministic
  duplicate diagnostics, lifecycle/close behavior, and no-op generic event
  sink; and
- generic `CapabilityError` subclasses and contained package-resource lookup.

It does **not** import Pydantic, YAML, xcfg, structlog, Typer, Rich, TOON,
platform APIs, subprocess, any capability port, or any xcron provider name.
The kernel’s strongest test is a lean installation containing only
`xcron-kernel`: it can discover no capabilities and reports that fact without
importing a product implementation.

## Host boot and selection

```text
installed entry point metadata
  -> registry validates candidate identity without importing all providers
  -> explicit CapabilitySelection resolves competing implementations
  -> selected descriptors validate kernel API and dependency DAG
  -> host imports selected provider factories in topological order
  -> provider registers typed ports / channel contributions / assets
  -> registry verifies descriptor-to-registration parity and freezes snapshot
  -> SDK and CLI project the same snapshot
```

The first release uses the package installation set as the source of truth:
there is one default implementation for every required capability. An embedder
may pass `CapabilitySelection` to choose a competing implementation. No
environment variable, project YAML, or workspace configuration may name an
import target; executable selection remains install-time or explicit API data.

The host validates all of these before an operation can write:

- descriptor ID, package version, and kernel API range;
- one selected implementation for each required capability;
- dependency references and cycles;
- duplicate port, operation, SDK-group, CLI-path, or asset-schema claims;
- descriptor `provides` set exactly matching registration; and
- capability assets contained under the owning distribution.

Every error names the capability ID/implementation and a concrete install or
selection remedy. There is never a silent fallback.

## Channel and SDK shape

`xcron-sdk` provides the public synchronous, context-managed `Xcron` client.
It imports only kernel and contracts. `Xcron.open()` discovers and freezes a
host; it obtains workspace and settings values once per scoped invocation
through `WorkspacePort` and `SettingsPort`, then passes a typed immutable
`InvocationContext` to an operation port.

Existing groups remain public compatibility affordances:

| SDK group | Required port(s) |
| --- | --- |
| `schedules` | `ScheduleControlPort` |
| `jobs` | `JobManagementPort` |
| `operations` | `LogPort`, `MetricsPort` |
| `hooks` | `AgentHooksPort` |
| `home` | `WorkspacePort` |

The client constructs a group lazily. Asking a lean install for an unavailable
group raises `CapabilityUnavailableError`; it does not make client import or
unrelated operations fail. The root client keeps idempotent close and
use-after-close behavior.

`xcron-cli` owns Typer input, AXI response projection, TOON/JSON/tmux
rendering, authored help, error envelopes, and exit codes. A provider can
register a `CliContribution` only through a channel adapter supplied by the
CLI package. The provider's domain code never imports Typer or a renderer.
CLI attachment validates duplicate command paths before creating the app.

## Capability package anatomy

Every capability package follows this shape, including a provider-specific
README that explains its hidden decision and replacement contract.

```text
capabilities/xcron-capability-manifest-yaml/
├── pyproject.toml                         # dependency closure and entry point
├── capability.toml                        # source descriptor, generated/checked metadata
├── README.md                              # scope, state ownership, substitution notes
├── justfile                               # safe local discovery and package-owned lanes
├── src/xcron/capabilities/manifest_yaml/
│   ├── capability.py                      # descriptor and build(host)
│   ├── provider.py                        # public port implementation
│   ├── _loader.py                         # private mechanism
│   ├── _editor.py
│   └── resources/schemas/schedules.schema.yaml
├── tests/
│   ├── test_provider.py
│   ├── test_contract_conformance.py
│   ├── test_assets.py
│   └── fixtures/
└── docs/                                  # non-packaged explanatory material if needed
```

The `pyproject.toml` entry point is data, not a hand-maintained central list:

```toml
[project.entry-points."xcron.capabilities"]
manifest-yaml = "xcron.capabilities.manifest_yaml.capability:capability"
```

The capability ID is `manifest`; its implementation is `yaml`. `capability`
is a `Capability` value with a build callable returning an object verified
against `ManifestPort`. The directory and wheel name make implementation
ownership visible, while the port name is the replaceable decision.
