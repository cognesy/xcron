# Current-state evidence

Observed on 2026-08-03, at commit `e5bdadc` ("Isolate agent hooks as a Level 1
module"), on a clean working tree.

All figures below are measured, not estimated. The commands are recorded so the
evidence can be regenerated after each phase.

## How the evidence was produced

```sh
rg --files -g '*.py' libs apps resources          # module inventory
rg -n '^\s*(from|import)\s+xcron[_a-z.]*' libs apps  # internal import graph
ast-grep outline libs --items exports --view names --color never
ast-grep outline apps/cli/typer_app.py --view names --color never
```

## Package size and ownership

| Package | Modules | Lines | Declared owner |
| --- | ---: | ---: | --- |
| `libs/services/` (incl. `backends/`) | 21 | 3,855 | none |
| `libs/capabilities/reconciliation/` | 10 | 1,272 | reconciliation |
| `libs/capabilities/agent_hooks/` | 6 | 426 | agent_hooks (Level 1) |
| `libs/capabilities/jobs/` | 2 | 308 | jobs |
| `libs/capabilities/operations/` | 3 | 280 | operations |
| `libs/capabilities/home/` | 2 | 63 | home |
| `libs/domain/` | 4 | 554 | shared |
| `libs/sdk/` | 9 | 509 | SDK channel |
| `apps/cli/` | 5 | 1,058 | CLI channel |
| `libs/actions/` | 11 | 172 | compatibility shim |
| `libs/runtime/` | 3 | 113 | composition root |
| `libs/infra/` | 1 | 1 | dead |

The unowned bucket is larger than every owned capability combined
(3,855 versus 2,349 lines).

## Finding 1 — `libs/services/` is a shared dumping ground

`MODULE-ISOLATION.md` names this failure smell directly: "one feature change
routinely edits top-level `actions/`, `services/`, `domain/`, SDK, and central
test files."

The bucket contains four clusters with four different real owners:

| Cluster | Modules | Lines | Real owner |
| --- | --- | ---: | --- |
| CLI projection | `cli_contracts`, `cli_responses`, `cli_mappers`, `axi_presenter`, `toon_renderer`, `tmux_renderer`, `help_renderer` | 1,299 | `apps/cli` |
| Scheduler adapters and artifacts | `backends/cron_service`, `backends/launchd_service`, `backends/__init__`, `wrapper_renderer`, `state_store`, `logging_paths` | 1,372 | reconciliation |
| Manifest mechanics | `config_loader`, `schema_validator`, `manifest_editor`, `hash_service` | 729 | a new `manifest` module |
| Cross-cutting | `observability`, `logging_config`, `metrics` | 449 | `shared` (observability) and a new `metrics` owner |
| Package initializer | `__init__` | 6 | removed |

Only the CLI cluster is currently documented as owned, and only by import
direction. `docs/dev/architecture.md` states this openly: "Physical location
alone does not make them reusable product services."

## Finding 2 — reconciliation's vertical slice has two physical owners

The scheduler port lives in the capability; its two implementations live
outside it and import back in:

```text
libs/services/backends/cron_service.py
  -> xcron_libs.capabilities.reconciliation.contracts import DeploymentPlan
libs/services/backends/launchd_service.py
  -> xcron_libs.capabilities.reconciliation.contracts import DeploymentPlan
libs/capabilities/reconciliation/scheduler_registry.py
  -> xcron_libs.services.backends.cron_service import (...)
  -> xcron_libs.services.backends.launchd_service import (...)
```

The previous refactor fixed the direction of the *data* dependency — adapters
no longer import `PlanProjectResult` from an action. The *physical* ownership
break remains: the module cannot be moved, tested, or replaced without also
moving code from a sibling top-level package.

Definition of done in `MODULE-ISOLATION.md`: "Its complete vertical slice has
one physical owner." Not met for reconciliation.

## Finding 3 — one state family, two writers

`libs/services/metrics.py` owns `~/.xcron/metrics/metrics.json`
(`resolve_metrics_path`). `MetricsService` is constructed directly by:

```text
libs/capabilities/reconciliation/status.py
libs/capabilities/reconciliation/apply.py
libs/capabilities/operations/logs.py
libs/capabilities/operations/metrics.py
```

Two capabilities write one durable state family through a shared class. The
standard requires one logical writer per state family and public commands for
cross-module writes.

## Finding 4 — only one capability has a public surface

`agent_hooks` has `api.py` and `contracts.py`, an empty non-aggregating
`__init__.py`, private `_`-prefixed implementation files, and a module test
lane. The other four capabilities expose `actions.py` through an aggregating
`__init__.py`, and outside callers deep-import implementation modules:

```text
libs/actions/apply_project.py    -> capabilities.reconciliation.apply
libs/actions/manage_jobs.py      -> capabilities.jobs.actions
libs/actions/manage_logs.py      -> capabilities.operations.logs
libs/actions/plan_project.py     -> capabilities.reconciliation.planning
libs/sdk/schedules.py            -> capabilities.reconciliation.scheduler_registry
libs/sdk/client.py               -> capabilities.reconciliation.scheduler_registry
libs/runtime/composition.py      -> capabilities.reconciliation.scheduler_registry
tests/test_inspect_action.py     -> capabilities.reconciliation.inspect
```

Rule 2 of the dependency law: "Incoming calls enter through one public
surface." Met by `agent_hooks` only.

## Finding 5 — tests are central, not module-owned

```text
tests/                      34 flat test modules
tests/modules/agent_hooks/   2 module-owned test modules
tests/integration/           4 explicit-only host harnesses
```

Fifteen test modules still import the `xcron_libs.actions` compatibility shim.
`MODULE-ISOLATION.md` requires a focused per-module lane that runs "without
importing sibling implementations"; only `agent_hooks` has one.

## Finding 6 — enforcement is one hand-written file

`tests/test_reconciliation_architecture.py` (228 lines) carries twelve
assertions covering adapters, CLI, capabilities, domain, runtime, services,
shims, and registry policy. It has genuine strengths — it checks all four
Python import forms and includes planted negative examples for the
`agent_hooks` scanner.

Its weaknesses against the standard:

- there is no declared dependency graph, so a new module is unprotected by
  default until someone remembers to extend the file;
- planted negatives exist only for `agent_hooks`;
- no Import Linter or Tach contract exists (`rg --files | rg 'tach.toml|importlinter'`
  returns nothing);
- the module name (`test_reconciliation_architecture`) no longer describes its
  repository-wide scope.

## Finding 7 — no validated workspace contract

`libs/services/config_loader.py`:

```text
resolve_project_root:  explicit --project > cwd (if it has schedules/) > ~/.xcron
```

Consequences measured against `WORKSPACES-AND-CONFIGURATION.md`:

- no marker file, so any directory containing `schedules/` is accepted as an
  xcron project — the standard calls this out as the exact case that can
  operate on the wrong project;
- no workspace schema version, so there is no migration gate;
- no `XCRON_PROJECT`-style environment root (only `XCRON_HOME`, which selects
  the home directory, not the project);
- no typed `Workspace` value: capabilities receive `Path` values and re-derive
  sub-paths in `state_store`, `logging_paths`, and `metrics` independently.

## Finding 8 — configuration is single-layer and untyped at the edges

There is no layered configuration: `config_loader` reads one manifest file.
There is no `Settings` model, no `extra="forbid"` boundary for operator
configuration, and no XCFG adapter. Environment variables are read in at least
`config_loader.resolve_xcron_home` and `metrics.resolve_metrics_path`, which
the standard restricts to a single configuration adapter.

## Finding 9 — packaging gaps

```toml
requires-python = ">=3.9"
dependencies = ["PyYAML", "jsonschema", "pydantic", "python-toon", "rich",
                "structlog", "typer"]
packages = [ ... 21 hand-listed packages including "xcron_libs.infra" ... ]
```

- **No `py.typed`.** `rg --files | rg 'py.typed'` returns nothing. The SDK
  ships typed signatures that consumers cannot see.
- **CLI dependencies are mandatory.** `typer`, `rich`, and `python-toon` are
  required to embed the SDK. The standard puts them in a `cli` extra.
- **The package list is hand-maintained** and already contains one dead entry,
  `xcron_libs.infra` (1 line, imported by nothing).
- **Public import names expose repository layout.** The distribution is
  `xcron`, but consumers import `xcron_libs`, `xcron_cli`, and
  `xcron_resources`, mapped from `libs/`, `apps/cli/`, and `resources/`.
- **Packaged resources are shared**, not module-owned: `xcron_resources.help`
  is CLI-owned, `xcron_resources.schemas` is manifest-owned, and
  `xcron_resources.logging` is observability-owned.

## Finding 10 — the CLI shell is one 805-line module

`apps/cli/typer_app.py` declares five Typer sub-apps and 26 commands in one
file. It correctly opens `Xcron` and keeps output at the boundary, but it also
imports six projection modules from `libs/services/` directly.

The previous plan deferred the split as "churn without stronger isolation".
That reasoning holds only while the projection modules stay in `libs/`. Once
they move under `apps/cli/`, splitting by command group and co-locating each
group's contract/mapper becomes an ownership improvement rather than a
cosmetic one.

## Finding 11 — the operating brief documents the pre-refactor architecture

`AGENTS.md` is the file agents read first. Its "Repo Layout" and "Layering
Contract" sections still describe the layout replaced on 2026-08-03:

```text
apps/cli -> libs/actions -> libs/services (incl. backends) -> libs/domain
```

They state that `libs/actions` "owns user-visible use cases" (it is now a
shim), that `libs/services` provides "reusable capabilities" including "hook
installers" (moved into `agent_hooks`), and list `libs/infra` as a real
package. `docs/dev/architecture.md` is current; `AGENTS.md` contradicts it.

## What is already correct and must be preserved

- The typed `SchedulerBackend` port, backend-neutral `DeploymentPlan` /
  `SchedulerInspection` contracts, and the explicit `SchedulerRegistry` with a
  tested unknown/duplicate policy.
- `Xcron.open(...)` as a context-managed composition root with grouped APIs,
  idempotent `close()`, and a stable `ClientClosedError`.
- Channel-neutral capability results; TOON/JSON/tmux, field selection,
  stdout/stderr split, and exit codes confined to the CLI boundary.
- The `agent_hooks` module as the working Level 1 reference implementation,
  including its planted-negative scanner and installed-wheel import smoke.
- `plan` reads derived state, `status` reads actual scheduler state, and
  `apply` starts from `status`. This is a product invariant.
