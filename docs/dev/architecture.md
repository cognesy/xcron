# xcron Architecture

This prototype keeps the public product contract in `SPEC.md` while organizing
application work by capability. Every file now belongs to exactly one module or
to a declared leaf; there is no shared services drawer left to put things in.

Top-level layout:

- `apps/cli/` contains the thin Typer/output channel;
- `libs/capabilities/` contains capability-owned use cases: `workspace`,
  `manifest`, `reconciliation`, `jobs`, `operations`, `agent_hooks`, and `home`;
- `libs/domain/` is a leaf of manifest value types, normalization, and
  identities; desired-vs-deployed diffing belongs to the reconciliation module;
- `libs/shared/` is a strict leaf: structlog wiring, logging configuration, and
  the packaged logging resource. It holds no workflow, persists nothing, and may
  not import a capability. Adding a module here is a recorded decision;
- `libs/runtime/` composes the deterministic first-party provider set and owns
  every adapter that joins two capabilities;
- `libs/sdk/` exposes the typed `Xcron` client for embedders and CLI use; and
- `libs/actions/` is a compatibility import facade for the previous action
  paths.

The dependency direction is:

```text
apps/cli -> xcron_libs.Xcron -> module api/contracts -> module internals
runtime  -> explicit scheduler registry -> module-owned scheduler adapters
runtime  -> OutcomeRecorder adapter -> operations.api
adapters -> reconciliation ports + reconciliation domain
every module -> libs/domain, libs/shared          (leaves only)
```

The only permitted cross-module edges are:

```text
home           -> workspace.api
manifest       -> workspace.api
jobs           -> manifest.api, reconciliation.api
operations     -> workspace.api, reconciliation.api
reconciliation -> workspace.api, manifest.api
```

`reconciliation -> operations` is deliberately absent. Reconciliation reports
what it did through an `OutcomeRecorder` port; `libs/runtime/composition.py`
supplies the adapter that calls `operations.api.record_outcome`. That keeps
`metrics.json` to a single writing module and makes the cross-capability flow
one named contract instead of two capabilities sharing a file.

Rules:

- CLI code parses Typer input, opens `Xcron`, maps typed results/errors through
  `Output`, and chooses exit codes. It does not import action implementations,
  native backend functions, or output encoders below its channel boundary.
- Capabilities own use-case policy and return typed results. They do not import
  `xcron_cli`, Typer, Rich, TOON, JSON, or tmux renderers.
- `reconciliation` owns the typed scheduler port, backend-neutral
  `DeploymentPlan` and `SchedulerInspection` contracts, and registry selection.
  Backends must never import an action result or the SDK.
- `runtime` composes only. It owns immutable resolved invocation options and
  the scheduler registry, owns no product policy, and provides the same
  first-party provider set to all channels.
- `Xcron` is a synchronous context-managed SDK. It owns no native scheduler
  connection today, has idempotent `close()`, rejects use after close, and does
  not import CLI/output code. See [sdk.md](sdk.md) for its public surface and
  lifecycle contract.
- `libs/actions` preserves compatibility for current callers while code moves;
  it must not grow new business logic.
- Packaged resources ship inside the module that reads them:
  `libs/capabilities/manifest/resources/schemas/` and
  `libs/shared/resources/logging/`. There is no shared `xcron_resources`
  distribution package.
- The CLI projection cluster lives inside the channel that owns it:
  `apps/cli/contracts.py`, `apps/cli/mappers.py`, `apps/cli/responses.py`, and
  `apps/cli/presenters/` (AXI field selection, TOON, tmux, and Rich help).
  Authored help pages are packaged data of that channel, under
  `apps/cli/resources/help/`. Nothing under `libs/` may import `xcron_cli` in
  any import form; `tests/test_reconciliation_architecture.py` enforces this
  across every file in `libs/`.

## Verified Level 1 module

`xcron_libs.capabilities.agent_hooks` is the first capability with executable
Level 1 isolation evidence. It owns the repository-local Codex and Claude hook
lifecycle and file-format decision, including these four state paths:

- `.codex/config.toml`
- `.codex/hooks.json`
- `.claude/settings.json`
- `session-history.jsonl`

Its only cross-module entrypoints are `agent_hooks.api` and
`agent_hooks.contracts`. The SDK `HooksAPI` is the sole product/channel adapter;
the CLI reaches hooks through that SDK. The implementation is standard-library
only and imports no sibling capability, SDK, CLI, presentation, or global
service implementation. AST checks cover direct, submodule, root-`from`, and
aliased forbidden imports, with planted negative examples. A focused module
test lane covers payload preservation, idempotency, typed failures, and exact
state ownership.

This is a Level 1 code-module result, not a new distribution, dependency set,
process boundary, plugin system, or service deployment.

## Module cards

Every capability now declares a public surface (`api.py` plus `contracts.py`)
and a non-aggregating `__init__.py`. The cards below are the checked-in record
of what each module hides, owns, and is allowed to depend on;
`tests/test_reconciliation_architecture.py` enforces the surface, the
initializer, and the `allowed_dependencies` line of every card.

`agent_hooks`, `reconciliation`, `manifest`, `workspace`, and `operations` own
their implementation outright and have module-owned test lanes. `home` and
`jobs` have the public surface and the declared dependency edges but reach their
state through another module's API; each card's `isolation_level` says which.

```yaml
module: xcron_libs.capabilities.agent_hooks
hidden_decision: >
  How repository-local Codex and Claude hooks are installed, repaired, and
  detected, including each agent's on-disk hook file format.
public_entrypoints: [agent_hooks.api, agent_hooks.contracts]
owned_state:
  - .codex/config.toml
  - .codex/hooks.json
  - .claude/settings.json
  - session-history.jsonl
owned_resources: [repository-local agent configuration files]
allowed_dependencies: [stdlib]
cross_module_flows:
  - libs/sdk/hooks.py adapts api/contracts for the SDK and CLI
failure_behavior: >
  Typed AgentHooksError; installation is idempotent and preserves unrelated
  payload keys.
isolation_level: 1 (verified)
verification:
  - tests/test_agent_hooks.py
  - tests/test_reconciliation_architecture.py
```

```yaml
module: xcron_libs.capabilities.workspace
hidden_decision: >
  What directory an invocation is scoped to, where xcron's home is, and where
  every derived artifact for a project lands on this machine.
public_entrypoints: [workspace.api, workspace.contracts]
owned_state: []          # owns the layout, not the files written into it
owned_resources:
  - the project-root resolution precedence
  - the XCRON_HOME and XCRON_STATE_ROOT environment contracts
  - the derived state tree (projects/<id>/{wrappers,logs,locks})
owned_code:
  - resolver.py (xcron home, project root, schedules directory)
  - paths.py (state root and per-job runtime paths)
allowed_dependencies: [libs/domain, libs/shared]
cross_module_flows:
  - callee: manifest, reconciliation, operations, home
failure_behavior: >
  A missing or non-directory root raises WorkspaceResolutionError; an unknown
  platform raises UnsupportedPlatformError. No path function creates
  directories except ensure_runtime_dirs.
isolation_level: 1 (surface plus owned implementation)
verification:
  - tests/modules/workspace/ (module-owned lane)
  - tests/test_reconciliation_architecture.py
```

```yaml
module: xcron_libs.capabilities.manifest
hidden_decision: >
  The on-disk schedule manifest format: how a manifest is discovered, parsed,
  schema- and semantics-validated, hashed, and edited in place.
public_entrypoints: [manifest.api, manifest.contracts]
owned_state:
  - schedules/*.yaml (the whole document, including author formatting)
owned_resources:
  - resources/schemas/schedules.schema.yaml (packaged with the module)
  - the manifest identity hashes and WRAPPER_RENDERER_VERSION
owned_code:
  - _loader.py, _schema.py, _editor.py, _hashes.py
allowed_dependencies: [workspace.api, libs/domain, libs/shared]
cross_module_flows:
  - callee: jobs, reconciliation
failure_behavior: >
  Every failure is a ManifestLoadError or ManifestEditError subclass; a
  rejected edit is written atomically or not at all, never partially.
isolation_level: 1 (surface plus owned implementation)
verification:
  - tests/modules/manifest/ (module-owned lane)
  - tests/test_reconciliation_architecture.py
```

```yaml
module: xcron_libs.capabilities.home
hidden_decision: >
  What a first-run starter manifest contains.
public_entrypoints: [home.api, home.contracts]
owned_state:
  - ~/.xcron/schedules/<starter manifest>
owned_resources: [the starter manifest template]
allowed_dependencies: [workspace.api, libs/shared]
cross_module_flows:
  - resolves the home directory through workspace.api
failure_behavior: >
  Creating an existing home is a no-op reported as created=false; the starter
  manifest is never overwritten.
isolation_level: >
  1 (surface only) - this module is 63 lines and folds into
  workspace/initializer.py in phase 5
verification:
  - tests/test_init_home.py
  - tests/test_reconciliation_architecture.py
```

```yaml
module: xcron_libs.capabilities.jobs
hidden_decision: >
  How a job entry is added, edited, enabled, and removed inside a schedule
  manifest while preserving the author's YAML.
public_entrypoints: [jobs.api, jobs.contracts]
owned_state:
  - resources/schedules/*.yaml (job entries only)
owned_resources: [manifest job list]
allowed_dependencies:
  - manifest.api, manifest.contracts
  - reconciliation.api, reconciliation.contracts
  - libs/domain, libs/shared
cross_module_flows:
  - validates through reconciliation.api.validate_project before every mutation
  - every manifest write goes through manifest.api; jobs never touches the file
failure_behavior: >
  Every action returns JobActionResult; a rejected edit sets valid=false and
  changed=false and leaves the manifest untouched.
isolation_level: >
  1 (surface only) - jobs owns use-case semantics, not the manifest file; the
  format belongs to the manifest module
verification:
  - tests/test_job_actions.py
  - tests/test_reconciliation_architecture.py
```

```yaml
module: xcron_libs.capabilities.reconciliation
hidden_decision: >
  How desired manifest state is compared to actual native scheduler state and
  converged, and which artifacts xcron may claim as its own.
public_entrypoints: [reconciliation.api, reconciliation.contracts]
owned_state:
  - project-state.json
  - launchd plists under the selected LaunchAgents directory
  - xcron-owned crontab entries
  - generated job wrapper scripts
owned_resources:
  - the SchedulerBackend registry and its first-party adapters
  - native scheduler artifacts
  - the launchctl and crontab subprocess boundary
owned_code:
  - adapters/ (cron, launchd, and their logged-subprocess boundary)
  - domain.py (desired-vs-deployed diffing)
  - ports.py (the SchedulerBackend and OutcomeRecorder ports)
  - registry.py (adapter registry and default-backend selection)
  - state_store.py (project-state.json persistence)
  - wrapper.py (job wrapper rendering)
allowed_dependencies:
  - workspace.api, workspace.contracts
  - manifest.api, manifest.contracts
  - libs/domain, libs/shared
cross_module_flows:
  - SchedulerBackend is an inbound port; adapters are module-private
  - callee: OutcomeRecorder port, wired to operations by the composition root
failure_behavior: >
  Validation failures short-circuit before any mutation; an unknown backend
  raises UnknownSchedulerBackendError. Outcome recording is best-effort and can
  never fail a convergence run - the default recorder does nothing at all.
isolation_level: 1 (surface plus owned implementation)
verification:
  - tests/modules/reconciliation/ (module-owned lane, including a fake-backend
    lane that imports only api, contracts, and ports)
  - tests/test_reconciliation_architecture.py
```

```yaml
module: xcron_libs.capabilities.operations
hidden_decision: >
  Where wrapper logs and runtime counters live, and what clearing or resetting
  them means.
public_entrypoints: [operations.api, operations.contracts]
owned_state:
  - per-project stdout, stderr, and event log files
  - metrics/metrics.json
owned_resources: [runtime log directory, metrics file]
owned_code:
  - logs.py (log discovery, rotation, and clearing)
  - metrics.py (show, reset, and the single public write: record_outcome)
  - metrics_store.py (the only writer of metrics/metrics.json)
allowed_dependencies:
  - workspace.api, workspace.contracts
  - reconciliation.api, reconciliation.contracts
  - libs/shared
cross_module_flows:
  - resolves the project through reconciliation.api.validate_project
  - caller: reconciliation, via the OutcomeRecorder adapter in libs/runtime
failure_behavior: >
  Clearing defaults to dry_run=true; an unresolvable project returns
  valid=false with the underlying validation attached. record_outcome never
  raises, so a broken metrics file cannot fail its caller.
isolation_level: 1 (surface plus sole ownership of the metrics state family)
verification:
  - tests/modules/operations/ (module-owned lane)
  - tests/test_cli_logs.py
  - tests/test_reconciliation_architecture.py
```

Current model decisions:

- schedule manifests live under `resources/schedules/`
- the manifest is per-project only
- every manifest must define `project.id`
- backend-neutral job identity is derived as `<project.id>.<job.id>`
- `schedule.every` remains part of the public model, constrained to a simple
  duration string for v1

The Python prototype should preserve these boundaries so the later Go rewrite
can keep the same external contract and internal separation of concerns.

## Migration compatibility

`xcron_libs.actions` remains an import-compatible facade for the prior action
module paths. `xcron_libs.services`, `xcron_libs.infra`, and `xcron_resources`
are not part of that promise and no longer exist. Their contents moved to the
module that owns each decision:

| Former path | New owner |
| --- | --- |
| `services.observability`, `services.logging_config` | `libs/shared/` |
| `services.config_loader` (home, project root) | `workspace.api` |
| `services.logging_paths`, `services.state_paths` | `workspace.api` |
| `services.config_loader` (manifest loading) | `manifest.api` |
| `services.schema_validator`, `services.hash_service` | `manifest.api` |
| `services.manifest_editor` | `manifest.api` |
| `services.metrics` | `operations` (private; write via `record_outcome`) |
| `xcron_resources.schemas` | `manifest.resources.schemas` |
| `xcron_resources.logging` | `shared.resources.logging` |

This is an intentional internal compatibility break. A package that anything may
import and that imports anything back is the coupling this refactor exists to
remove; keeping a shim would have preserved exactly that.

## Distribution shape

`xcron` deliberately ships as one root Python distribution. The root
`pyproject.toml` maps `apps/cli` to `xcron_cli` and `libs` to `xcron_libs`; its
`xcron` console script targets `xcron_cli.typer_app:run`. `apps/cli` therefore
does not have a second `pyproject.toml`. Packaged data ships inside the module
that reads it, so there is no third top-level distribution package.

The CLI channel, native SDK, capability implementation, and packaged runtime
resources share one version, dependency graph, and release lifecycle. Splitting
the CLI into a separate distribution would introduce a cross-distribution
dependency on the SDK/capabilities and a second release/install boundary
without providing independent ownership, dependencies, or release cadence.
Reconsider the split only if one of those operational boundaries becomes real.

Older xpack versions warned about the root entry point and missing app-local
metadata. Those warnings are accepted when using such a version because the
single-distribution mapping is intentional, not accidental. Current xpack
recognizes both the scoped root entry point and `apps/cli` package mapping as
passing x-style structures: the live structure check reports six passes and no
warnings. `.xpack/config.toml` remains the installed-wheel verification
contract.

Implemented prototype components:

- validation, normalization, and stable hashing
- planner and per-project derived local state
- a manifest module owning the format: loading, schema and semantic validation,
  identity hashing, and formatting-preserving job edits
- wrapper rendering with default logs and overlap control
- `launchd` backend
- `cron` backend
- operator-facing `status` projection layered on top of planner diffing
- richer `inspect` results that expose normalized desired data plus
  backend-native detail
- nested `jobs` CLI group for manifest-side job management
- capability-owned workspace, manifest, reconciliation, jobs, operations, home,
  and agent-hook use cases, with legacy `libs/actions` import shims
- explicit `cron`/`launchd` scheduler registry and backend-neutral deployment
  and scheduler-inspection contracts
- embeddable `Xcron.open(...)` SDK with grouped schedules, jobs, operations,
  hooks, and home APIs
- CLI thin shells that call the SDK rather than embedding backend logic
- Typer-based command declaration and command grouping
- Pydantic response envelopes plus mapper helpers under `apps/cli/`
- unified machine/human output rendering:
  - TOON for machine-facing output
  - Rich-backed help and human-facing presentation paths
- resource-backed runtime help under `apps/cli/resources/help/`
- repo-local Codex and Claude hook adapters plus install/status/repair flows

Verification model:

- deterministic core lane is `./scripts/verify-core.sh`
- today that core lane runs the safe default `uv run pytest`
- default core verification stays safe and does not mutate the host scheduler
- host-gated `launchd` integration exists for real macOS verification
- Docker/Colima-gated cron integration exists for real Linux cron verification

See `docs/dev/go-rewrite-contract.md` for the external behavior that should
remain stable in the later Go implementation.
