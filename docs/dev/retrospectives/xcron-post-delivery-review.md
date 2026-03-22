# xcron Post-Delivery Review

## Scope

Retrospective scope: the completed `xcron-0mt` prototype plus the follow-up bug
fix `xcron-qm2`.

At review time:

- `bd status --json` reported 13 closed issues
- no open issues
- no in-progress issues
- no open epics

This made the prototype a valid completed unit for retrospective review.

## What Was Delivered

The delivered prototype includes:

- per-project manifest discovery under `resources/schedules/`
- schema validation, semantic validation, normalization, and stable hashing
- planner and derived local state storage
- wrapper generation with default logs and overlap control
- macOS `launchd` backend
- Linux `cron` backend
- CLI thin shells for `validate`, `plan`, `apply`, `status`, `inspect`, and
  `prune`
- tests, examples, architecture notes, and Go rewrite contract docs

The architecture stayed aligned with the intended thin-shell -> action ->
service split.

## Plan Versus Reality

The original task breakdown was mostly accurate.

What worked well:

- schema/model -> validation -> planner -> wrappers -> backends -> CLI was the
  right sequence
- backend work was easier because wrappers and state handling were factored out
  first
- the explicit retrospective bug `xcron-qm2` stayed narrowly scoped and was
  fixed without broad churn

Where reality differed from the plan:

- several correctness issues only became obvious after reviewing actual backend
  state reconstruction rather than reading the intended flow
- the initial implementation over-trusted derived local state in places where
  actual backend state needed to be authoritative
- monitoring/observability for control-plane actions and real scheduled process
  execution was under-specified during the initial build

## Findings Fixed In This Review

### 1. Missing control-plane observability

The action layer and backend subprocess calls were effectively uninstrumented.
That made it hard to monitor `validate`, `plan`, `apply`, `status`, `inspect`,
and `prune` behavior.

Fix:

- added `structlog`-based logging setup
- added action instrumentation decorators
- logged backend subprocess calls such as `launchctl`, `crontab`, and `id`
- logged wrapper/plist/crontab write events and runtime path generation

### 2. Missing runtime execution markers for actual scheduled jobs

The managed wrapper redirected stdout/stderr but did not emit explicit start and
finish markers for the real scheduled process.

Fix:

- wrappers now emit `event=job_started`
- wrappers now emit `event=job_finished`
- finish markers include `exit_code` and `duration_seconds`
- signal/exit handling was tightened so finish logging remains single-shot

This makes the managed stderr log usable as an execution timeline instead of a
raw command sink only.

### 3. Backend-only inspection lost log paths

When reconstructing deployed state from `cron` or `launchd`, the code preserved
wrapper paths but dropped stdout/stderr log paths. That weakened monitoring and
inspection after backend-only reconstruction.

Fix:

- added log-path derivation from wrapper paths
- preserved stdout/stderr log paths in cron inspection/state reconstruction
- preserved stdout/stderr log paths in launchd inspection/state reconstruction

### 4. `inspect` output undershot the spec

The `inspect` CLI output omitted useful operator data that the implementation
already knew, such as artifact path, wrapper path, and log paths.

Fix:

- `inspect` now surfaces artifact path
- `inspect` now surfaces wrapper path
- `inspect` now surfaces stdout/stderr log paths
- `inspect` prints the raw managed cron entry where relevant

## Remaining Gaps

No new high-severity implementation bugs were left open after this review.

Residual risk:

- logging behavior is smoke-tested and integration-tested through CLI/backend
  paths, but there is still room for richer explicit observability assertions if
  the tool grows further

No new `bd` follow-up issues were created from this retrospective.

## Verification

Verification run after the fixes:

```sh
uv run pytest
```

Result:

- 10 tests passed

The test suite now also covers:

- wrapper execution lifecycle markers
- backend-derived log-path preservation
- CLI `inspect` output for artifact/wrapper/log paths

## Patterns

Repeated pattern observed during the prototype:

- the easiest mistakes were not in schema or planner logic
- they were in the boundary between desired state, actual backend state, and
  operator observability

This matches the earlier `xcron-qm2` bug and this review’s observability fixes.

## Lessons

### Process lessons

- Future planning for scheduler or queue tools should treat “actual runtime
  state inspection” as a first-class design area, not a late polish item.
- Retrospectives should explicitly review backend-state reconstruction and
  monitoring behavior, not only primary apply/plan flows.
- Verification for OS-integrated tools should include operator-facing inspection
  output, not only backend internals and unit-level rendering.

### Implementation lessons

- Derived local state is useful, but `status`, `inspect`, and `apply` must stay
  grounded in actual backend state.
- Runtime wrappers should emit minimal lifecycle metadata themselves; relying on
  command stdout/stderr alone is too weak for monitoring.
- If log paths are deterministic, backend inspection should reconstruct them
  rather than assuming the saved state file is always present.

## What Worked Well

- The action/service split made the fixes local instead of cross-cutting
- deterministic runtime paths made log-path reconstruction straightforward
- existing backend tests made it safe to tighten behavior without guesswork
- using `uv` kept dependency and verification changes simple
