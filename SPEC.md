# xcron Specification

## Context

`xcron` is a tool for defining recurring command execution schedules in a
portable, repo-owned format and deploying those schedules to native operating
system schedulers.

The initial user context is:

- local development on macOS
- future deployment to Linux servers
- desire for one source of truth for schedule definitions
- desire to avoid coupling the schedule model directly to `launchd`, `cron`, or
  `systemd`
- desire to keep execution owned by the OS, not by a custom long-running
  scheduler daemon

The prototype will be implemented in Python for fast iteration and design
validation. Once the model, CLI, and backend behavior stabilize, the public
implementation will be rewritten in Go to ship as a single standalone binary.

Each project manages its own schedules independently. There is no central,
machine-wide schedule manifest.

## Problem Statement

Recurring task management is fragmented across platforms:

- macOS prefers `launchd`
- Linux commonly uses `cron` or `systemd` timers
- native scheduler formats are different and not pleasant to manage manually
- inspecting deployed state and reconciling drift is awkward

Teams that want portable recurring tasks usually end up with one of these
unpleasant choices:

- maintain separate scheduler definitions per platform
- build an app-owned scheduler daemon
- hand-edit OS-native config on each machine

`xcron` solves the narrow scheduling problem:

- define schedules once
- reconcile them to OS-native scheduler mechanisms
- inspect actual deployed machine state

`xcron` does not replace the OS scheduler. It compiles and reconciles desired
schedule state to the OS scheduler.

The desired state always comes from a single project's own manifest file. It
does not come from any cross-project aggregate configuration.

## Product Positioning

`xcron` is:

- a schedule definition and reconciliation tool
- a thin control plane over OS-native schedulers
- a CLI-first developer and operator tool

`xcron` is not:

- a job queue
- a workflow engine
- a distributed scheduler
- an orchestration system
- a general-purpose process supervisor
- a long-running task execution daemon

## Core Model

The model has three layers:

1. Desired state
   - stored in one project-local manifest under `resources/schedules/`
2. Rendered native state
   - generated backend-specific artifacts such as launchd plists or managed
     crontab entries
3. Actual machine state
   - what is currently installed, enabled, and visible in the local scheduler

`xcron` is responsible for making actual machine state converge toward desired
state for the managed jobs it owns.

`xcron` does not own any central cross-project desired state layer.

## Goals

- One portable, human-editable schedule definition format
- Native OS execution via `launchd`, `cron`, and later optionally `systemd`
- Idempotent apply behavior
- Strong visibility into actual deployed state
- Safe ownership boundaries so unmanaged native scheduler entries are preserved
- Predictable logs, env handling, and working directory handling
- Small conceptual surface area
- Prototype quickly in Python, then reimplement in Go once stable

## Non-Goals

- Running jobs inside the `xcron` process
- Building a cross-platform scheduler daemon
- Supporting every feature of every native scheduler
- Distributed coordination between machines
- Queue semantics, retries, backoff, or workflow chaining
- Dynamic runtime task creation from external APIs in v1
- Cloud scheduler support in v1

## Design Principles

- YAML is the source of truth
- The source of truth is always one project's own manifest under `resources/schedules/`
- The OS remains the executor
- Generated native artifacts are disposable
- Only managed artifacts with an `xcron` ownership marker may be modified
- `status` and `inspect` are first-class features, not afterthoughts
- Behavior should be explicit and unsurprising
- Cross-platform portability matters more than exposing backend-specific bells
  and whistles
- Architecture should remain modular and consistent across the Python prototype
  and Go implementation
- No central schedule manifest is allowed

## Repository Structure

The project should use a consistent top-level structure:

- `./apps/`
  - runnable and deployable thin shells
  - for `xcron`, this primarily means CLI commands
  - in other systems, this could include REST API servers, web apps, queue
    workers, or other executable entrypoints
- `./libs/`
  - reusable application code used by apps
  - includes actions, services, helpers, domain logic, renderers, planners,
    backends, and supporting utilities
- `./resources/`
  - static and semi-static assets required by the system
  - includes data files, configs, schemas, templates, migrations, and similar
    resources
- `./docs/`
  - human-facing documentation
  - includes the specification, design notes, implementation notes, and user
    documentation

This layout is required for both the Python prototype and the later Go rewrite,
adapted to the conventions of each language ecosystem where necessary.

## Code Architecture

The codebase should be organized around three major groups of building blocks.

### Actions

Actions are at the heart of the architecture.

They can be thought of as system use cases. They are invoked by thin shells such
as CLI commands or future API/web entrypoints. An action coordinates one or more
services to complete a meaningful unit of work.

Examples in `xcron` include:

- validate configuration
- compute a plan
- apply desired state
- inspect deployed state
- prune unmanaged drift within owned scope

Action responsibilities:

- define the use-case boundary
- coordinate services
- perform input-level orchestration
- handle access control if relevant
- centralize use-case logging and audit-friendly behavior
- return structured results suitable for thin-shell presentation

Actions should not contain low-level backend integration details inline when
those details belong in services.

### Services

Services are context-independent providers of capabilities.

They encapsulate integrations with:

- filesystem
- YAML parsing and schema validation
- scheduler backends such as `launchd` and `cron`
- rendering engines
- hashing and drift detection
- locking
- logging adapters
- shell and subprocess execution

Services may also directly implement reusable features that do not belong to a
particular entrypoint.

Service responsibilities:

- expose reusable capabilities
- remain independent of CLI or other delivery context
- isolate third-party tool and OS integration logic
- keep side effects explicit and testable

### Thin Shells

Thin shells translate external inputs into action parameters and invoke actions
with the required context.

For `xcron`, thin shells are primarily CLI commands in `./apps/`.

In broader systems, thin shells could also include:

- web app controllers
- REST API controllers
- queue workers
- other executable adapters

Thin shell responsibilities:

- parse input
- construct action parameters
- provide execution context
- call actions
- format and present outputs

Thin shells should stay thin. They should not implement core scheduling logic,
backend reconciliation logic, or domain rules.

## Architectural Expectations

- CLI commands live under `./apps/` and should be minimal shells around actions
- Core use cases live as actions under `./libs/`
- Backend integrations and reusable capabilities live as services under
  `./libs/`
- Config schemas, templates, example YAML files, and similar assets live under
  `./resources/`
- Human documentation lives under `./docs/`
- The Python prototype should follow this structure instead of growing as a set
  of scripts
- The Go rewrite should preserve the same architectural boundaries even if the
  package layout differs in detail

## User Stories

- As a developer, I want to define recurring commands in one file and apply
  them on macOS without hand-writing plists.
- As an operator, I want to apply the same schedule definitions on Linux
  without rewriting them as raw cron entries.
- As a maintainer, I want to know whether deployed schedules match the YAML
  definitions.
- As a debugger, I want to inspect the actual native scheduler artifact and the
  exact command that will run.
- As a cautious user, I want dry-run planning before any machine changes are
  applied.

## Initial Backend Strategy

Prototype and likely public v1 backend support:

- macOS: `launchd`
- Linux: `cron`

Possible later backend support:

- Linux: `systemd` timers

Reasoning:

- `launchd` is the native and preferred scheduler on macOS
- `cron` is the lowest-friction Linux target for portability
- `systemd` timers are desirable later, but add more mapping complexity and a
  somewhat different capability model

## Configuration Format

The source of truth is one per-project YAML manifest under
`resources/schedules/<schedule-name>.yaml`.

Each project owns its own manifests under `resources/schedules/`. `xcron` must
not require or invent any central schedule file spanning multiple projects.

Example:

```yaml
version: 1

project:
  id: myapp

defaults:
  working_dir: .
  shell: /bin/zsh
  timezone: Europe/Warsaw
  env:
    PATH: /usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin
    APP_ENV: production

jobs:
  - id: sync_invoices
    description: Pull invoice data from provider
    enabled: true
    schedule:
      cron: "*/15 * * * *"
    command: ./bin/sync-invoices
    env:
      LOG_LEVEL: info
    overlap: forbid

  - id: cleanup_tmp
    enabled: true
    schedule:
      cron: "0 3 * * *"
    command: ./bin/cleanup-tmp

  - id: refresh_cache
    enabled: false
    schedule:
      every: 10m
    command: ./bin/refresh-cache
```

## Configuration Semantics

Expected v1 fields:

- `version`
- `project`
- `project.id`
- `defaults`
- `defaults.working_dir`
- `defaults.shell`
- `defaults.timezone`
- `defaults.env`
- `jobs[]`
- `jobs[].id`
- `jobs[].description`
- `jobs[].enabled`
- `jobs[].schedule`
- `jobs[].schedule.cron`
- `jobs[].schedule.every`
- `jobs[].command`
- `jobs[].working_dir`
- `jobs[].shell`
- `jobs[].env`
- `jobs[].overlap`

Rules:

- `project.id` is required
- `id` must be stable and unique
- exactly one of `schedule.cron` or `schedule.every` must be set
- commands must be one-shot commands
- `enabled: false` means desired state is present but should not be active
- defaults are merged into job-specific configuration
- `overlap` is advisory policy in the source model, implemented via wrappers or
  backend capabilities where possible
- `working_dir: .` is resolved relative to the project root

## Project Scope

`xcron` operates on one project at a time.

Default behavior:

- `xcron` run inside a project directory uses the selected manifest under
  `resources/schedules/`
- `xcron --project /path/to/project ...` uses the specified project
- if there is exactly one manifest under `resources/schedules/`, `xcron` may
  auto-select it
- if there are multiple manifests, the user should pass `--schedule <name>`

Project-scoped behavior is the default for:

- `validate`
- `plan`
- `apply`
- `status`
- `inspect`
- `prune`

Machine-wide discovery or reporting may exist later as convenience behavior,
but it must never become a required configuration layer and must never replace
the per-project manifest as the source of truth.

## Execution Model

Each job is a one-shot command launched by the OS scheduler at schedule time.

`xcron` may generate a small wrapper per job in order to standardize:

- environment variables
- working directory
- shell invocation
- stdout and stderr logging
- overlap policy enforcement
- embedded metadata such as config hash and job id

This wrapper is still a thin execution shim. It is not a scheduler.

The scheduler backend always executes artifacts derived from one project's own
manifest. It never executes from a central xcron-managed job catalog.

## Ownership Model

`xcron` must only modify artifacts it owns.

Examples:

- `launchd` labels prefixed with `dev.xcron.` or another explicit prefix
- managed plist files in a known directory
- managed crontab block surrounded by begin/end markers
- generated wrapper scripts in an `xcron` state directory

This protects user-managed scheduler entries from accidental edits.

## Command Surface

Expected prototype CLI:

- `xcron validate`
- `xcron plan`
- `xcron apply`
- `xcron status`
- `xcron inspect <job-id>`
- `xcron prune`

### validate

Checks:

- YAML syntax
- schema validity
- schedule validity
- duplicate ids
- invalid paths or unsupported field combinations

### plan

Shows what would change without mutating machine state.

Typical outputs:

- create
- update
- remove
- enable
- disable
- no-op

### apply

Converges managed machine state toward desired state.

Requirements:

- idempotent
- safe on repeated runs
- preserve unmanaged native scheduler entries
- write explicit artifacts before activation where possible

### status

Shows desired vs actual state for all managed jobs in the current project.

Typical states:

- `ok`
- `missing`
- `drift`
- `disabled`
- `extra`
- `error`

### inspect

Shows detailed information for one job, including:

- normalized desired job definition
- selected backend
- generated native artifact path
- generated wrapper path if any
- native scheduler status
- relevant logs paths
- native config snippet or raw rendered artifact

### prune

Removes managed artifacts for the current project that no longer exist in that
project's YAML desired state.

## Drift Detection

Drift detection is a first-class capability.

The tool should detect when the actual deployed scheduler artifact differs from
the YAML desired definition.

Likely strategy:

- normalize job definition
- compute a stable hash
- embed that hash in generated artifact metadata or wrapper headers
- compare desired hash to deployed hash during `status`, `inspect`, and `apply`

This avoids unreliable text diffing against backend-specific generated files.

## Backend Mapping

### launchd

Expected mapping:

- `schedule.cron` -> `StartCalendarInterval`
- `schedule.every` -> `StartInterval`
- command -> `ProgramArguments` or shell invocation wrapper
- logs -> `StandardOutPath` and `StandardErrorPath`
- activation -> `launchctl bootstrap`, `enable`, `bootout`, `disable`,
  `kickstart`, or the modern equivalent flow selected during implementation

Notes:

- `launchd` does not use cron syntax natively
- some cron expressions may need translation constraints
- timezone semantics need careful treatment

### cron

Expected mapping:

- `schedule.cron` -> native crontab line
- `schedule.every` -> translated into cron-compatible cadence when possible, or
  rejected in v1 if translation is ambiguous
- command -> wrapper invocation
- ownership -> managed block within user crontab

Notes:

- cron is simple but has limited expressiveness
- direct support for arbitrary interval semantics is weaker than `launchd`

## Logging Expectations

Every managed job should have explicit log destinations.

Goals:

- predictable stdout and stderr capture
- backend-independent user experience
- easy debugging from `inspect`

Default bias:

- one stdout log and one stderr log per job in an `xcron` state or logs
  directory

Projects should not be required to define log targets in schedule manifests in
v1. `xcron` assigns deterministic default log paths automatically.

## Overlap Policy

V1 should support at least:

- `allow`
- `forbid`

`forbid` means a second invocation should not start if the previous invocation
is still running.

Likely implementation:

- lock file or OS lock wrapper

This is not queueing. Missed or skipped executions are not replayed in v1.

## State Storage

Prototype likely requires a small local state directory for generated artifacts.

Possible contents:

- generated wrappers
- rendered backend artifacts
- hash metadata
- last apply metadata
- logs

The exact location is to be decided, but should be explicit and inspectable.

Examples:

- `~/.local/state/xcron`
- `~/Library/Application Support/xcron`

Local state is derived state only. It is not configuration.

It must be partitioned by `project.id` to prevent collisions between multiple
projects on the same machine.

Possible partitioned contents:

- wrappers under a project-specific directory
- logs under a project-specific directory
- metadata and hashes under a project-specific directory
- rendered artifacts or cached render outputs under a project-specific
  directory

## Prototype Implementation Plan

Language: Python

Reasoning:

- fastest path to iterate on schema and behavior
- easy YAML parsing
- easy subprocess and file work
- fast feedback while refining backend mapping

Python prototype responsibilities:

- define and validate the schedule spec
- prove backend mapping decisions
- prove status and drift detection model
- expose the final CLI shape
- validate that the `apps` / `libs` / `resources` / `docs` structure is
  practical in real implementation

## Public Implementation Plan

Language: Go

Reasoning:

- single small binary for users
- simple distribution for macOS and Linux
- no dependency on local Python environment
- good long-term fit for infra CLI tooling

The Go implementation should preserve the validated external interface from the
Python prototype as much as practical:

- YAML schema
- command names
- behavior of `plan`, `apply`, `status`, and `inspect`
- ownership and drift model
- architectural separation between thin shells, actions, and services

## Success Criteria

The prototype is successful when:

- a user can define schedules in one project's own manifest under `resources/schedules/`
- the same definitions can be applied on macOS and Linux
- the tool can clearly tell whether deployed state matches desired state
- generated artifacts are understandable and inspectable
- repeated `apply` runs are safe and idempotent
- backend ownership boundaries are safe
- the design feels stable enough to justify a Go rewrite

## Open Questions

- Should Linux v1 target only `cron`, or support `systemd` timers from the
  start?
- What exact subset of cron syntax should be considered portable?
- Should `every` be part of the public model in v1, given backend differences?
- What is the exact state directory layout?
- How should timezone be modeled per job vs globally?
- Should commands be expressed as a shell string, argv list, or both?
- How much native backend detail should `inspect` expose by default?
- What should be the default ownership prefix for labels, files, and blocks?

## Summary

`xcron` is a YAML-driven schedule reconciliation tool. It owns the schedule
definition layer, while the OS owns execution. The Python prototype exists to
stabilize the model and operational semantics. The Go implementation exists to
ship the same model as a single portable binary for public use.

The source of truth is always one project's own manifest under
`resources/schedules/`. There is no central schedule manifest.
