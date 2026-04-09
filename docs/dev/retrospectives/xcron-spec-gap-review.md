# xcron SPEC Gap Review

## Scope

Review of the full prototype implementation against `SPEC.md` as of 2026-03-23.

At review time:
- 23 closed issues, 3 open (`xcron-mm2`, `xcron-1hs`, `xcron-3ca`)
- all three open items are in the `xcron jobs` CLI edge-case epic
- a fix plan already exists at `docs/dev/plans/xcron-jobs-cli-edge-fixes.md`

## What Is Delivered and Correct

Against the SPEC success criteria:

- per-project manifest discovery under `resources/schedules/` ✅
- schema validation, semantic validation, normalization, stable hashing ✅
- macOS `launchd` and Linux `cron` backends ✅
- all six CLI commands: `validate`, `plan`, `apply`, `status`, `inspect`, `prune` ✅
- `jobs` command group for YAML-only manifest editing (additive, not in SPEC) ✅
- idempotent `apply` ✅
- drift detection via hash embedding in artifacts ✅
- ownership boundary enforcement (launchd prefix, cron block markers) ✅
- all SPEC status states: `ok`, `missing`, `drift`, `disabled`, `extra`, `error` ✅
- all SPEC overlap policies: `allow`, `forbid` via lock-dir wrapper ✅
- deterministic log paths, wrapper lifecycle markers ✅
- state storage partitioned by `project.id` ✅
- thin-shell → action → service architecture ✅

## Major Problems Found

### Bug 1: Cron step syntax in non-minute positions fails at apply time (untracked)

**Severity: HIGH**

Cron expressions with step syntax (`*/N`) in positions other than minute pass
validation but raise an unhandled `ValueError` at apply time on macOS launchd.

Examples that fail silently until apply:
- `0 */4 * * *` — every 4 hours
- `0 0 */2 * *` — every 2 days
- `30 */6 * * *` — every 6 hours at :30

Root cause: `render_launchd_schedule` converts `*/N * * * *` (minute step,
all-wildcard rest) to `StartInterval` correctly. But for any other position,
`parse_calendar_field` is called, which rejects `*/N` tokens:

```python
if "*/" in field or "-" in field:
    raise ValueError(f"unsupported cron syntax for launchd {field_name}: {field}")
```

The schema validator accepts `*/N` syntax via `CRON_FIELD_PATTERN`, so the
expression passes `validate` and `plan` cleanly. The failure surfaces only at
`apply`.

SPEC requirement (`validate`): "invalid paths or unsupported field combinations"
must be caught at validate time.

Fix direction: detect unsupported launchd cron syntax at validation time or at
plan time when the backend is known. Alternatively, expand `render_launchd_schedule`
to handle common step patterns in hour, day, month fields by expanding them to
`StartCalendarInterval` lists.

### Bug 2: `every: Xs` (seconds) silently fails with cron backend (untracked)

**Severity: MEDIUM**

`every: 30s` is valid per the SPEC model and passes `validate_semantics`. On
macOS it works: `parse_every_seconds` converts seconds to `StartInterval`.
On Linux (`cron` backend) it raises an unhandled `ValueError` at apply time
because `render_cron_schedule` only handles `m`, `h`, `d`, `w`:

```python
raise ValueError(f"cannot translate portable every schedule to cron: {job.schedule.value}")
```

Same for multi-week intervals: `every: 2w` passes validation but fails in the
cron backend at apply.

Fix direction: catch unsupported `every` + backend combinations during `plan`
rather than at `apply`, so the user gets a clean error before any machine
changes.

### Bug 3: `--env BAD` crashes with traceback (tracked: xcron-3ca)

**Severity: MEDIUM**

`_parse_env_assignments()` raises `ValueError` for malformed input like
`--env BAD`, which escapes the CLI shell boundary and prints a Python traceback
instead of a clean command failure.

Fix plan exists in `docs/dev/plans/xcron-jobs-cli-edge-fixes.md`.

### Bug 4: `jobs update` with no flags rewrites manifest (tracked: xcron-1hs)

**Severity: MEDIUM**

`xcron jobs update JOB_ID` with no field flags succeeds, reports
`updated_job: ...`, and rewrites the YAML file on disk even though no semantic
change was requested.

Fix plan exists in `docs/dev/plans/xcron-jobs-cli-edge-fixes.md`.

## Design Gaps

### Gap 1: `plan` vs `status` semantic split is undocumented

`plan` computes its output from derived local state (`project-state.json`).
`status` queries the actual backend (real plist files, real crontab).

This means:
- after `apply`, if a plist is manually removed, `plan` shows NOOP, `status`
  shows MISSING
- `plan` works offline and is fast; `status` is ground-truth but slower

This split is a reasonable design choice but is not explained anywhere in the
user docs. Users who reach for `plan` expecting a ground-truth view will be
misled. The distinction should be documented explicitly.

### Gap 2: Backend-specific cron syntax limitations are invisible to the user

Launchd cannot express arbitrary cron step/range syntax. The cron backend
cannot express sub-minute or multi-week intervals. Neither limitation is
surfaced at `validate` time. This means users can write manifests that are
valid per SPEC but fail on one or both backends.

The SPEC asks for "cross-platform portability" and "behavior should be
explicit and unsurprising." Silently failing at apply violates that.

Fix direction: add a backend-compatibility validation pass to `plan` (when the
backend is known) that flags incompatible schedule expressions before any
machine changes are attempted.

## Minor Observations

- `cron artifact_path` for the real user crontab is set to `"<user crontab>"`,
  not a real inspectable path. This makes `inspect` output for cron less useful
  than for launchd.
- The `parse_calendar_field` range syntax rejection (`-` in field) is correct
  for launchd but should be documented as a known cron portability limitation.

## bd Housekeeping

Open issues at review time:

| id | type | title |
|----|------|-------|
| xcron-mm2 | epic | Fix jobs CLI edge-case failures |
| xcron-1hs | bug | Reject no-op jobs update commands |
| xcron-3ca | bug | Handle invalid --env assignments without traceback |

Two new untracked bugs surfaced in this review:
- Cron step syntax in non-minute positions fails at launchd apply (HIGH)
- `every: Xs` and `every: Nw` (N>1) fail at cron apply (MEDIUM)

## Recommended Next Actions

1. File bd issues for the two new untracked bugs.
2. Implement the existing `xcron-mm2` plan (`xcron-1hs`, `xcron-3ca`).
3. Add backend-compatibility validation to `plan` for launchd cron step
   restrictions and cron `every` limitations.
4. Update user docs to explain the `plan` (local state) vs `status` (actual
   backend) semantic split.

## What Worked Well

- Architecture stayed intact across all epics; every fix was local, not
  cross-cutting.
- The hash-based drift detection model is clean and reliable.
- Wrapper lifecycle markers make managed jobs independently observable.
- `status` correctly queries actual backend state rather than cached local
  state.
- `inspect` now surfaces artifact path, wrapper path, and log paths as
  required by SPEC.
