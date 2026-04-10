---
name: admin-xcron
description: >-
  Guide agents on xcron admin and troubleshooting operations: diagnosing drift,
  recovering broken state, inspecting backend artifacts, understanding ownership
  boundaries, and using test overrides. Use this skill when something is wrong
  with a deployed schedule or when operating xcron at a system level rather than
  as a normal project user.
---

# xcron Admin Skill

## Purpose

Use this skill when the task is diagnostic or corrective rather than routine:
a job is not running, the scheduler state looks wrong, a plist or crontab entry
is missing or stale, or you need to reason about what xcron has deployed and
why.

## Mental Model for Admins

xcron has three distinct state layers:

| Layer | What it is | Where it lives |
|-------|-----------|----------------|
| Desired state | YAML manifest | `resources/schedules/<name>.yaml` |
| Derived local state | xcron's own records of the last apply | `~/.local/state/xcron/projects/<id>/` (Linux) or `~/Library/Application Support/xcron/projects/<id>/` (macOS) |
| Actual backend state | Real scheduler artifacts | `~/Library/LaunchAgents/` (launchd) or user crontab (cron) |

`plan` compares desired state against **derived local state**.
`status` compares desired state against **actual backend state**.

These differ whenever anything touches the scheduler outside xcron. Always
use `status` for ground-truth diagnostics.

## CLI Shape

xcron now emits TOON-first structured stdout for normal command execution.

For admin work, this changes how you should read command results:

- bare `xcron` is a safe home/dashboard view
- `status`, `plan`, and `jobs list` return tabular TOON arrays
- `inspect` returns structured desired/deployed objects plus snippet payloads
- `--fields` narrows noisy responses
- `--full` disables truncation in detail-heavy inspect output

## State Storage Layout

```
# macOS
~/Library/Application Support/xcron/projects/<project-id>/
  project-state.json       # xcron's records from last apply
  wrappers/                # generated shell wrapper scripts
  logs/                    # stdout and stderr logs per job
  locks/                   # overlap lock directories (transient)

# Linux
~/.local/state/xcron/projects/<project-id>/
  project-state.json
  wrappers/
  logs/
  locks/
```

Override the state root for isolated testing:

```sh
XCRON_STATE_ROOT=/tmp/xcron-test xcron apply
```

## Diagnostic Workflow

When something is wrong, work through these steps in order:

### 1. Validate the manifest

```sh
xcron validate
```

Catches YAML errors, schema violations, duplicate job ids, invalid schedule
expressions, and non-existent working directories before anything touches
the scheduler.

### 2. Check actual deployed state

```sh
xcron status
xcron status --fields backend,statuses
```

Status reflects the real scheduler, not xcron's local records. If a job shows
`missing`, `drift`, or `extra`, the scheduler and the manifest are out of sync.

Representative output:

```text
backend: cron
count: 2 of 2
statuses[2,]{kind,id,reason}:
  missing,myapp.sync_docs,job is not currently installed in the backend
  drift,myapp.cleanup_tmp,deployed state differs from desired definition
```

### 3. Inspect one job in depth

```sh
xcron inspect <job-id>
xcron inspect <job-id> --fields backend,job,status,deployed.artifact_path,snippets
xcron inspect <job-id> --full
```

Shows:
- normalized desired definition (schedule, command, working dir, env, overlap)
- artifact path (plist or crontab reference)
- wrapper script path
- stdout and stderr log paths
- backend-native status (launchd loaded/enabled state, raw plist, or managed
  cron entry)
- hash comparison (desired hash vs deployed hash)

Hash mismatch means the deployed artifact does not match what xcron last wrote.
This is the drift signal.

Large raw snippet fields are truncated by default. Use `--full` when you need
the complete plist, cron entry, or `launchctl print` output.

### 4. Reconcile

```sh
xcron apply
```

Converges actual backend state toward the manifest. Safe to run repeatedly —
apply is idempotent. Jobs with no change are left alone.

## Common Failure Scenarios

### Job not running — plist or crontab entry missing

```
xcron status  →  missing
```

The job is in the manifest but the scheduler artifact is gone (manual deletion,
system cleanup, or first run before any apply).

Fix:

```sh
xcron apply
```

### Job not running — drift detected

```
xcron status  →  drift
```

The deployed artifact exists but its hash does not match the last-applied hash.
Something modified the artifact outside xcron.

Fix:

```sh
xcron apply   # overwrites the artifact with the correct version
```

### plan says noop but status shows missing or drift

`plan` reads xcron's local records. Those records still show the job as
deployed. `status` reads the actual scheduler and sees the truth.

This happens after manual edits to plists, crontab, or wrapper scripts, or
after a system event removes launchd agents.

Fix:

```sh
xcron apply   # apply always uses status (actual backend) as its baseline
```

### Extra managed artifact with no matching job

```
xcron status  →  extra
```

A managed plist or cron entry exists for a job that is no longer in the
manifest. This can happen if a job was removed from YAML but apply was not
run afterward, or if the project id changed.

Fix:

```sh
xcron apply   # removes the orphaned artifact
# or, to remove all managed artifacts for the project:
xcron prune
```

### Job runs but produces no output or errors

Check the job's log files. The paths are shown by `xcron inspect <job-id>`.

```sh
xcron inspect <job-id>
# note stdout_log_path and stderr_log_path, then:
tail -f ~/.local/state/xcron/projects/<id>/logs/<artifact-id>.err.log
```

The stderr log contains xcron's own lifecycle markers:

```
2026-03-23T05:00:00Z event=job_started qualified_id=myapp.sync pid=12345
2026-03-23T05:00:01Z event=job_finished qualified_id=myapp.sync exit_code=0 duration_seconds=1
```

If `job_started` appears but `job_finished` does not, the process was killed.
If neither appears, the wrapper was not invoked — check the backend artifact.

### Overlap: job skipped because previous run is still active

If `overlap: forbid` is set, xcron uses a lock directory under
`<state-root>/projects/<id>/locks/<artifact-id>.lock/`. If a previous run
was killed without cleanup, the lock directory may still exist.

Check:

```sh
ls ~/.local/state/xcron/projects/<project-id>/locks/
```

If the lock exists and no matching process is running, remove it:

```sh
rmdir ~/.local/state/xcron/projects/<project-id>/locks/<artifact-id>.lock
```

## Ownership Boundaries

xcron only modifies artifacts it created. It will never touch:

- launchd plists it did not write (labels not prefixed with `com.xcron.`)
- crontab entries outside its managed block (`# BEGIN XCRON project=<id>` …
  `# END XCRON project=<id>`)
- any user-managed scheduler configuration

If a managed artifact is missing, xcron recreates it on the next apply. It
does not attempt to interpret or repair artifacts it did not create.

Managed label format (launchd): `com.xcron.<project-id>.<job-id>`
Managed block format (cron): `# BEGIN XCRON project=<id>` … `# END XCRON project=<id>`

## Removing All Managed Artifacts for a Project

```sh
xcron prune
```

Removes all plists (launchd) or the managed cron block (cron), plus all wrapper
scripts. Does not remove logs or lock directories. Does not modify
`project-state.json` — run `xcron apply` after restoring the manifest if you
want xcron's records to reflect the clean state.

To completely reset xcron state for a project:

```sh
xcron prune
rm -rf ~/.local/state/xcron/projects/<project-id>/        # Linux
rm -rf ~/Library/Application\ Support/xcron/projects/<project-id>/  # macOS
```

## Testing Overrides

All system paths can be redirected for isolated testing without touching the
real scheduler or state root:

| Variable | Overrides |
|----------|-----------|
| `XCRON_STATE_ROOT` | derived state root (wrappers, logs, locks, project-state.json) |
| `XCRON_LAUNCH_AGENTS_DIR` | plist output directory (launchd) |
| `XCRON_LAUNCHCTL_DOMAIN` | launchd domain target (e.g. `gui/501`) |
| `XCRON_CRONTAB_PATH` | file path used instead of the real user crontab |
| `XCRON_MANAGE_LAUNCHCTL` | set to `0` to skip all launchctl calls |
| `XCRON_MANAGE_CRONTAB` | set to `0` to skip all crontab writes |

Example — run a full apply cycle without touching any real system paths:

```sh
XCRON_STATE_ROOT=/tmp/xcron-test \
XCRON_LAUNCH_AGENTS_DIR=/tmp/xcron-test/agents \
XCRON_MANAGE_LAUNCHCTL=0 \
xcron apply
```

## Runtime Help And Hooks

Admin sessions should prefer runtime help and repo-local hooks over stale copied
examples:

```sh
xcron --help
xcron status --help
xcron inspect --help
xcron hooks install
```

xcron's agent hooks are installed repo-locally under:

- `.codex/config.toml`
- `.codex/hooks.json`
- `.claude/settings.json`

The generated hook commands use the absolute path of the current `xcron`
executable and are designed to self-repair when that path changes.

## Backend-Specific Notes

### launchd (macOS)

- Plists live in `~/Library/LaunchAgents/com.xcron.<project-id>.<job-id>.plist`
- Each job runs through a generated wrapper script; the plist's
  `ProgramArguments` points to the wrapper
- `xcron inspect` can show `launchctl print` output for the loaded service
- If launchctl reports a job is loaded but not running, check `LastExitStatus`
  in the plist output; a non-zero code means the wrapper exited with an error
- Timezone is set via `TZ=` export in the wrapper, not via launchd keys

### cron (Linux)

- xcron manages a delimited block in the user crontab; all other crontab
  content is preserved
- Each cron line invokes the wrapper script directly
- `artifact_path` in inspect output shows the crontab file path, or
  `<user crontab>` when managing the real crontab
- `every` schedules are translated to cron expressions: `15m` → `*/15 * * * *`,
  `4h` → `0 */4 * * *`, `1d` → `0 0 */1 * *`, `1w` → `0 0 * * 0`
- Sub-minute (`every: 30s`) and multi-week (`every: 2w`) intervals are not
  expressible in cron and are rejected at plan time with a clear error

## Verifying Changes Are Safe Before Applying

```sh
xcron validate   # schema and semantic checks
xcron plan       # shows what apply would do based on xcron's last records
xcron status     # shows actual deployed state vs manifest
```

If `plan` and `status` disagree, trust `status`. Apply always uses actual
backend state as its baseline.
