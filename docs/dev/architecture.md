# xcron Architecture

`xcron` is a package workspace, not a monolithic import tree. The root
distribution is a metadata-only default aggregate; real code is independently
buildable and installable from its owning distribution.

```text
xcron[cli] aggregate
  ├── xcron-sdk              typed client and public grouped APIs
  ├── xcron-kernel           discovery, selection, capability host
  ├── xcron-contracts        neutral typed requests, results, and ports
  ├── xcron-cli              Typer, AXI output, renderers, packaged help
  └── xcron-capability-*     one selected provider per product capability
```

The distributions share the PEP 420-style `xcron` namespace. No root wheel
supplies a forwarding `xcron` package, and no provider uses a private import
from another provider. The only stable programmatic import is
`xcron.sdk`; contracts are deliberately available as `xcron.contracts` for
provider authors and advanced embedders.

## Capability model

Each `xcron-capability-*` distribution is a complete micropackage with its own:

- `pyproject.toml` and `xcron.capabilities` entry point;
- source, provider descriptor, resources, and focused tests;
- README explaining its decision and boundaries;
- `justfile` with local `check`, `test`, and `build` recipes.

The kernel discovers descriptors through package metadata, validates their API
range, requirements, and port claims, then constructs a selected capability
host. Selection is explicit when multiple implementations exist; the alternate
metrics provider is the deterministic proof lane. A provider may depend on the
neutral contracts and kernel, but never on a sibling provider or the CLI.

Default providers are `workspace:local`, `settings:xcfg`,
`observability:structlog`, `manifest:yaml`, `scheduler:native`,
`jobs:manifest`, `logs:local`, `metrics:local`, and `agent-hooks:local`.

## Channel and SDK boundary

`packages/xcron-cli/src/xcron_cli/` owns the executable channel: Typer command
registration, AXI contracts, output projections, renderers, and Markdown help.
It imports `xcron.sdk`, converts typed results to stdout, and assigns exit
codes. It contains no scheduling policy or provider implementation.

`packages/xcron-sdk/src/xcron/sdk/` owns `Xcron`, a synchronous context-managed
typed client. It asks the capability host only for neutral ports and exposes
grouped APIs for schedules, jobs, operations, hooks, and home. It imports no
concrete provider, CLI package, or terminal dependency.

Requests, values, errors, and ports live in
`packages/xcron-contracts/src/xcron/contracts/`. This keeps a typed caller and
a substitute provider on the same vocabulary without turning either into the
other's dependency.

## Native scheduler and data-plane boundary

`scheduler:native` owns generated wrappers, native `cron` and `launchd`
adapters, derived state, and scheduler inspection. It consumes and produces
contract types only. Generated wrappers execute the declared command directly;
they never invoke the `xcron` executable or SDK. Consequently a missing tool,
SDK, or control-plane provider cannot interrupt an already deployed job.

## Operations catalogue

`ops/` is a separate catalogue of self-service operations. Every operation
directory carries `capability.yaml`, README, local `justfile`, owned scripts,
and focused tests where applicable. The root dispatcher exposes them as:

```sh
just ops list
just ops packages doctor
just ops distribution wheel
just ops quality check
```

This keeps capability build/test/install workflows next to the capability that
owns them, while the `ops/control` schema validates the catalogue and provides
aggregate discovery.

## Enforced contracts

`tests/architecture/test_workspace_packages.py` verifies the workspace shape:
there is no legacy source tree or forwarding bridge; every distribution is
self-contained; PEP 420 parent namespace initializers are absent; descriptors map to
their owner; kernel, contracts, SDK, CLI, and provider boundaries stay separate;
resources stay with their reader; and direct environment reads are explicit.

`xcron-testing` adds layout-independent scans for provider-peer and
provider-channel imports. `tests/parity/` proves the CLI and SDK reach the same
typed ports. `tests/degraded/` proves the durable data plane is independent of
the management plane. `scripts/verify-wheel.sh` proves actual clean installs:
individual packages, the default aggregate, a lean SDK host, alternate provider
selection, and the CLI extra.
