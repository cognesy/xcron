# xcron User Guide

`xcron` manages one project schedule manifest under `resources/schedules/`
against a native OS scheduler.

Core rules:

- each project owns its own manifests under `resources/schedules/`
- there is no central machine-wide schedule manifest
- native schedulers remain the executors
- `xcron` owns only the artifacts it generates

## qaman Pilot Workflow

This repo now has a minimal `qaman` setup for deterministic core quality work.

Use it for:

- readiness checks: `qa doctor`
- deterministic default verification: `qa profile run default`
- baseline/current progress measurement: `qa snap store` and `qa progress`

Current pilot scope:

- `default` wraps the deterministic core lane in `./scripts/verify-core.sh`
- explicit scheduler integration remains outside the default `qaman` lane

Typical flow:

```sh
qa doctor
qa profile run default --format json
qa snap store --format json
# make changes
qa progress --against latest --format text
```

Use `qa doctor --profile default` when you want readiness diagnostics plus a
real execution probe of the default profile.

## Manifest

The prototype expects schedule manifests under:

```text
<project-root>/resources/schedules/<schedule-name>.yaml
```

If a project has exactly one manifest there, `xcron` can auto-select it.
If a project has multiple manifests, use `--schedule <name>`.

Example:

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
  - id: cleanup_tmp
    enabled: false
    schedule:
      cron: "0 3 * * *"
    command: ./bin/cleanup-tmp
```

Sample manifests live under `resources/examples/*/resources/schedules/`.

## Commands

Run inside the project or pass `--project /path/to/project`.

```sh
xcron validate
xcron plan
xcron apply
xcron status
xcron inspect sync_docs
xcron jobs list
xcron jobs show sync_docs
xcron prune
```

If the project has multiple schedule files:

```sh
xcron --schedule default validate
xcron --schedule ops plan
xcron --schedule ops apply
```

Use `--backend launchd` or `--backend cron` to override the platform default.

Default backend selection:

- macOS: `launchd`
- Linux: `cron`

## Jobs

`xcron jobs ...` manages individual job entries inside the selected manifest.

Important boundary:

- `xcron jobs ...` edits YAML only
- `xcron apply` is still the step that reconciles scheduler state

Available commands:

```sh
xcron jobs list
xcron jobs show <job-id>
xcron jobs add <job-id> --command <cmd> --cron "*/15 * * * *"
xcron jobs add <job-id> --command <cmd> --every 1h
xcron jobs update <job-id> --command <cmd>
xcron jobs enable <job-id>
xcron jobs disable <job-id>
xcron jobs remove <job-id>
```

Examples:

```sh
xcron jobs add cleanup_tmp --command ./bin/cleanup-tmp --every 1h --disabled
xcron jobs update cleanup_tmp --cron "0 * * * *" --clear-env
xcron jobs enable cleanup_tmp
xcron apply
```

The CLI exposes help at three levels:

```sh
xcron --help
xcron jobs --help
xcron jobs add --help
```

## Plan vs Status

`plan` and `status` answer different questions.

**`plan`** compares your YAML against xcron's own local records — the
`project-state.json` file written during the last `apply`. It shows what
`apply` would do given those records. It is fast and works without touching
the scheduler.

**`status`** compares your YAML against actual deployed scheduler state —
real plist files, real crontab entries. It reflects ground truth.

If the scheduler is changed outside xcron (manual plist edit, `launchctl
bootout`, external crontab edit), the two commands disagree:

```
# a plist was manually removed

xcron plan    → noop    (xcron's records still show it as deployed)
xcron status  → missing (the actual file is gone)
```

Running `apply` after `plan` shows noop would leave the scheduler broken.
Running `apply` after `status` shows missing would reinstall the job.

Practical rule:

- `plan` — preview what `apply` will do given xcron's current records
- `status` — check whether actual deployed state matches the manifest
- `apply` — repair the backend after `status` reveals drift

## Status

`xcron status` is an operator-facing desired-vs-actual view for the current
project.

Typical states:

- `ok` - desired definition and deployed backend state match
- `missing` - desired job is not currently installed in the backend
- `drift` - the deployed job exists but differs from desired state
- `disabled` - the job is intentionally disabled in the desired manifest
- `extra` - a managed backend artifact exists without a matching desired job
- `error` - backend inspection failed

Example:

```text
backend: cron
ok       example-basic.sync_docs    desired definition and actual backend state are aligned
disabled example-basic.cleanup_tmp  job is disabled in desired state
```

## Inspect

`xcron inspect <job-id>` shows one job in more depth. The current prototype
surfaces:

- normalized desired fields such as schedule, enabled state, command,
  working directory, shell, and overlap policy
- deployed backend fields such as artifact path, wrapper path, stdout/stderr
  log paths, hashes, and backend-loaded/enabled state where applicable
- backend-native raw detail:
  - cron: managed raw entry
  - launchd: raw plist content and `launchctl print` output when available

Example:

```text
backend: cron
desired:
  qualified_id: example-basic.sync_docs
  schedule: cron=*/15 * * * *
  command: ./bin/sync-docs
deployed:
  artifact_path: /tmp/crontab.txt
  wrapper_path: /tmp/state/projects/example-basic/wrappers/example-basic.sync_docs.sh
raw_entry:
*/15 * * * * /tmp/state/projects/example-basic/wrappers/example-basic.sync_docs.sh
```

`xcron jobs show <job-id>` is the manifest-side companion to `inspect`. It
shows the job as defined in YAML without querying `launchd` or `cron`.

## Runtime Behavior

Managed derived state is stored machine-locally and partitioned by `project.id`.

`xcron` manages:

- wrapper scripts
- stdout/stderr logs
- per-project deployment metadata
- backend-native artifacts such as plists or managed cron blocks

Projects do not need to define log targets in YAML. The tool assigns default
paths automatically.

## Safe Overrides For Testing

The CLI supports environment overrides that are useful for local testing:

- `XCRON_STATE_ROOT`
- `XCRON_LAUNCH_AGENTS_DIR`
- `XCRON_LAUNCHCTL_DOMAIN`
- `XCRON_CRONTAB_PATH`
- `XCRON_MANAGE_LAUNCHCTL`
- `XCRON_MANAGE_CRONTAB`

These make it possible to exercise the prototype without touching normal system
paths.

## Explicit Integration Checks

## Deterministic Core Verification

The deterministic core verification lane for `xcron` is:

```sh
./scripts/verify-core.sh
```

Today that wrapper runs the repo's safe default:

```sh
uv run pytest
```

This lane is intended for:

- routine local verification
- agent-safe default checks
- future `qaman` default profile integration

It stays fast and safe and does not mutate the host scheduler.

## Explicit Integration Checks

Real scheduler integration runs are explicit-only and outside the deterministic
core lane.

macOS `launchd` on the host:

```sh
XCRON_RUN_LAUNCHD_IT=1 XCRON_LOG_FORMAT=json XCRON_LOG_LEVEL=INFO uv run pytest tests/integration/launchd_real_it.py -s
```

Linux `cron` in Docker/Colima:

```sh
./tests/integration/run_cron_it.sh
```
