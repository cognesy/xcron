# xcron Architecture

This prototype keeps the public product contract in `SPEC.md` while organizing
application work by capability. Every file now belongs to exactly one module or
to a declared leaf; there is no shared services drawer left to put things in.

Top-level layout:

- `src/xcron/channels/cli/` contains the thin Typer/output channel;
- `src/xcron/capabilities/` contains capability-owned use cases: `workspace`,
  `manifest`, `reconciliation`, `jobs`, `operations`, and `agent_hooks`;
- `src/xcron/configuration/` is a leaf that owns how settings are composed out of
  packaged defaults, config files, and the environment. It is the only importer
  of `xcfg` and depends on no capability;
- `src/xcron/domain/` is a leaf of manifest value types, normalization, and
  identities; desired-vs-deployed diffing belongs to the reconciliation module;
- `src/xcron/shared/` is a strict leaf: structlog wiring, logging configuration, and
  the packaged logging resource. It holds no workflow, persists nothing, and may
  not import a capability. Adding a module here is a recorded decision;
- `src/xcron/runtime/` composes the deterministic first-party provider set and owns
  every adapter that joins two capabilities;
- `src/xcron/sdk/` exposes the typed `Xcron` client for embedders and CLI use.

There is no flat action namespace. Every use case is reached through the `api`
of the module that owns it, so the import says who is responsible for the
answer.

The dependency direction is:

```text
src/xcron/channels/cli -> xcron.Xcron -> module api/contracts -> module internals
runtime  -> explicit scheduler registry -> module-owned scheduler adapters
runtime  -> OutcomeRecorder adapter -> operations.api
adapters -> reconciliation ports + reconciliation domain
runtime  -> configuration.api -> the one resolved Settings value
every module -> src/xcron/domain, src/xcron/shared          (leaves only)
```

The only permitted cross-module edges are:

```text
manifest       -> workspace.api
jobs           -> manifest.api, reconciliation.api
operations     -> workspace.api, reconciliation.api
reconciliation -> workspace.api, manifest.api
```

`reconciliation -> operations` is deliberately absent. Reconciliation reports
what it did through an `OutcomeRecorder` port; `src/xcron/runtime/composition.py`
supplies the adapter that calls `operations.api.record_outcome`. That keeps
`metrics.json` to a single writing module and makes the cross-capability flow
one named contract instead of two capabilities sharing a file.

Settings follow the same shape. No capability reads `os.environ` for a tunable
value: `src/xcron/runtime/composition.py` calls `configuration.api.load_settings`
once per invocation and hands the resolved `Settings` down as a value. The
composed order, later winning, is packaged default → user config → workspace
`config.yaml` → environment variable → explicit argument. Only identity
variables — `XCRON_HOME` and `XCRON_PROJECT`, which select *which* files are
read — stay with `workspace`, because they cannot themselves come from a config
file. `tests/architecture/test_settings_boundary.py` pins the exact set of
files allowed to name `os.environ`.

Rules:

- CLI code parses Typer input, opens `Xcron`, maps typed results/errors through
  `Output`, and chooses exit codes. It does not import action implementations,
  native backend functions, or output encoders below its channel boundary.
- Capabilities own use-case policy and return typed results. They do not import
  `xcron.channels.cli`, Typer, Rich, TOON, JSON, or tmux renderers.
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
- Packaged resources ship inside the module that reads them:
  `src/xcron/capabilities/manifest/resources/schemas/` and
  `src/xcron/shared/resources/logging/`. There is no shared `xcron_resources`
  distribution package.
- The CLI projection cluster lives inside the channel that owns it:
  `contracts.py`, `mappers.py`, `responses.py`, and `presenters/` under
  `xcron/channels/cli/` (AXI field selection, TOON, tmux, and Rich help).
  Authored help pages are packaged data of that channel, under
  `src/xcron/channels/cli/resources/help/`. Nothing below `xcron.channels` may
  import a channel in any import form; `tests/architecture/` enforces this
  across every file under `src/xcron/` that is not itself a channel.

## Verified Level 1 module

`xcron.capabilities.agent_hooks` is the first capability with executable
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
`tests/architecture/` enforces the surface, the initializer, and the
`allowed_dependencies` line of every card.

`agent_hooks`, `reconciliation`, `manifest`, `workspace`, and `operations` own
their implementation outright and have module-owned test lanes. `jobs` has the
public surface and the declared dependency edges but reaches its state through
another module's API; each card's `isolation_level` says which.

```yaml
module: xcron.capabilities.agent_hooks
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
  - src/xcron/sdk/hooks.py adapts api/contracts for the SDK and CLI
failure_behavior: >
  Typed AgentHooksError; installation is idempotent and preserves unrelated
  payload keys.
isolation_level: 1 (verified)
verification:
  - tests/test_agent_hooks.py
  - tests/architecture/ (Import Linter contracts plus the AST scanner)
```

```yaml
module: xcron.capabilities.workspace
hidden_decision: >
  What directory an invocation is scoped to, how that directory is recognized
  as a workspace, and where every derived artifact for a project lands on this
  machine.
public_entrypoints: [workspace.api, workspace.contracts]
owned_state:
  - marker.toml (the workspace marker, in the project root)
  - ~/.xcron/schedules/<starter manifest>
owned_resources:
  - the project-root resolution precedence
  - the marker file format and its schema version
  - the XCRON_HOME and XCRON_PROJECT identity variables
  - the derived state tree (projects/<id>/{wrappers,logs,locks})
  - the starter manifest template
owned_code:
  - resolver.py (identity: explicit > XCRON_PROJECT > nearest marker > home)
  - marker.py (marker.toml read, write, and render)
  - paths.py (state root, xcron home layout, per-job runtime paths)
  - initializer.py (first-run creation; never overwrites, never deletes)
allowed_dependencies: [src/xcron/domain, src/xcron/shared]
cross_module_flows:
  - callee: manifest, reconciliation, operations
  - the resolved ProjectWorkspace names the workspace config file that
    src/xcron/configuration layers over the user config
failure_behavior: >
  A missing or non-directory root raises WorkspaceResolutionError; an unknown
  platform raises UnsupportedPlatformError. An unreadable marker raises
  MalformedMarkerError and a future schema raises UnsupportedMarkerSchemaError,
  but an absent marker is only a warning for this release. No path function
  creates directories except ensure_runtime_dirs and initialize_workspace.
isolation_level: 1 (surface plus owned implementation)
verification:
  - tests/modules/workspace/ (module-owned lane)
  - tests/architecture/ (Import Linter contracts plus the AST scanner)
```

```yaml
module: xcron.capabilities.manifest
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
allowed_dependencies: [workspace.api, src/xcron/domain, src/xcron/shared]
cross_module_flows:
  - callee: jobs, reconciliation
failure_behavior: >
  Every failure is a ManifestLoadError or ManifestEditError subclass; a
  rejected edit is written atomically or not at all, never partially.
isolation_level: 1 (surface plus owned implementation)
verification:
  - tests/modules/manifest/ (module-owned lane)
  - tests/architecture/ (Import Linter contracts plus the AST scanner)
```

```yaml
module: xcron.configuration
hidden_decision: >
  How a Settings value is composed: which layers exist, in what order they win,
  and that xcfg is the machinery underneath.
public_entrypoints: [configuration.api, configuration.contracts]
owned_state: []          # composes files, writes none
owned_resources:
  - resources/config/config.default.yaml (packaged base layer)
  - the XCRON_CONFIG and XCRON_ENV selectors
  - the settings environment variables (ENV_SETTINGS)
allowed_dependencies: [xcfg, pydantic, stdlib]
cross_module_flows:
  - src/xcron/runtime/composition.py is the only caller; capabilities receive the
    resolved Settings as constructor values, never by importing this module
failure_behavior: >
  Every xcfg failure is re-raised as ConfigurationError, so no dependency
  exception escapes the surface. Unknown keys and wrong types are rejected
  (extra="forbid") rather than silently ignored.
isolation_level: 1 (leaf; surface plus owned implementation)
verification:
  - tests/modules/configuration/ (module-owned lane)
  - tests/architecture/ (Import Linter contracts plus the AST scanner)
```

```yaml
module: xcron.capabilities.jobs
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
  - src/xcron/domain, src/xcron/shared
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
  - tests/architecture/ (Import Linter contracts plus the AST scanner)
```

```yaml
module: xcron.capabilities.reconciliation
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
  - src/xcron/domain, src/xcron/shared
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
  - tests/architecture/ (Import Linter contracts plus the AST scanner)
```

```yaml
module: xcron.capabilities.operations
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
  - src/xcron/shared
cross_module_flows:
  - resolves the project through reconciliation.api.validate_project
  - caller: reconciliation, via the OutcomeRecorder adapter in src/xcron/runtime
failure_behavior: >
  Clearing defaults to dry_run=true; an unresolvable project returns
  valid=false with the underlying validation attached. record_outcome never
  raises, so a broken metrics file cannot fail its caller.
isolation_level: 1 (surface plus sole ownership of the metrics state family)
verification:
  - tests/modules/operations/ (module-owned lane)
  - tests/test_cli_logs.py
  - tests/architecture/ (Import Linter contracts plus the AST scanner)
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

## Planes

Capability modules say *who owns a decision*. Planes say *what happens when
something is down*, which is a different question and cuts across the modules.
xcron has three, and the reason the distinction earns its keep is the first row
of the degraded table below: the data plane is the host scheduler, so it keeps
running when everything xcron owns is gone.

**System boundary.** xcron converges a project's schedule manifest onto a native
OS scheduler (`launchd`, `cron`), reversibly and with visible drift.

**Last-known-good safety window.** The deployed native artifacts — plist,
managed crontab block, and wrapper scripts. They keep executing indefinitely
with xcron uninstalled. `project-state.json` is only xcron's *record* of the
last successful convergence; it has no expiry, and `status` exists precisely
because that record can be wrong.

| Plane | What it does | Trigger | Authoritative state, and its sole writer | Authority it needs |
| --- | --- | --- | --- | --- |
| Data | scheduled jobs execute through the generated wrapper | every scheduler firing | wrapper stdout/stderr/event logs — written by the scheduled process, read and cleared by `operations` | the user's own account, via the host scheduler |
| Control | `validate`, `plan`, `status`, `apply`, `prune`, `inspect` | operator-initiated | `project-state.json`, wrappers, plist / managed crontab block — written by `reconciliation` | user-level `launchctl` / `crontab`; never root |
| Management | `init`, `jobs` edits, `hooks`, `metrics`, configuration | operator or lifecycle | manifest YAML (`manifest`), workspace layout and marker (`workspace`), metrics store (`operations`), hook files (`agent_hooks`) | filesystem write access to the project and `~/.xcron` |

### Cross-plane contracts

| Contract | Producer | Consumer | Form | Freshness | Compatibility rule |
| --- | --- | --- | --- | --- | --- |
| `NormalizedManifest` | `manifest` (management) | `reconciliation` (control) | in-process typed value | per invocation | additive fields only; unknown YAML keys rejected at load |
| `project-state.json` | `reconciliation.apply` | `reconciliation.plan` | durable JSON | may be arbitrarily stale — `status` is the authority | literal key set pinned; every non-required key must stay optional |
| native artifacts (plist, crontab block, wrapper) | `reconciliation` adapters | host scheduler (data) | files carrying xcron ownership markers | until the next `apply` or `prune` | ownership markers must never change meaning |
| wrapper log and event files | the scheduled process (data) | `operations` (management) | line-oriented text / JSONL | read-only tail | the reader tolerates truncation and partial lines |
| outcome summary | `reconciliation` (control) | `operations` (management) | the `OutcomeRecorder` port | per action | a bounded counter summary, never per-job callbacks |
| workspace `marker.toml` | `workspace` (management) | every plane | TOML, `schema = 1` | until an explicit migration | an unsupported version refuses with a recovery hint |

`project-state.json` still has no explicit `schema` discriminator. The durable
format is instead pinned from outside by
`tests/modules/reconciliation/test_durable_state_format.py`, which asserts the
literal key set and separately proves a document holding only the required keys
still loads. That covers today's compatibility question — an older file must
keep loading — but it does not answer the future one, which is how a reader
recognizes a format it is too old to understand. Adding the discriminator is
still open.

### Degraded behaviour

Every row is drilled. `tests/degraded/` holds the cross-cutting drills; two
rows are drilled inside the lane of the module that owns the state.

| Failure | What continues | What stops, and how | Recovery | Drilled by |
| --- | --- | --- | --- | --- |
| xcron uninstalled or broken | **everything already deployed** — this is the property the whole design exists to protect | nothing in the data plane | reinstall; `status` reveals drift | `test_a_deployed_job_still_runs_when_xcron_is_not_there`, `test_the_deployed_artifacts_never_call_back_into_xcron` |
| `project-state.json` missing or corrupt | `status` and `apply`, which ask the scheduler rather than the record | `plan` reports every job as a create — visibly wrong, never silently empty | run `status`, then `apply` | `test_losing_derived_state_degrades_visibly_not_silently`, `test_a_corrupt_state_document_does_not_take_the_project_down` |
| host scheduler unavailable | `validate`, `plan`, `jobs` edits | `apply` raises; no durable record is written and no scheduler entry changes | retry once the scheduler responds | `test_a_failing_scheduler_write_leaves_the_durable_record_untouched`, `tests/modules/reconciliation/test_fake_backend_lane.py` |
| manifest invalid | `status`, `logs`, `metrics` | `plan` and `apply` refuse before touching artifacts | fix the manifest; `validate` | `tests/modules/reconciliation/test_validation.py` |
| workspace marker missing or untrustworthy | one release: missing warns and proceeds | a malformed or unsupported marker refuses with a recovery hint from day one | `xcron init` | `tests/modules/workspace/test_marker.py` |
| metrics store unreadable | every action | nothing — the store discards unreadable content and heals on the next write | `metrics reset` | `test_a_corrupt_metrics_store_never_blocks_an_action`, `test_a_metrics_directory_that_cannot_be_written_never_blocks_an_action` |

One correction the drills forced. The third row used to claim "no partial
artifact write". That is not what happens: wrapper scripts are rendered and
written *before* the crontab, because the crontab entries have to reference
their paths. What is actually true — and what the drill asserts — is that no
scheduler entry changes and no durable record is written, so the orphaned
wrappers are inert files that the next successful `apply` overwrites.

**Physical plane separation is not justified.** xcron has one process, one
user, one release cadence, and one failure domain. The separation that matters
is already there and was earned by design rather than by packaging: the data
plane *is* the host scheduler.

## Channel exposure and parity

Two channels: the typed `Xcron` SDK and the Typer CLI. REST and Web are absent
by decision, not by omission — xcron is a local, single-user tool, and the
house standard says to add HTTP when remote, multi-user, or multi-language use
is real.

| Capability action | SDK | CLI | Plane | Note |
| --- | --- | --- | --- | --- |
| `workspace` initialize | `home.initialize` | `init` | management | opens an *unscoped* client; it creates the workspace it would otherwise have to resolve |
| `manifest` load / validate | internal | reached via `validate` | management | not a public capability surface |
| `jobs` list / show | yes | yes | management | — |
| `jobs` add / update / enable / disable / remove | yes | yes | management | edits YAML only; never touches the scheduler |
| `reconciliation` validate | yes | yes | control | — |
| `reconciliation` plan | yes | yes | control | reads the record; never mutates |
| `reconciliation` status | yes | yes | control | queries the real scheduler |
| `reconciliation` inspect | yes | yes | control | `--full` expansion is CLI-only presentation |
| `reconciliation` apply | yes | yes | control | the only converging mutation |
| `reconciliation` prune | yes | yes | control | removes xcron-owned artifacts only |
| `operations` logs list / clear | yes | yes | data evidence / management | `clear` never touches paths outside the workspace layout |
| `operations` metrics show / reset | yes | yes | management | unscoped, like `init` |
| `agent_hooks` install / status / repair | yes | yes | management | repository-local files only |
| `agent_hooks` session end | `hooks.session_end` | **no** | management | agent-invoked through the SDK; there is no CLI verb, and no session-*start* operation exists |

A channel is a projection: it decides how a result is rendered, never what was
asked for. `tests/parity/test_channel_parity.py` holds that to account. For
twelve CLI/SDK pairs a spy wraps the use case at the seam the SDK calls it
through, the same operation runs once per channel, and the two recorded calls
must be equal — composed collaborators compared by type, everything a caller
can state compared by value. Three pairs state an option explicitly rather than
relying on defaults, because a parity check that only compares defaults is a
check that both channels agree about nothing: a planted "the CLI drops the
`--job` filter" defect passed the first version of the lane cleanly.

## Migration compatibility

None. `xcron.actions`, `xcron.services`, `xcron.infra`, and
`xcron_resources` have all been deleted; the actions facade was the last one and
was time-boxed from the day it was created. Their contents moved to the module
that owns each decision:

| Former path | New owner |
| --- | --- |
| `services.observability`, `services.logging_config` | `src/xcron/shared/` |
| `services.config_loader` (home, project root) | `workspace.api` |
| `capabilities.home` (starter manifest, first run) | `workspace.api` |
| `xcron/channels/cli/common.py` env readers (`env_path`, `env_flag`, ...) | `configuration.api` |
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

`xcron` deliberately ships as one root Python distribution with one import
root. The root `pyproject.toml` maps the empty package prefix to `src/`, so
`src/xcron/channels/cli/typer_app.py` is `xcron.channels.cli.typer_app` and the
console script targets `xcron.channels.cli.typer_app:run`. The channel does not
have a second `pyproject.toml`. Packaged data ships inside the module that
reads it, so there is no second top-level distribution package.

The import root used to be two names, one per repository directory — `libs/`
and `apps/`. That made the layout the public API: moving a file between them was
a breaking change for anyone importing it, and the two names implied two
distributions where there was always one. Both survived one release as aliases,
implemented as a meta-path finder installed ahead of `PathFinder` so that each
old dotted name resolved to the *same module object* rather than to a second
copy of it — module-level state, `isinstance`, and `monkeypatch.setattr` all
behaved identically under either name, and importing either root emitted a
`DeprecationWarning`. That window has closed and the shims are deleted. What
remains is a check rather than a mechanism: `pyproject.toml` forbids the old
roots, `tests/architecture/test_layer_boundaries.py` asserts their directories
stay gone, and `scripts/verify-wheel.sh` proves an installed wheel no longer
answers to them.

One distribution, two dependency sets. The mandatory set is what the library
half needs — `PyYAML`, `jsonschema`, `pydantic`, `structlog`, and `xcfg` — and
the terminal renderers (`typer`, `rich`, `python-toon`) live in a `cli` extra.
An embedder installs `xcron` and gets the SDK; anyone who wants the command
installs `xcron[cli]`. This is a dependency boundary, not a distribution
boundary: the split is only meaningful because no file below
`xcron.channels` may import a renderer, which the architecture tests enforce.
The package carries one `py.typed` marker at its root, so an embedder's type
checker sees the annotations that are already there, in every subpackage.

`tests/test_packaging.py` reads `pyproject.toml` as data and compares it with
the tree: the declared package list must equal the discovered one, every
packaged resource pattern must match a real file, and the mandatory dependency
set must stay disjoint from the renderers. `scripts/verify-wheel.sh` covers what
static reading cannot — it builds, installs the plain wheel into a clean
environment and proves no renderer is present, then installs `xcron[cli]` and
runs the console script.

The CLI channel, native SDK, capability implementation, and packaged runtime
resources share one version, dependency graph, and release lifecycle. Splitting
the CLI into a separate distribution would introduce a cross-distribution
dependency on the SDK/capabilities and a second release/install boundary
without providing independent ownership, dependencies, or release cadence.
Reconsider the split only if one of those operational boundaries becomes real.

Older xpack versions warned about the root entry point and missing app-local
metadata. Those warnings are accepted when using such a version because the
single-distribution mapping is intentional, not accidental. Current xpack
recognizes both the scoped root entry point and the `src/` package mapping as
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
- capability-owned workspace, manifest, reconciliation, jobs, operations, and
  agent-hook use cases, each reached only through its own `api`
- a marked workspace (`marker.toml`) resolved by walking up from the working
  directory, and layered settings composed once in the composition root
- explicit `cron`/`launchd` scheduler registry and backend-neutral deployment
  and scheduler-inspection contracts
- embeddable `Xcron.open(...)` SDK with grouped schedules, jobs, operations,
  hooks, and home APIs
- CLI thin shells that call the SDK rather than embedding backend logic
- Typer-based command declaration and command grouping
- Pydantic response envelopes plus mapper helpers under `xcron/channels/cli/`
- unified machine/human output rendering:
  - TOON for machine-facing output
  - Rich-backed help and human-facing presentation paths
- resource-backed runtime help under `src/xcron/channels/cli/resources/help/`
- repo-local Codex and Claude hook adapters plus install/status/repair flows

Verification model:

- deterministic core lane is `./scripts/verify-core.sh`
- that lane runs `uv run lint-imports` and then `uv run pytest`
- the two gates say different things. Import Linter states the dependency graph
  and checks it; the AST scanner in `tests/architecture/` checks what a graph
  cannot express — *which file inside a module* an import reached for, and which
  files may name `os.environ`
- `tests/parity/` asserts that the CLI and the SDK reach the same use case with
  the same inputs, which no single-channel test can see
- `./scripts/verify-wheel.sh` is the installed-distribution lane (network)
- default core verification stays safe and does not mutate the host scheduler
- host-gated `launchd` integration exists for real macOS verification
- Docker/Colima-gated cron integration exists for real Linux cron verification

See `docs/dev/go-rewrite-contract.md` for the external behavior that should
remain stable in the later Go implementation.
