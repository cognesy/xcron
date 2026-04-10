---
name: use-xcron
description: >-
  Guide agents on day-to-day xcron use: defining and editing scheduled jobs in
  a project manifest, applying changes to the OS scheduler, and verifying
  deployed state. Use this skill when the broader task involves running
  something on a recurring schedule as part of a project's normal operation.
---

# xcron User Skill

## Purpose

Use this skill when the task calls for managing scheduled jobs in the context
of a project — adding a new schedule, changing when something runs, disabling
a job temporarily, or confirming that the schedule is deployed correctly.

xcron is not a daemon. It compiles one project's schedule manifest into
OS-native scheduler artifacts and reconciles them on demand. The OS scheduler
(launchd on macOS, cron on Linux) owns execution. xcron owns the definition
layer and the artifacts it generates.

## Core Model

- The source of truth is `resources/schedules/<name>.yaml` inside the project.
- Each job has a stable `id`, a `schedule` (cron expression or `every` interval),
  and a `command` (shell string executed from the project root).
- `xcron jobs ...` edits YAML only. `xcron apply` reconciles the scheduler.
- Never edit plists, crontab entries, or wrapper scripts directly. xcron owns
  those artifacts and will overwrite them.

## CLI Shape

xcron now uses AXI-style, TOON-first stdout for normal command execution.

Important implications:

- Bare `xcron` is a content-first home view, not a usage error.
- List and mutation commands return structured TOON rather than ad-hoc text.
- `--fields` narrows output to selected fields when the command supports it.
- `--full` expands detail-heavy views such as `xcron inspect`.
- Runtime `--help` is sourced from `resources/help/` and is the authoritative
  command reference.

## Standard Workflow

For any change to a project's schedule:

```
1. edit the manifest (via xcron jobs ... or directly in YAML)
2. xcron validate          — check for errors before touching the scheduler
3. xcron plan              — preview what apply will do
4. xcron apply             — reconcile the scheduler to the manifest
5. xcron status            — confirm the deployed state matches desired
```

Always validate before apply. Always check status after apply.

## Manifest Location and Selection

```
<project-root>/resources/schedules/<schedule-name>.yaml
```

If there is exactly one manifest in `resources/schedules/`, xcron selects it
automatically. If there are multiple, pass `--schedule <name>`.

Run from the project root:

```sh
xcron validate
xcron apply
```

Or pass the project path explicitly:

```sh
xcron --project /path/to/project validate
xcron --project /path/to/project apply
```

## Manifest Format

```yaml
version: 1

project:
  id: myapp                      # required; stable identifier, lowercase

defaults:
  working_dir: .                 # resolved relative to project root
  shell: /bin/sh
  timezone: Europe/Warsaw        # optional; applied to all jobs
  env:
    PATH: /usr/local/bin:/usr/bin:/bin

jobs:
  - id: sync_invoices            # required; unique within the project
    description: Pull invoice data from provider
    schedule:
      cron: "*/15 * * * *"       # standard 5-field cron expression
    command: ./bin/sync-invoices
    env:
      LOG_LEVEL: info
    overlap: forbid              # skip if previous run still active

  - id: cleanup_tmp
    schedule:
      cron: "0 3 * * *"
    command: ./bin/cleanup-tmp

  - id: refresh_cache
    enabled: false               # defined but not deployed
    schedule:
      every: 10m                 # portable interval: s m h d w
    command: ./bin/refresh-cache
```

### Schedule Options

**Cron expression** — any standard 5-field expression:

```yaml
schedule:
  cron: "*/15 * * * *"      # every 15 minutes
  cron: "0 */4 * * *"       # every 4 hours at :00
  cron: "0 9-17 * * 1-5"    # every hour 9am–5pm, Mon–Fri
  cron: "0 0 * * 1-5"       # weekdays at midnight
  cron: "30 6 * * *"        # daily at 06:30
```

**Portable interval** — backend-independent, supported on both macOS and Linux:

```yaml
schedule:
  every: 30m     # every 30 minutes
  every: 4h      # every 4 hours
  every: 1d      # every day
  every: 1w      # every week
```

Note: `every` with seconds (`30s`) works on macOS (launchd) but is rejected
on Linux (cron cannot schedule sub-minute intervals). `every: 2w` and longer
multi-week intervals are also not supported with cron. Use a cron expression
for cross-platform portability.

### Overlap Policy

```yaml
overlap: allow    # default — concurrent runs permitted
overlap: forbid   # skip if previous run is still active (lock file)
```

## Common Operations

### Add a new job

```sh
xcron jobs add sync_reports \
  --command ./bin/sync-reports \
  --cron "0 6 * * *" \
  --description "Daily report sync"
xcron apply
```

### Change a job's schedule

```sh
xcron jobs update sync_reports --cron "0 */2 * * *"
xcron apply
```

### Disable a job without removing it

```sh
xcron jobs disable refresh_cache
xcron apply
```

### Re-enable a job

```sh
xcron jobs enable refresh_cache
xcron apply
```

### Remove a job

```sh
xcron jobs remove old_job
xcron apply
```

### View all jobs in the manifest

```sh
xcron jobs list
```

### View one job

```sh
xcron jobs show sync_reports
```

## Checking Deployed State

```sh
xcron status
xcron status --fields backend,statuses
```

Status values:

| State      | Meaning |
|------------|---------|
| `ok`       | desired and deployed state match |
| `missing`  | job is in the manifest but not deployed |
| `drift`    | job is deployed but differs from desired |
| `disabled` | job is intentionally disabled in the manifest |
| `extra`    | a managed artifact exists but no matching job is in the manifest |
| `error`    | backend inspection failed |

If status shows anything other than `ok` or `disabled`, run `xcron apply`
to reconcile.

Representative status output now looks like:

```text
backend: cron
count: 2 of 2
statuses[2,]{kind,id,reason}:
  ok,myapp.sync_invoices,desired definition and actual backend state are aligned
  disabled,myapp.refresh_cache,job is disabled in desired state
```

## Inspecting One Job

```sh
xcron inspect sync_reports
xcron inspect sync_reports --fields backend,job,status,desired.command,deployed.artifact_path
xcron inspect sync_reports --full
```

`inspect` returns structured desired/deployed field sets plus backend-native
snippets. Large snippet content is truncated by default and expanded by
`--full`.

## plan vs status

`plan` compares the manifest against xcron's local records (written during
the last apply). It previews what `apply` will do.

`status` compares the manifest against the actual scheduler state (real plist
files or crontab entries). It shows ground truth.

If something changes the scheduler outside xcron, `plan` may say noop while
`status` shows drift or missing. When in doubt, use `status`.

## Default Backend

| Platform | Backend  |
|----------|----------|
| macOS    | launchd  |
| Linux    | cron     |

Override with `--backend launchd` or `--backend cron` if needed.

## Removing All Schedules for a Project

```sh
xcron prune
```

Removes all managed artifacts for the current project from the scheduler.
Does not touch any user-managed scheduler entries outside xcron's ownership.

## Safety Rules

- Do not edit plists, crontab entries, or xcron wrappers directly.
- Do not run `xcron apply` for multiple different projects concurrently.
- `prune` only removes what xcron owns. Unmanaged entries are preserved.
- `enabled: false` keeps the job defined in YAML but removes it from active
  scheduling. Prefer this over deleting a job you may want to restore later.

## Runtime Help And Hooks

Use runtime help instead of relying on copied command references:

```sh
xcron --help
xcron jobs --help
xcron jobs add --help
```

xcron also provides repo-local hook commands for Codex and Claude Code:

```sh
xcron hooks install
```

Those hooks are mainly for agent/session startup context and are not part of
normal day-to-day schedule editing, but they are expected to exist in projects
that use xcron heavily with coding agents.
