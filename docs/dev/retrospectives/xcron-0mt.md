# xcron-0mt Retrospective

## Scope

Epic: `xcron-0mt`

Delivered scope:

- per-project `schedules.yaml` model
- Python prototype following `apps/` -> `libs/actions/` -> `libs/services/`
- validation, normalization, hashing, planning, wrappers, local derived state
- `launchd` backend
- `cron` backend
- CLI commands for `validate`, `plan`, `apply`, `status`, `inspect`, `prune`
- tests, examples, and user/developer docs

The epic is complete and all original child tasks were closed.

## Plan vs Reality

What matched the original plan:

- task decomposition was mostly accurate
- dependency order was correct
- the action/service/thin-shell architecture held through implementation
- the Python-first prototype was a good fit for converging on the model quickly

Where execution diverged:

- several important correctness issues only became obvious during late
  verification:
  - wrapper lock cleanup needed a runtime test to catch the `exec`/trap bug
  - `apply` originally reconciled against cached derived state rather than
    actual backend state
  - backend state reconstruction assumed `project.id` had no dots
- packaging/test-path cleanup was discovered only after the first full pytest
  pass and local install flow

## Implementation Findings

Findings discovered during the retrospective:

1. `apply_project` used `plan_project`, which diffed against local derived state
   rather than actual backend state. This meant missing backend artifacts could
   be left unrepaired if the cache still said they existed.
2. `collect_launchd_project_state` and `collect_cron_project_state` derived
   `job_id` by splitting `qualified_id` on the first dot, which was incorrect
   for dotted `project.id` values allowed by the schema.

Both issues were fixed during the retrospective and covered by regression
tests. The follow-up bug was tracked as `xcron-qm2` and closed after the fix.

## What Worked Well

- The per-task verification discipline caught real runtime bugs before the work
  was treated as stable.
- Keeping the backends behind services made the retrospective fixes local and
  low-risk.
- Sample manifests plus CLI smoke tests were useful for confirming the external
  operator contract, not just internals.

## Friction Patterns

- The local `bd`/Dolt server intermittently tripped its circuit breaker, which
  slowed close-out and required retries.
- Several backend behaviors looked correct in static code review but only
  failed under concrete runtime tests.

## Next-Cycle Adjustments

Process adjustments:

- Add at least one runtime verification step for wrapper/process-management
  work, not just render/snapshot tests.
- Treat `apply` semantics as “desired vs actual backend state” from the start
  in future scheduling/control-plane work.
- Add dotted-identifier cases early whenever IDs are allowed to contain dots or
  path-like separators.

Implementation adjustments:

- Keep `plan` and `status` conceptually separate:
  - `plan` can remain a derived-state preview
  - `status` and `apply` must be grounded in actual backend state
- Carry explicit metadata through backend artifacts instead of reverse-parsing
  identifiers when the schema already provides stable fields.

## Final State

- automated tests pass locally
- the retrospective follow-up bug is fixed
- no additional retrospective-discovered work remains open for this epic
