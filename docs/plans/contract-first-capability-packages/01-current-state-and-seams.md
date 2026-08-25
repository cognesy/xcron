# Current state and extraction seams

<!-- markdownlint-disable MD013 -->

## What is already strong

`docs/dev/architecture.md` establishes real decision ownership inside one
wheel. The current implementation has clear public `api.py`/`contracts.py`
surfaces, imported only through the intended edges:

```text
CLI -> Xcron SDK -> capability api/contracts -> capability internals
runtime -> configuration once -> resolved Settings value
runtime -> scheduler registry and metrics OutcomeRecorder adapter
```

The import linter, architecture scanner, CLI/SDK parity tests, degraded drills,
and clean-wheel verification already protect behavior that must survive the
move. The migration starts from those protections rather than replacing them.

## Current ownership map

| Current module | Hidden decision and owned assets | Public seam today | Target provider package |
| --- | --- | --- | --- |
| `capabilities/workspace` | Workspace resolution, `marker.toml`, home/state paths, starter manifest. | `workspace.api`, `workspace.contracts` | `xcron-capability-workspace-local` |
| `capabilities/manifest` | YAML discovery, schema validation, hashes, atomic formatting-preserving edits, schedule schema resource. | `manifest.api`, `manifest.contracts` | `xcron-capability-manifest-yaml` |
| `capabilities/reconciliation` | Plan/apply/status/prune/inspect, wrapper rendering, derived state, scheduler port, native adapters. | `reconciliation.api`, `reconciliation.contracts` | `xcron-capability-scheduler-native` |
| `capabilities/jobs` | Job mutation policy over a manifest, typed add/update inputs. | `jobs.api`, `jobs.contracts` | `xcron-capability-jobs-manifest` |
| `capabilities/operations` | Wrapper-log access and metrics persistence/outcome recording. | `operations.api`, `operations.contracts` | `xcron-capability-logs-local` and `xcron-capability-metrics-local` |
| `capabilities/agent_hooks` | Codex/Claude hook file formats and lifecycle. | `agent_hooks.api`, `agent_hooks.contracts` | `xcron-capability-agent-hooks-local` |
| `configuration` | xcfg layer ordering, config resource, environment mapping. | `configuration.api`, `configuration.contracts` | `xcron-capability-settings-xcfg` |
| `shared` | Structlog wiring and logging config resource. | implicit leaf API | `xcron-capability-observability-structlog` |
| `domain` | Schedule models, normalization, stable IDs. | direct shared leaf | `xcron-contracts` |
| `runtime` | Scope, settings, concrete scheduler registry, metrics adapter. | `XcronRuntime` | generic host in kernel; typed composition in SDK; concrete providers external |
| `sdk` | Typed facade groups and lifecycle. | `Xcron` | `xcron-sdk` |
| `channels/cli` | Typer parsing, output contracts, renderers and help resources. | console script | `xcron-cli` |

## The concrete coupling to remove

`src/xcron/runtime/composition.py` directly imports:

- `operations.api.record_outcome`;
- `reconciliation.api.default_scheduler_registry` and
  `reconciliation.contracts.OutcomeRecorder`;
- `workspace.api.resolve_state_root` and `resolve_workspace`;
- `configuration.api.load_settings`.

Those imports mean adding or substituting one provider edits central code. The
target SDK composition may name stable port protocols such as `WorkspacePort`,
`SettingsPort`, and `ScheduleControlPort`, but it cannot name `*_local`,
`*_yaml`, `xcfg`, `cron`, `launchd`, or structlog implementation modules.

Similarly, `sdk/client.py` currently constructs fixed `SchedulesAPI`, `JobsAPI`,
`OperationsAPI`, `HooksAPI`, and `HomeAPI` objects over a concrete runtime.
The target retains those ergonomic groups but each resolves only its declared
port from an immutable host. A package absent from a lean install fails when
that group is reached, not when the client is imported.

## Extraction order is driven by dependencies

```text
kernel
  <- contracts
      <- testing harness
      <- settings-xcfg, workspace-local, observability-structlog
      <- manifest-yaml
      <- scheduler-native <- jobs-manifest, logs-local, metrics-local
      <- agent-hooks-local
      <- sdk <- cli
      <- xcron aggregate meta distribution
```

`scheduler-native` depends on workspace and manifest ports, not on an
implementation package. `jobs-manifest` depends on manifest and schedule
control ports. Metrics remain optional from the scheduler’s perspective: the
kernel supplies a no-op event/outcome sink, so a broken or absent management
provider cannot prevent native reconciliation.

## Seam decisions

### Keep the semantic schedule model stable

`ProjectManifest`, `JobDefinition`, `ScheduleDefinition`, normalized identities,
and job-mutation request models become contract values. They are not mechanism
implementations. Existing Pydantic validation and the literal YAML schema move
with the manifest provider; a second manifest provider must honor the same
contract and compatibility fixtures before it can be selected.

### Split operations by independently replaceable decision

The current `operations` module owns two unrelated mechanisms: wrapper-log
files and a metrics counter store. They become separate provider IDs so a
future metrics backend cannot accidentally own log-retention semantics. Their
SDK group remains `operations` for compatibility and composes both ports.

### Keep scheduler adapters together initially

`launchd`, `cron`, wrapper rendering, ownership markers, and derived-state
transaction rules form one control-plane compatibility unit. Splitting launchd
and cron into competing provider wheels before the shared native artifact
contract is independently proven would create a false seam. The first provider
is therefore `scheduler:native`; later backends are an explicit second phase.

### Do not put product policy in the kernel

The kernel validates generic descriptor shape, API compatibility, dependency
DAGs, duplicate claims, host lifecycle, asset containment, and capability
selection. It must not understand `project.id`, YAML, `launchctl`, crontab,
metrics, Codex, Claude, or CLI output.
