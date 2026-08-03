# xcron Architecture

This prototype keeps the public product contract in `SPEC.md` while organizing
application work by capability. The implementation is deliberately a small
brownfield step: it retains low-level services where they are useful, but makes
the high-level ownership and scheduler boundary explicit.

Top-level layout:

- `apps/cli/` contains the thin Typer/output channel;
- `libs/capabilities/` contains capability-owned use cases:
  `reconciliation`, `jobs`, `operations`, `agent_hooks`, and `home`;
- `libs/domain/` contains canonical models, normalization, identities, and
  desired-vs-deployed diffing;
- `libs/services/` contains reusable low-level mechanisms and native scheduler
  adapters;
- `libs/runtime/` composes the deterministic first-party provider set;
- `libs/sdk/` exposes the typed `Xcron` client for embedders and CLI use; and
- `libs/actions/` is a compatibility import facade for the previous action
  paths.

The dependency direction is:

```text
apps/cli -> xcron_libs.Xcron -> capability actions -> domain + ports
runtime  -> explicit scheduler registry -> native scheduler adapters
adapters -> reconciliation contracts + domain
```

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
- `libs/services/__init__.py` stays non-aggregating. Callers import explicit
  leaf modules so capability/SDK imports cannot transitively load CLI response
  models or rendering dependencies.
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

Only `agent_hooks` currently satisfies the full Level 1 bar. The other four
have the public surface and the declared dependency edges but not yet a single
state owner or a module-owned test lane; their `isolation_level` says so.

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
module: xcron_libs.capabilities.home
hidden_decision: >
  Where the default xcron home lives and what a first-run starter manifest
  contains.
public_entrypoints: [home.api, home.contracts]
owned_state:
  - ~/.xcron/schedules/
  - ~/.xcron/schedules/<starter manifest>
owned_resources: [the xcron home directory tree]
allowed_dependencies: [libs/services/config_loader, libs/services/observability]
cross_module_flows: []
failure_behavior: >
  Creating an existing home is a no-op reported as created=false; the starter
  manifest is never overwritten.
isolation_level: 1 (surface only; state owner shared with config_loader)
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
  - reconciliation.api, reconciliation.contracts
  - libs/domain
  - libs/services/manifest_editor
  - libs/services/observability
cross_module_flows:
  - validates through reconciliation.api.validate_project before every mutation
failure_behavior: >
  Every action returns JobActionResult; a rejected edit sets valid=false and
  changed=false and leaves the manifest untouched.
isolation_level: 1 (surface only; manifest writes still go through a shared service)
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
owned_resources: [SchedulerBackend registry, native scheduler artifacts]
allowed_dependencies:
  - libs/domain
  - libs/services (hashing, schema validation, state store, backends)
cross_module_flows:
  - SchedulerBackend is an inbound port; adapters live in libs/services/backends
failure_behavior: >
  Validation failures short-circuit before any mutation; an unknown backend
  raises UnknownSchedulerBackendError.
isolation_level: >
  1 (surface only) - workspace resolution and manifest mechanics split out in
  phases 4-5, and the metrics write path moves behind an OutcomeRecorder port
verification:
  - tests/test_validation.py, tests/test_planning.py, tests/test_status_projection.py
  - tests/test_launchd_backend.py, tests/test_cron_backend.py
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
allowed_dependencies:
  - reconciliation.api, reconciliation.contracts
  - libs/services/logging_paths, libs/services/metrics, libs/services/state_store
cross_module_flows:
  - resolves the project through reconciliation.api.validate_project
failure_behavior: >
  Clearing defaults to dry_run=true; an unresolvable project returns
  valid=false with the underlying validation attached.
isolation_level: >
  1 (surface only) - reconciliation also writes metrics.json today, so this
  module is not yet the single owner of that file
verification:
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
module paths. The former `xcron_libs.services` package-root aggregate is not
part of that promise: its re-exports were removed deliberately. Callers must
replace imports such as `from xcron_libs.services import get_logger` with the
owning leaf-module import, such as
`from xcron_libs.services.observability import get_logger`.

This is an intentional internal compatibility break. It prevents a low-level
package import from eagerly loading unrelated CLI projections and makes actual
module ownership visible at each call site.

## Distribution shape

`xcron` deliberately ships as one root Python distribution. The root
`pyproject.toml` maps `apps/cli` to `xcron_cli`, `libs` to `xcron_libs`, and
`resources` to `xcron_resources`; its `xcron` console script targets
`xcron_cli.typer_app:run`. `apps/cli` therefore does not have a second
`pyproject.toml`.

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
- manifest editing service for job-level YAML updates
- wrapper rendering with default logs and overlap control
- `launchd` backend
- `cron` backend
- operator-facing `status` projection layered on top of planner diffing
- richer `inspect` results that expose normalized desired data plus
  backend-native detail
- nested `jobs` CLI group for manifest-side job management
- capability-owned reconciliation, manifest jobs, runtime operations, home,
  and agent-hook use cases, with legacy `libs/actions` import shims
- explicit `cron`/`launchd` scheduler registry and backend-neutral deployment
  and scheduler-inspection contracts
- embeddable `Xcron.open(...)` SDK with grouped schedules, jobs, operations,
  hooks, and home APIs
- CLI thin shells that call the SDK rather than embedding backend logic
- Typer-based command declaration and command grouping
- Pydantic response envelopes plus mapper helpers in CLI-owned projection leaf
  modules under `libs/services/`
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
