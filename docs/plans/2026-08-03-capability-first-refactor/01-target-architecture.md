# Target architecture

## Dependency model

```text
apps/cli command modules
        |
        v
xcron_libs.sdk.Xcron  <----- xcron_libs.runtime.Runtime
        |                         |
        v                         +--> explicit scheduler registry
capability APIs/actions                   |
        |                                  v
        +--> domain + declared ports <-- cron / launchd adapters
```

`runtime` is composition only: it resolves the project options once, constructs
the built-in scheduler registry, and wires capability actions. It owns no
product policy, output rendering, or hidden global singleton.

The SDK is the stable, typed, in-process channel. The CLI translates Typer
inputs to SDK calls and maps results through existing `Output`, contracts, and
mappers. Neither the SDK nor capability code imports `xcron_cli`.

## Capability map

```text
xcron_libs/
  domain/                         canonical models, normalization, diffing
  capabilities/
    reconciliation/               validate, plan, status, apply, inspect, prune
      contracts.py                backend-neutral deployment/inspection port
      planning.py, status.py, ... focused use-case orchestration
      scheduler_registry.py       explicit first-party selection
    jobs/                         manifest read/edit operations
    operations/                   logs and metrics
    agent_hooks/                  hook setup/session operations
  runtime/                        composition and project option resolution
  sdk/                            Xcron root and grouped typed APIs
  services/                       retained low-level mechanisms during migration
    backends/                     cron/launchd adapter implementations
```

The first implementation may retain existing low-level services in place.
Physical moves must follow real ownership, not merely rename every file.
`xcron_libs.actions` becomes a documented compatibility facade delegating to
the capability implementations, so current test and external imports keep
working while the SDK becomes the canonical channel surface.

## Scheduler port

The reconciliation capability owns a small typed provider contract and the
backend-neutral deployment input. It contains only domain data required for an
adapter to render, inspect, apply, and prune artifacts; it does not contain a
`ValidateProjectResult`, Typer context, output response, or mapper type.

Each first-party backend implements operations equivalent to:

- collect actual project state;
- inspect owned artifacts;
- apply a validated deployment plan;
- prune owned artifacts; and
- report schedule constraints for planning.

`SchedulerRegistry` maps the stable backend identities `launchd` and `cron` to
those adapters explicitly. It rejects an unknown identity deterministically.
Adding systemd later means adding an adapter and registration at the runtime
composition root, with no new generic extension framework.

## State and plane ownership

| State / effect | Owner | Plane |
| --- | --- | --- |
| YAML schedule manifest | jobs capability / manifest editor | management |
| normalized manifest, job identity, plan diff | domain | shared contracts |
| derived `project-state.json` and generated wrappers | reconciliation backend | control |
| native plist or managed crontab block | reconciliation backend | control |
| wrapper stdout/stderr/events | scheduled process; operations reads/clears | data/runtime |
| metrics and hook configuration | operations / agent-hooks capability | management |

No capability silently writes another owner's state. `plan` continues to use
derived state, `status` actual state, and `apply` actual state as baseline.

## SDK contract

`from xcron_libs import Xcron` exposes `Xcron.open(...)` with the same explicit
project/backend/test-override inputs already accepted by actions. It provides:

- `schedules`: validate, plan, status, apply, inspect, prune;
- `jobs`: list, show, add, update, enable, disable, remove;
- `operations`: list/clear logs and show/reset metrics; and
- `hooks`: install, status, repair, and session helpers where those existing
  actions are available.

The client is a context manager with idempotent `close()` and a stable
use-after-close error. It owns only resources it constructs; the initial
runtime has no persistent scheduler connection to close. API calls return
typed capability results; legacy action paths re-export those types during the
compatibility period. Output models, TOON, JSON, tmux, and Typer errors remain
CLI-only projections.

## Guardrails

Architecture tests must enforce at least:

- backend modules never import `xcron_libs.actions` or `xcron_libs.sdk`;
- `domain` imports no capability, runtime, adapter, or CLI module;
- capabilities import no `xcron_cli` or channel renderer;
- SDK imports no `xcron_cli`, Typer, Rich, TOON, JSON, or tmux renderer;
- CLI command modules open/use `Xcron` rather than import action
  implementations directly; and
- the scheduler registry has an explicit, tested duplicate/unknown-backend
  policy.

The test may be a small AST/import assertion initially. It should test the
actual forbidden imports, not infer architecture from directories alone.
