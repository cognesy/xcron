# Design review

## Internal review outcome

The implementation follows the incremental sequence and constraints below. The
plan addressed the real architectural break (adapter imports from the action
layer) before changing the channel/SDK wiring, so the later steps stand on a
backend-neutral contract. The Beads database was migrated only after the user
explicitly designated this checkout as the migrator.

## Deliberate exclusions

- No plugin marketplace, entry-point discovery, extension manifests, or
  generic subprocess protocol for `cron`, `launchd`, or a future `systemd`
  backend. These are first-party adapters; the typed registry is the correct
  present isolation boundary.
- No change to schedule language, YAML schema, artifact ownership markers,
  derived-state semantics, or native scheduler integration behaviour.
- No changes to reference repositories; XQA, CXTK, xfind, and Stepping Stones
  were inspected read-only.
- No mechanical split of `apps/cli/typer_app.py`: the commands are already thin
  SDK channel adapters, and a declaration-only file split would add churn
  without strengthening isolation. The architecture test enforces the material
  CLI boundary instead.
- No Beads bootstrap or database replacement. The authorized schema migration
  preserved the existing dirty working set in a Dolt commit before advancing
  the database from schema v46 to v53 and pushing it to the configured remote.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| A contract move changes plan/apply semantics | Reuse `ProjectPlan` and verify planner/status/backend tests before and after each move. |
| SDK becomes a second implementation | Compose existing capability actions only; CLI and SDK share the same registry/runtime. |
| CLI refactor changes AXI behaviour | Leave mappers/output in `apps/cli`; preserve existing CLI tests and help smokes. |
| Compatibility breaks current importers | Maintain `xcron_libs.actions` re-exports and test the legacy imports. |
| Over-engineered extension framework | Keep a first-party typed registry; require a concrete independent dependency/release/failure case before considering process isolation. |
| Folder renames claim more than they enforce | Add targeted import/AST architecture tests for every essential boundary. |

## Completion criteria

The refactor is complete when the following are true:

1. No scheduler adapter imports `xcron_libs.actions`.
2. A typed backend contract and explicit runtime registry select cron and
   launchd.
3. `Xcron.open(...)` provides grouped typed APIs and keeps a CLI-free public
   import surface.
4. CLI commands use the SDK/composition helper and all output conversion stays
   at the CLI boundary.
5. Existing command, manifest, planning, status, apply, and scheduler
   contracts remain compatible.
6. Import-boundary, SDK, backend, and CLI tests pass with the deterministic
   core suite.
7. Architecture and Go-rewrite documentation match the implemented shape.
8. Beads epic `xcron-c81` and phase tasks `xcron-c81.1` through `xcron-c81.5`
   are created with ordered blocking dependencies and closed only after their
   recorded verification passes.

## Execution evidence (2026-08-03)

- Scheduler reconciliation now lives in a capability package with a typed
  `SchedulerBackend` contract, backend-neutral `DeploymentPlan` and
  `SchedulerInspection` contracts, and an explicit first-party
  `SchedulerRegistry` for `cron` and `launchd`.
- `Xcron.open(...)` composes one runtime containing resolved immutable options
  and the scheduler registry, then exposes grouped schedules, jobs, operations,
  hooks, and home APIs. Every public SDK method has an explicit return type.
- The Typer shell uses that SDK. Capability results, including metrics, remain
  channel-neutral; TOON, JSON, tmux, field selection, stdout/stderr, and exit
  codes stay at the CLI output boundary.
- `xcron_libs.actions` remains as an import-compatible shim over the
  capabilities. `xcron_libs.services` is intentionally a non-aggregating
  package so leaf service imports cannot eagerly load CLI projections.
- Architecture tests enforce adapter, SDK, CLI, capability, domain, runtime,
  services, and compatibility-shim boundaries. A fresh-process test proves
  importing `xcron_libs` does not load Typer, `xcron_cli`, or CLI response
  models.
- A wheel was built, installed into an isolated virtual environment, and
  passed the same CLI-free public-import smoke.
- `./scripts/verify-core.sh` completed successfully: 152 passed. The explicit
  host scheduler integration checks were intentionally not run because they
  remain opt-in and can mutate real scheduler state.
- Beads was upgraded to 1.1.2, the pending working set was preserved in Dolt
  commit `rr33jrt8eo8uauj9orh22d8nu8oqftpt`, schema migration v46 to v53
  completed, and the result was pushed. Epic `xcron-c81` and tasks
  `xcron-c81.1` through `xcron-c81.5` record the execution and verification;
  all five phase tasks were closed after their acceptance checks passed.
