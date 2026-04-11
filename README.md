# xcron

`xcron` is a CLI-first schedule definition and reconciliation tool for
project-local recurring shell commands. A project keeps one YAML schedule
manifest under `resources/schedules/`, and `xcron` reconciles that desired state
to the native OS scheduler.

## Problem

Recurring local jobs are awkward to keep portable. macOS uses `launchd`, Linux
often uses `cron` or `systemd` timers, and hand-maintaining separate native
artifacts makes drift hard to detect.

`xcron` keeps the schedule source of truth in the repository and lets the OS
remain the executor. It is not a scheduler daemon, queue, workflow engine, or
process supervisor.

## Example Usage

Create or edit a manifest:

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

Operate from the project root:

```sh
uv run xcron validate
uv run xcron plan
uv run xcron apply
uv run xcron status
uv run xcron inspect sync_docs --output json
```

Manage jobs in the manifest:

```sh
uv run xcron jobs add cleanup_tmp --command ./bin/cleanup-tmp --every 1h
uv run xcron jobs disable cleanup_tmp
uv run xcron apply
```

Use `--backend launchd` or `--backend cron` to override automatic backend
selection.

## How It Works

`xcron` models three layers:

- desired state: one project manifest under `resources/schedules/`
- rendered native state: generated `launchd` plist or managed crontab entries
- actual machine state: what the native scheduler currently reports

Commands such as `plan`, `status`, `apply`, `inspect`, and `prune` compare or
reconcile those layers. `xcron` only modifies scheduler artifacts that carry its
ownership markers, so unmanaged plist and crontab entries stay outside its
scope.

## Tech Stack

- Python 3.9+
- Typer for the CLI
- Rich for human-facing text
- Pydantic for typed command responses and domain models
- PyYAML and jsonschema for schedule manifests
- python-toon for compact agent-facing output
- structlog for structured logging
- pytest for tests

The code is organized around thin CLI shells in `apps/cli/`, use-case actions in
`libs/actions/`, reusable services and scheduler backends in `libs/services/`,
domain models in `libs/domain/`, and packaged help, schemas, examples, and
skills in `resources/`.
