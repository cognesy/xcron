# Target architecture

## Naming note

The house standard uses `modules/` in `MODULE-ISOLATION.md` and
`capabilities/` in `REFERENCE-STRUCTURE.md` for the same construct. xcron keeps
`capabilities/`, which is already established in the code, the architecture
document, and the previous plan. The isolation rules apply unchanged; only the
directory noun differs.

## Target layout

```text
apps/cli/                        CLI channel — owns every projection
  app.py                         Typer root, callback, version, bootstrap errors
  commands/
    schedules.py                 validate, plan, status, apply, prune, inspect
    jobs.py                      list, show, add, update, enable, disable, remove
    logs.py                      list, clear
    metrics.py                   show, reset
    hooks.py                     install, status, repair, session-start/end
    home.py                      init
  client.py                      opens Xcron from resolved CLI options
  output.py                      Output class, field selection, exit codes
  contracts.py                   per-command CommandContract          (was libs/services/cli_contracts.py)
  responses.py                   response models                      (was libs/services/cli_responses.py)
  mappers.py                     capability result -> response        (was libs/services/cli_mappers.py)
  presenters/
    axi.py                       (was libs/services/axi_presenter.py)
    toon.py                      (was libs/services/toon_renderer.py)
    tmux.py                      (was libs/services/tmux_renderer.py)
    help.py                      (was libs/services/help_renderer.py)
  resources/help/*.md            authored runtime help, CLI-owned

libs/
  shared/                        strict leaf: no workflows, no persistence
    observability.py             get_logger, instrument_action, redaction
    logging_config.py            structlog configuration model
    resources/logging/default.yaml

  domain/                        shared leaf: manifest value types only
    models.py                    ProjectManifest, JobDefinition, NormalizedJob, ...
    normalization.py             normalize_job, normalize_manifest

  configuration/                 app-owned XCFG adapter
    settings.py                  strict Settings (extra="forbid")
    loader.py                    the only module that imports XCFG or reads env
    errors.py                    ConfigurationError

  capabilities/
    workspace/                   xcron home + project workspace identity and paths
      api.py contracts.py
      marker.py resolver.py paths.py initializer.py
    manifest/                    on-disk schedule manifest format
      api.py contracts.py
      _loader.py _schema.py _editor.py _hashes.py
      resources/schemas/schedules.schema.yaml
    jobs/                        job-level use cases over the manifest
      api.py contracts.py actions.py
    reconciliation/              desired -> native scheduler convergence
      api.py contracts.py
      domain.py                  plan/state/status diffing (was libs/domain/diffing.py)
      ports.py                   SchedulerBackend, OutcomeRecorder
      planning.py status.py apply.py prune.py inspect.py cron_policy.py
      registry.py                explicit first-party backend selection
      state_store.py             project-state.json read/write
      wrapper.py                 wrapper script rendering
      adapters/
        cron.py launchd.py process.py
    operations/                  logs and metrics evidence
      api.py contracts.py logs.py metrics.py metrics_store.py
    agent_hooks/                 already Level 1; unchanged
      api.py contracts.py _codex.py _claude.py _paths.py

  runtime/                       composition root only
  sdk/                           Xcron and grouped typed APIs

tests/
  modules/{workspace,manifest,jobs,reconciliation,operations,agent_hooks}/
  channels/{cli,sdk}/
  contracts/                     durable-format compatibility
  parity/                        SDK/CLI equivalence
  architecture/                  import contracts and planted negatives
  integration/                   explicit-only host harnesses (unchanged)
```

`libs/services/` and `libs/infra/` cease to exist. `libs/actions/` is deleted
in Phase 6.

## What moves where, and why

| Current module | New owner | Reason |
| --- | --- | --- |
| `cli_contracts`, `cli_responses`, `cli_mappers` | `apps/cli/` | Wire/operator encoding is a channel responsibility. |
| `axi_presenter`, `toon_renderer`, `tmux_renderer`, `help_renderer` | `apps/cli/presenters/` | Same. |
| `resources/help/` | `apps/cli/resources/help/` | Authored CLI help is CLI-owned. |
| `backends/cron_service`, `backends/launchd_service` | `reconciliation/adapters/` | An adapter belongs with the port it implements. |
| `wrapper_renderer` | `reconciliation/wrapper.py` | Wrappers are reconciliation artifacts. |
| `state_store` | `reconciliation/state_store.py` | `project-state.json` is the control-plane snapshot reconciliation owns. |
| `observability.run_logged_subprocess`, `check_output_logged` | `reconciliation/adapters/process.py` | Only the two scheduler adapters call them. |
| `observability` (logging, `instrument_action`, redaction) | `libs/shared/` | Six real owners; stable; no workflow. |
| `logging_config` | `libs/shared/` | Supports the above. |
| `logging_paths` | `workspace/paths.py` | On-disk layout is workspace knowledge, consumed by reconciliation and operations. |
| `config_loader.resolve_xcron_home`, `resolve_project_root` | `workspace/resolver.py` | Workspace identity and root precedence. |
| `config_loader` manifest loading/parsing | `manifest/_loader.py` | Manifest format. |
| `schema_validator` | `manifest/_schema.py` | Manifest format. |
| `manifest_editor` | `manifest/_editor.py` | Manifest format. |
| `hash_service` | `manifest/_hashes.py` | Manifest identity hashing. |
| `resources/schemas/` | `manifest/resources/schemas/` | Module-owned resource. |
| `metrics` (`MetricsService`) | `operations/metrics_store.py` | Single writer for the metrics state family. |
| `domain/diffing.py` | `reconciliation/domain.py` | Every consumer is reconciliation-owned after the move. |
| `capabilities/home/` | `workspace/initializer.py` | `init_home` is workspace initialization; a 63-line module is not an independent decision. |
| `libs/infra/` | deleted | Dead: one empty file, imported by nothing. |
| `libs/actions/` | deleted | Time-boxed compatibility shim, expiring in Phase 6. |

`app.home.init()` stays as the SDK group name even though the module is
`workspace`. Public names follow user vocabulary; module names follow
ownership.

## Module cards

### workspace

```yaml
module: workspace
hidden_decision: what an xcron workspace is, where its root is, and how its
  on-disk layout is arranged
public_entrypoints:
  - xcron_libs.capabilities.workspace.api
  - xcron_libs.capabilities.workspace.contracts
owned_state:
  - <project>/.xcron/marker.toml
  - ~/.xcron/ (home root, state, logs, wrappers, metrics directory layout)
owned_resources:
  - starter manifest template
allowed_dependencies:
  - xcron_libs.domain
  - xcron_libs.shared.observability
cross_module_flows:
  - caller: every capability and the runtime
    contract: XcronHome, ProjectWorkspace typed paths
failure_behavior: WorkspaceNotFoundError, InvalidWorkspaceMarkerError,
  UnsupportedWorkspaceSchemaError; no partial initialization
isolation_level: 1
verification:
  - root-resolution precedence tests
  - marker round-trip and unsupported-version refusal
  - two workspaces in one process
  - state-ownership test for path allocation
```

### manifest

```yaml
module: manifest
hidden_decision: the on-disk schedule manifest format — discovery, parsing,
  schema and semantic validation, editing, and identity hashing
public_entrypoints:
  - xcron_libs.capabilities.manifest.api
  - xcron_libs.capabilities.manifest.contracts
owned_state:
  - <project>/resources/schedules/*.yaml
owned_resources:
  - resources/schemas/schedules.schema.yaml
allowed_dependencies:
  - xcron_libs.domain
  - xcron_libs.capabilities.workspace.api
  - xcron_libs.shared.observability
cross_module_flows:
  - caller: jobs, reconciliation, workspace initializer
    contract: LoadedManifest, ValidationMessage, ManifestHashes
failure_behavior: ManifestNotFoundError, ManifestParseError,
  ManifestEditValidationError; edits are atomic or refused
isolation_level: 1
verification:
  - module test lane
  - schema/semantic validation cases
  - atomic edit and round-trip tests
  - durable-format compatibility test
```

### jobs

```yaml
module: jobs
hidden_decision: job-level use cases and their result semantics over a manifest
public_entrypoints:
  - xcron_libs.capabilities.jobs.api
  - xcron_libs.capabilities.jobs.contracts
owned_state: []          # mutates manifest state only through manifest.api
owned_resources: []
allowed_dependencies:
  - xcron_libs.domain
  - xcron_libs.capabilities.manifest.api
  - xcron_libs.shared.observability
cross_module_flows:
  - caller: sdk.jobs.JobsAPI
    contract: JobActionResult
failure_behavior: typed invalid results; never a partial manifest write
isolation_level: 1
verification:
  - module test lane
  - no direct filesystem write outside manifest.api
```

### reconciliation

```yaml
module: reconciliation
hidden_decision: how desired schedules converge to native launchd/cron state,
  and what counts as planned, applied, or drifted
public_entrypoints:
  - xcron_libs.capabilities.reconciliation.api
  - xcron_libs.capabilities.reconciliation.contracts
owned_state:
  - ~/.xcron/<project>/project-state.json
  - generated wrapper scripts
  - managed crontab block / launchd plist owned by xcron
owned_resources: []
allowed_dependencies:
  - xcron_libs.domain
  - xcron_libs.capabilities.workspace.api
  - xcron_libs.capabilities.manifest.api
  - xcron_libs.shared.observability
cross_module_flows:
  - caller: sdk.schedules.SchedulesAPI
    contract: ProjectPlan, StatusEntry, ApplyResult, SchedulerInspection
  - callee: OutcomeRecorder port
    contract: bounded outcome summary, supplied by composition
failure_behavior: typed backend errors; never a partial artifact write without
  a recorded state transition
isolation_level: 1
verification:
  - module test lane with a fake SchedulerBackend
  - registry duplicate/unknown policy tests
  - state-ownership test: no sibling writes project-state.json
  - explicit-only host integration harnesses (unchanged)
```

### operations

```yaml
module: operations
hidden_decision: how runtime evidence — wrapper logs and counters — is stored,
  read, and cleared
public_entrypoints:
  - xcron_libs.capabilities.operations.api
  - xcron_libs.capabilities.operations.contracts
owned_state:
  - ~/.xcron/metrics/metrics.json
  - wrapper log and event files (read/clear only; the scheduled process writes)
owned_resources: []
allowed_dependencies:
  - xcron_libs.capabilities.workspace.api
  - xcron_libs.shared.observability
cross_module_flows:
  - caller: sdk.operations.OperationsAPI
    contract: LogsListResult, LogsClearResult, MetricsResult
  - caller: reconciliation, via the OutcomeRecorder adapter
    contract: record_outcome(summary) public command
failure_behavior: typed errors; a missing metrics file reads as empty, never
  as a crash
isolation_level: 1
verification:
  - module test lane
  - sole-writer test for metrics.json
  - log clear safety test (never deletes outside owned paths)
```

### agent_hooks

Unchanged from `docs/dev/plans/agent-hooks-level-1-module.md`. It is the
reference implementation for every card above.

## Non-module packages

| Package | Rule it must satisfy |
| --- | --- |
| `libs/shared/` | Strict leaf. Imports only the standard library and `libs/domain`. No workflow, no persistence, no capability results, no service locator. Adding a module here requires a recorded decision. |
| `libs/domain/` | Shared leaf of manifest value types and normalization. It must not accumulate per-capability results; `diffing.py` leaving is the test of that rule. |
| `libs/configuration/` | The only place that imports XCFG or reads `os.environ` for settings. Exposes a validated `Settings`. |
| `libs/runtime/` | Composition only. May know concrete modules and adapters. Contains no product policy. |
| `libs/sdk/` | Typed in-process channel. Imports module public APIs only, never internals. Imports no Typer, Rich, TOON, or CLI module. |
| `apps/cli/` | Channel. Owns argv, flags, formats, envelopes, exit codes, and every projection. No business rules. |

## Dependency law

```text
apps/cli ──► libs/sdk ──► libs/runtime ──► module public APIs
                                              │
                                              ├─► module actions ─► ports ─► module domain
                                              └─► module adapters

module A ──X──► module B implementation
module A ─────► A-owned port ◄─── integration adapter ───► module B public API

every module ──► libs/domain, libs/shared      (leaves only)
libs/configuration ──► XCFG, os.environ        (nobody else may)
```

Declared contract dependencies — the only permitted cross-module import edges:

```text
manifest        -> workspace.api
jobs            -> manifest.api
reconciliation  -> workspace.api, manifest.api
operations      -> workspace.api
agent_hooks     -> (none)
```

`reconciliation -> operations` is deliberately absent. Reconciliation declares
an `OutcomeRecorder` port; `libs/runtime/composition.py` supplies an adapter
that calls `operations.api`. This removes the current shared-`MetricsService`
write path, keeps reconciliation testable without operations, and gives the
plane map one typed cross-plane contract instead of an implicit shared file.

## Public surfaces

Every module follows the `agent_hooks` shape:

- `__init__.py` is empty and aggregates nothing;
- `api.py` holds the callable surface;
- `contracts.py` holds closed request/result models and stable errors;
- everything else is private, `_`-prefixed where the module is flat, or under
  a private subpackage where the module is large;
- outside code imports only `api` and `contracts`, in any of the four Python
  import forms.

Contracts use frozen Pydantic models with `extra="forbid"`. Paths cross module
boundaries as strings where the module already does so; the SDK may adapt back
to `Path` to preserve its current public return types.

## What does not change

- Every CLI command, flag, output format, envelope, field-selection rule, and
  exit code.
- The schedule language, YAML schema, manifest location, and artifact
  ownership markers.
- `project-state.json` semantics and the plan/status/apply sources of truth.
- The `Xcron` SDK's public method names and return types.
- The Go-rewrite contract in `docs/dev/go-rewrite-contract.md`.
- Explicit-only host integration harnesses.
