# xcron Job CLI Management Plan

## Goal

Add CLI-first job management operations so operators and agents can manage
individual jobs inside one schedule manifest without editing YAML by hand, while
preserving the existing `xcron` model:

- YAML remains the source of truth
- backend state is still changed only through `plan` and `apply`
- thin shell -> action -> service boundaries remain intact

This plan belongs to epic `xcron-iip`.

## Problem Restatement

Today `xcron` can only reconcile an already-existing manifest. It cannot:

- add a new job entry
- remove a job entry
- change a job's command or schedule
- enable or disable a job through CLI operations
- list or inspect manifest jobs without dropping into raw YAML

That makes the tool weaker for agent automation than `bd`, which exposes
explicit lifecycle commands for individual tasks and epics.

Separately, `xcron` already has root and per-command `--help` through
`argparse`, but that behavior is implicit and shallow. The contract is not
formalized, not tested directly, and will become more important once nested
job-management commands exist.

## Constraints

- YAML manifest files under `resources/schedules/` remain the only desired-state
  source.
- New job commands must edit the manifest on disk, not the native scheduler.
- Existing reconciliation commands (`validate`, `plan`, `apply`, `status`,
  `inspect`, `prune`) must keep their current meaning.
- Architecture from `SPEC.md` and `docs/dev/architecture.md` must hold:
  shells stay thin, actions coordinate use cases, services handle I/O.
- The tool currently uses `PyYAML`, not a round-trip YAML editor.
- Global options such as `--project` and `--schedule` should continue to select
  the target manifest.

## Current Codebase Observations

- Root CLI lives in `apps/cli/main.py` and uses `argparse` subparsers.
- Manifest loading/parsing lives in `libs/services/config_loader.py`.
- Validation and normalization live in `libs/actions/validate_project.py`,
  `libs/domain/models.py`, and `libs/domain/normalization.py`.
- There is no manifest-writing service yet.
- Help already works for:
  - `xcron --help`
  - `xcron inspect --help`
  but there is no explicit contract or coverage for nested command groups.

## Proposed UX

Introduce a `jobs` command group for explicit manifest editing and inspection.

### Read Operations

- `xcron jobs list`
- `xcron jobs show <job-id>`

These operate on the selected manifest only and do not touch backend state.

### Write Operations

- `xcron jobs add <job-id> --command <cmd> (--cron <expr> | --every <interval>)`
- `xcron jobs remove <job-id>`
- `xcron jobs enable <job-id>`
- `xcron jobs disable <job-id>`
- `xcron jobs update <job-id> [--command ...] [--cron ... | --every ...] [--description ...] [--working-dir ...] [--shell ...] [--overlap ...] [--env KEY=VALUE ...] [--clear-env]`

This keeps the command set explicit and agent-friendly instead of relying on one
opaque mutation command.

### Help Contract

Help should be intentionally supported at three layers:

- root: `xcron --help`
- command group: `xcron jobs --help`
- leaf command: `xcron jobs add --help`

The help output should describe:

- what the command edits or reads
- whether it changes YAML only or scheduler state
- required arguments
- schedule selection behavior via `--schedule`

## Data and Write Model

Add a manifest-editing service that:

1. loads the selected manifest document
2. mutates the raw YAML mapping in memory
3. validates obvious structural preconditions for the edit
4. writes the updated YAML back to disk
5. returns enough structured metadata for the shell to confirm the change

Likely new layers:

- service:
  - manifest read/write helpers
  - job mutation helpers on raw manifest mappings
- actions:
  - `list_jobs`
  - `show_job`
  - `add_job`
  - `remove_job`
  - `update_job`
  - `set_job_enabled`
- CLI shells:
  - nested `jobs` subcommands

After a write, the action should run validation against the updated manifest
before returning success. If validation fails, the action should not leave a bad
manifest on disk.

## Important Design Decision

Use manifest-first operations, not backend-first operations.

That means:

- `xcron jobs add ...` edits YAML only
- `xcron apply` is still the step that reconciles to `launchd` or `cron`

This preserves the core `xcron` contract and avoids surprising partial state.

## YAML Rewrite Tradeoff

The current stack uses `PyYAML`, so rewriting the manifest may change formatting
or comments.

Pragmatic v1 options:

1. Stay with `PyYAML` and accept normalized rewrites.
2. Introduce a round-trip YAML library later if comment preservation becomes a
   hard requirement.

Recommendation: v1 should stay with the existing stack and document that
job-editing commands may normalize YAML formatting.

## Task Breakdown

1. Define the command contract and manifest-editing model.
2. Implement manifest read/write and atomic update actions for job operations.
3. Add nested `jobs` CLI shells and root/group/leaf help coverage.
4. Update user and developer docs for the new job-management workflow.

## Risks

### YAML rewrite churn

Manifest edits may reformat files more than users expect.

Mitigation:

- keep writes deterministic
- document the behavior
- test resulting YAML shape, not formatting trivia

### Ambiguous mutation surface

If `update` tries to do everything, the CLI becomes hard to learn.

Mitigation:

- keep explicit commands for add/remove/enable/disable
- reserve `update` for field changes

### Help regressions with nested parsers

Adding a `jobs` group can make root help noisy or confusing.

Mitigation:

- test root, group, and leaf help explicitly
- keep descriptions short and specific

## Open Questions

- Do we want `jobs update` to support partial env mutation, or only full replace
  plus `--clear-env` in v1?
- Do we want `jobs list` / `jobs show` to remain text-only for now, or should
  they anticipate a future structured-output mode?
- Is normalized YAML rewrite acceptable for v1, or should comment preservation
  be treated as a hard requirement before implementation begins?
