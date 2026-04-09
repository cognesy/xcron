# xcron Schedule Engine Fix

## Goal

Correct the schedule engine so both backends fully support the schedules they
are natively capable of expressing, and reject what they cannot express with a
clean, operator-facing error before any machine changes occur.

This plan belongs to epic `xcron-mzl`.

## Problem Restatement

Two distinct bugs exist in the schedule rendering layer.

### Bug A — launchd: cron step/range syntax rejected at apply time

`parse_calendar_field` in `libs/services/backends/launchd_service.py` raises
`ValueError` for any cron field that contains `*/<step>` or `-` (range)
syntax, except for the single special case `*/N * * * *` → `StartInterval`.

This means expressions like:

- `0 */4 * * *` — every 4 hours
- `0 0 */2 * *` — every 2 days
- `0 9-17 * * 1-5` — every hour, 9am–5pm, Mon–Fri
- `0,30 * * * *` — at :00 and :30 every hour
- `0 0 * * 1-5` — weekdays at midnight

all pass `validate` and `plan` cleanly, then crash during `apply` with an
unhandled Python exception.

Root cause: `parse_calendar_field` was written to only handle bare integer
lists. It was never extended to handle the full cron grammar that launchd's
`StartCalendarInterval` actually supports (any set of explicit integer values).

Fix: rewrite `parse_calendar_field` to expand all standard cron syntax into
explicit integer value lists. launchd's `StartCalendarInterval` accepts any
set of explicit values for each field, so any valid 5-field cron expression
can be faithfully represented.

### Bug B — cron backend: unsupported `every` schedules crash apply

`render_cron_schedule` in `libs/services/backends/cron_service.py` raises
`ValueError` for two `every` variants that cron genuinely cannot express:

- `every: Xs` — sub-minute intervals (cron minimum granularity is 1 minute)
- `every: Nw` where N > 1 — multi-week intervals

These raise `ValueError` inside `render_cron_block`, which is called from
`apply_cron_plan`, which is called from `apply_project`. No code catches these,
so they surface as unhandled Python tracebacks.

Fix: detect these incompatible schedules before any machine state changes.
Add a backend-compatibility check that runs in `plan_project` (where the
backend is already known) and records each incompatible job as a structured
`PlanChangeKind.ERROR` entry. The operator sees a clean error from `plan`
or `apply`, not an exception from deep inside the rendering layer.

## Constraints

- Preserve the existing architecture: CLI shells in `apps/`, use-case logic
  in `libs/actions/`, backend rendering in `libs/services/backends/`.
- Do not change the manifest schema or the domain model.
- Keep the launchd optimization: `*/N * * * *` → `StartInterval` (simpler
  and more reliable than a large StartCalendarInterval list for pure
  minute-based schedules).
- Reject genuinely inexpressible schedules at plan time, not apply time.
- All existing tests must continue to pass.

## Approach

### Task 1 — Fix launchd calendar field expansion

**File**: `libs/services/backends/launchd_service.py`

Rewrite `parse_calendar_field` to expand all standard cron field syntax into
sorted lists of explicit integers. The launchd `StartCalendarInterval` key
accepts any combination of explicit values for Minute, Hour, Day, Month, and
Weekday.

Field bounds for expansion:

| Field   | Min | Max | Notes                        |
|---------|-----|-----|------------------------------|
| Minute  | 0   | 59  |                              |
| Hour    | 0   | 23  |                              |
| Day     | 1   | 31  |                              |
| Month   | 1   | 12  |                              |
| Weekday | 0   | 7   | launchd treats 0 and 7 as Sunday |

Syntax to expand:

| Syntax   | Meaning                          | Example       | Result           |
|----------|----------------------------------|---------------|------------------|
| `*`      | wildcard (no restriction)        | `*`           | `None`           |
| `N`      | single value                     | `5`           | `[5]`            |
| `N,M`    | comma list                       | `0,30`        | `[0, 30]`        |
| `M-N`    | inclusive range                  | `9-17`        | `[9,10,...,17]`  |
| `*/S`    | step from field min to max       | `*/4`         | `[0,4,8,...]`    |
| `M/S`    | step from M to field max         | `6/2`         | `[6,8,10,...]`   |
| `M-N/S`  | step within range                | `8-20/4`      | `[8,12,16,20]`   |
| Combined | comma-joined combinations        | `0,8-16/4`    | `[0,8,12,16]`    |

`render_launchd_schedule` does not need structural changes — it already builds
the cartesian product from the values returned by `parse_calendar_field`. Only
the expansion logic inside `parse_calendar_field` needs to change.

Keep the optimization: if the cron expression matches `*/N * * * *`, emit
`StartInterval: N*60` instead of a large `StartCalendarInterval` list.

### Task 2 — Add cron backend-compatibility check to plan

**Files**: `libs/actions/plan_project.py`, `libs/domain/diffing.py`

Add a `validate_cron_schedule_compatibility(jobs)` function that inspects each
normalized job and returns a tuple of `(qualified_id, reason)` pairs for
schedules that the cron backend cannot express:

- `every: Xs` (any seconds interval)
- `every: Nw` where N > 1

Call this from `plan_project` after the backend is resolved to `"cron"`. For
each incompatible job, append a `PlanChange(kind=PlanChangeKind.ERROR, ...)` to
the plan's change list. The existing error surfacing in `plan` and `apply` CLI
shells already handles `ERROR`-kind changes.

This surfaces the incompatibility at plan time with a structured, readable
message rather than crashing during `render_cron_block`.

### Task 3 — Add regression tests

**File**: `tests/test_launchd_backend.py`, `tests/test_cron_backend.py`,
`tests/test_planning.py`

Add focused tests for:

- launchd: step syntax in Hour (`0 */4 * * *`)
- launchd: step syntax in Day (`0 0 */2 * *`)
- launchd: range syntax in Hour and Weekday (`0 9-17 * * 1-5`)
- launchd: comma list in Minute (`0,30 * * * *`)
- launchd: combined step + range (`0 8-20/4 * * *`)
- launchd: `*/N * * * *` still emits `StartInterval` (regression)
- cron: `every: 30s` → `plan` returns an ERROR-kind change (not an exception)
- cron: `every: 2w` → `plan` returns an ERROR-kind change (not an exception)

## Task Breakdown

| # | Task                                                | Type    | Depends on |
|---|-----------------------------------------------------|---------|------------|
| 1 | Fix launchd `parse_calendar_field` expansion        | bug     | —          |
| 2 | Add cron backend-compatibility check to `plan`      | bug     | —          |
| 3 | Regression tests for both backends                  | task    | 1, 2       |

Tasks 1 and 2 are independent and can proceed in parallel. Task 3 requires
both to be complete before the full test matrix can be verified.

## Risks

### Cartesian product explosion

Expressions like `* * * * *` (all wildcards) produce no specified fields and
are handled by the `StartInterval: 60` fallback. Expressions like `*/2 */2 * * *`
expand to 30×12 = 360 `StartCalendarInterval` entries — large but valid. Very
dense expressions are an operator problem, not an engine problem.

### Weekday 7 normalization

cron treats weekday 7 as Sunday (same as 0). launchd also accepts 7 = Sunday.
No normalization is required. The expansion can leave 7 as-is.

## Open Questions

None. The retrospective narrowed the scope enough to proceed.
