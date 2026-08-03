# xcron capability-first refactor

## Purpose

Refactor xcron from a global `apps -> actions -> services -> domain` directory
layout into independently understandable capability slices without changing the
project-local manifest, scheduler ownership, or AXI CLI contract.

This is a brownfield refactor. Each increment must preserve the existing
Python CLI behaviour and leave the later Go rewrite's public contract intact.

## Why now

At the planning baseline, both scheduler services imported `PlanProjectResult`
from `xcron_libs.actions.plan_project`. That made a reusable backend depend on
the action coordinating it, contrary to the documented direction. The 806-line
Typer module also constructed and called actions directly, so a second channel
could not reuse the same composition safely.

The repository already has useful seams: normalized domain models, a planner,
state store, manifest editor, backend-specific services, typed CLI response
models, and tests. The plan extracts and enforces those seams instead of
replacing working scheduler behaviour.

## Decisions

1. Keep the public product contract stable: manifests under
   `resources/schedules`, `project.id`, cron/`every`, derived local state,
   existing CLI commands, TOON/JSON output, exit codes, and host scheduler
   ownership rules all remain unchanged.
2. Organize application code by capability, not by every technical layer.
   The initial capabilities are `reconciliation`, `jobs`, `operations`, and
   `agent_hooks`.
3. Treat the native scheduler backends as trusted typed providers. A runtime
   registry selects `launchd` or `cron` through a small host-owned port.
4. Do **not** introduce metadata discovery, entry points, subprocess dispatch,
   or a generic plugin platform. Built-in scheduler adapters share xcron's
   lifecycle and dependencies, so process isolation would add cost without
   solving a present dependency, crash, or release-isolation problem.
5. Add an embeddable `Xcron` SDK that composes the same capability APIs as the
   CLI. It owns no scheduler state itself and never imports Typer or output
   renderers.
6. Preserve `xcron_libs.actions` as compatibility re-exports while callers
   migrate. Delete only after a deliberate compatibility decision.

## Documents

- [00-current-state.md](00-current-state.md) records live evidence and the
  boundary problems to remove.
- [01-target-architecture.md](01-target-architecture.md) defines the target
  seams, dependency direction, ownership, and explicit non-goals.
- [02-execution-plan.md](02-execution-plan.md) is the ordered implementation
  and verification plan.
- [03-review.md](03-review.md) records the design review, completion criteria,
  and final execution evidence.

## Tracking

Beads epic `xcron-c81` tracks the refactor, with dependent tasks `xcron-c81.1`
through `xcron-c81.5` corresponding to phases 0 through 4 in
`02-execution-plan.md`. The designated-migrator authorization was supplied on
2026-08-03: the existing database was preserved, migrated from schema v46 to
v53 with Beads 1.1.2, and pushed to its configured Dolt remote. No bootstrap or
database replacement was performed.
