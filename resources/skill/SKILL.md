---
name: xcron-operator
description: >-
  Assist users in creating, applying, updating, inspecting, and removing
  per-project xcron schedules without exposing backend implementation details
  unless needed.
---

# xcron Operator Skill

## Purpose

Use this skill when the user wants help with:

- creating a new schedule manifest under `resources/schedules/`
- adding or editing scheduled jobs for one project
- validating or previewing schedule changes
- applying schedules to the local machine
- checking current deployed status
- inspecting one job
- removing a project's schedules from the system

The goal is to handle scheduling as a simple per-project workflow. Do not make
the user think in terms of plists, crontabs, wrapper scripts, or local state
directories unless debugging requires it.

## Core Model

Keep these rules explicit:

- `xcron` is a one-shot CLI, not a daemon
- each project owns its own manifests under `resources/schedules/`
- there is no central machine-wide schedule manifest
- users manage one project at a time
- `xcron` itself is not the scheduler
- after `apply`, the OS scheduler owns execution

Default backend selection:

- macOS: `launchd`
- Linux: `cron`

Only mention backend overrides if they matter for the task.

## Agent Behavior

Optimize for the user workflow, not internal architecture.

Default operating pattern:

1. locate the target project root
2. create or edit that project's manifest under `resources/schedules/`
3. run `xcron validate`
4. run `xcron plan`
5. run `xcron apply` if the user wants the change deployed
6. run `xcron status` or `xcron inspect <job-id>` when confirmation is useful

When the user asks to remove scheduling for a project, use:

```sh
xcron --project /path/to/project prune
```

When the user asks to update an existing schedule:

1. edit the selected manifest under `resources/schedules/`
2. run `validate`
3. run `plan`
4. run `apply`

## Manifest Guidance

The expected manifest location is:

```text
<project-root>/resources/schedules/<schedule-name>.yaml
```

Selection rule:

- if there is exactly one manifest in `resources/schedules/`, `xcron` can use it automatically
- if there are multiple manifests, pass `--schedule <name>`

Minimum useful shape:

```yaml
version: 1
project:
  id: my-project
defaults:
  working_dir: .
  shell: /bin/sh
jobs:
  - id: sync_docs
    schedule:
      cron: "*/15 * * * *"
    command: ./bin/sync-docs
```

Important constraints:

- `project.id` is required
- each `job.id` must be unique within the project
- v1 supports `schedule.cron` or constrained `schedule.every`
- `enabled: false` is the way to keep a job defined but not active
- log targets are not required in YAML

## Commands

Run inside the project:

```sh
xcron validate
xcron plan
xcron apply
xcron status
xcron inspect <job-id>
xcron prune
```

Or explicitly:

```sh
xcron --project /path/to/project validate
xcron --project /path/to/project plan
xcron --project /path/to/project apply
xcron --project /path/to/project status
xcron --project /path/to/project inspect <job-id>
xcron --project /path/to/project prune
```

When multiple manifests exist:

```sh
xcron --project /path/to/project --schedule default validate
xcron --project /path/to/project --schedule ops apply
```

Use `--backend launchd` or `--backend cron` only when the default is not the
right target.

## How To Help Users

### Creating a Schedule

If the user describes a recurring task:

1. translate it into one-shot command execution
2. add a job entry to the selected manifest under `resources/schedules/`
3. choose a stable `job.id`
4. use `cron` unless the user explicitly wants `every`
5. validate and show the plan before applying

### Updating a Schedule

If the user wants a change:

1. update the existing job entry
2. keep the same `job.id` unless they are intentionally replacing the job
3. run `validate`
4. run `plan`
5. apply if requested

### Disabling vs Removing

Use:

- `enabled: false` when the user wants to keep the job definition but stop execution
- delete the job from YAML when the user wants it gone from the desired state
- `prune` when the user wants to unschedule the whole project from the machine

### Inspecting

Use:

```sh
xcron status
xcron inspect <job-id>
```

Prefer `status` for project-wide drift or sync questions.
Prefer `inspect` for one-job debugging.

For machine-readable follow-up, prefer:

```sh
xcron status --output json
xcron inspect <job-id> --output json --fields backend,job,status
```

## Safety Rules

- never invent a central service or central schedule registry
- never tell the user to run multiple long-lived `xcron` instances
- do not expose machine-local derived state as if it were source-of-truth config
- preserve one project's independence from all others
- treat `apply` as the operation that reconciles the system to the manifest
- treat `prune` as the operation that removes one project's schedules from the system

## When To Mention Internals

Only surface backend details when the user asks or debugging requires them.

Examples:

- `launchd` vs `cron`
- generated log locations
- temporary testing overrides
- why `status` differs from `plan`

Even then, keep the explanation secondary to the user task.

## Testing Overrides

For safe local testing, these environment variables exist:

- `XCRON_STATE_ROOT`
- `XCRON_LAUNCH_AGENTS_DIR`
- `XCRON_LAUNCHCTL_DOMAIN`
- `XCRON_CRONTAB_PATH`
- `XCRON_MANAGE_LAUNCHCTL`
- `XCRON_MANAGE_CRONTAB`

Only use them when you need isolated test targets. Do not make them part of the
default user workflow.
