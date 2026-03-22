# xcron Cheat Sheet

## Basics

- Manifest location: `resources/schedules/<name>.yaml`
- Default backend:
  - macOS: `launchd`
  - Linux: `cron`
- Run from the project root, or pass `--project /path/to/project`

## Schedule File Format

Minimal manifest shape:

```yaml
version: 1
project:
  id: example-basic
defaults:
  working_dir: .
  shell: /bin/sh
jobs:
  - id: sync_docs
    schedule:
      cron: "*/15 * * * *"
    command: ./bin/sync-docs
```

Common fields:

- `version`: manifest version, currently `1`
- `project.id`: required project identifier
- `defaults.working_dir`: default working directory for jobs
- `defaults.shell`: default shell for job execution
- `jobs[].id`: required job identifier
- `jobs[].command`: shell command to run
- `jobs[].enabled`: optional, defaults to `true`
- `jobs[].description`: optional human description
- `jobs[].schedule.cron`: native cron string
- `jobs[].schedule.every`: portable interval string like `15m`, `1h`, `1d`

Each job must define exactly one schedule form: `cron` or `every`.

## Core Commands

```sh
xcron validate
xcron plan
xcron apply
xcron status
xcron inspect <job-id>
xcron jobs list
xcron jobs show <job-id>
xcron jobs add <job-id> --command <cmd> --cron "*/15 * * * *"
xcron jobs update <job-id> --command <cmd>
xcron jobs enable <job-id>
xcron jobs disable <job-id>
xcron jobs remove <job-id>
xcron prune
```

Select a specific schedule file:

```sh
xcron --schedule default validate
xcron --schedule ops apply
```

Override the backend:

```sh
xcron --backend cron plan
xcron --backend launchd status
```

## Job Editing

- `xcron jobs ...` edits the selected manifest YAML only
- `xcron apply` reconciles the edited manifest to the scheduler backend

Useful help entry points:

```sh
xcron --help
xcron jobs --help
xcron jobs add --help
```

## Status Meanings

- `ok`: desired definition and deployed backend state match
- `missing`: desired job is not installed in the backend
- `drift`: deployed job exists but differs from desired state
- `disabled`: job is intentionally disabled in YAML
- `extra`: managed backend artifact exists without a matching desired job
- `error`: backend inspection failed

## Inspect Output

`xcron inspect <job-id>` shows:

- normalized desired fields: schedule, enabled, command, working dir, shell, overlap
- deployed fields: hashes, artifact path, wrapper path, stdout/stderr logs
- backend-native raw detail:
  - cron: managed raw entry
  - launchd: raw plist and `launchctl print` output when available

## Useful Env Overrides

```sh
XCRON_STATE_ROOT=/tmp/xcron-state
XCRON_LAUNCH_AGENTS_DIR=/tmp/LaunchAgents
XCRON_LAUNCHCTL_DOMAIN=gui/$(id -u)
XCRON_CRONTAB_PATH=/tmp/crontab.txt
XCRON_MANAGE_LAUNCHCTL=0
XCRON_MANAGE_CRONTAB=0
```

## Real Integration Runs

Host macOS `launchd`:

```sh
XCRON_RUN_LAUNCHD_IT=1 XCRON_LOG_FORMAT=json XCRON_LOG_LEVEL=INFO uv run pytest tests/integration/launchd_real_it.py -s
```

Linux `cron` in Docker/Colima:

```sh
./tests/integration/run_cron_it.sh
```
