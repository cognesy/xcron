# xcron v1 Prototype Plan

## Goal

Build the first working `xcron` prototype in Python as a per-project,
YAML-driven schedule reconciliation CLI.

The prototype must:

- manage one project's schedules independently of all others
- use the project's own schedule manifests under `resources/schedules/` as the only source of truth
- deploy jobs to native OS schedulers rather than running them in-process
- support macOS `launchd` first and Linux `cron` second
- expose a stable model and command surface suitable for a later Go rewrite

## Current State

The repository currently contains:

- a high-level product and design spec in `SPEC.md`
- a fresh `bd` issue database
- no implementation code
- no project skeleton under `apps/`, `libs/`, `resources/`, or `docs/`

## Constraints

- No central schedule file spanning multiple projects is allowed.
- Each project must be deployable and inspectable independently.
- Native OS schedulers remain the runtime executors.
- The Python prototype must follow the intended production architecture rather
  than becoming a collection of scripts.
- The external model should be stable enough to reimplement in Go with minimal
  user-visible change.
- Generated state may exist machine-locally, but project configuration must
  remain repo-local.

## Desired Operating Model

Per-project workflow:

1. A project contains one or more manifests under `resources/schedules/`.
2. The user runs `xcron` within that project, or points `xcron` at the project
   path.
3. `xcron` validates the manifest, computes desired state, renders native
   scheduler artifacts, and applies them.
4. `xcron status` and `xcron inspect` operate in the current project scope by
   default.

Machine-local state exists only as derived runtime state, such as:

- rendered artifacts
- generated wrappers
- logs
- deployment hashes and metadata

This state is not configuration and must never become a central source of
schedule truth.

The manifest convention for the prototype is project-local manifests under
`resources/schedules/`, with explicit schedule-name selection when more than
one manifest exists.

## Architectural Approach

The prototype should implement the repository and code structure already defined
in the spec.

Top-level structure:

- `apps/`
  - CLI entrypoints and command adapters
- `libs/`
  - actions, services, domain models, planners, renderers, backend adapters,
    and infrastructure helpers
- `resources/`
  - schemas, templates, sample configs, and other static assets
- `docs/`
  - design and user/developer documentation

Application building blocks:

- thin shells in `apps/`
  - parse CLI input
  - construct action parameters
  - invoke actions
  - format results
- actions in `libs/`
  - represent use cases such as validate, plan, apply, status, inspect, prune
- services in `libs/`
  - implement filesystem, YAML, hashing, wrapper generation, backend
    integrations, state store access, and logging support

## Proposed Python Package Layout

```text
apps/
  cli/
    main.py
    commands/
      validate.py
      plan.py
      apply.py
      status.py
      inspect.py
      prune.py

libs/
  actions/
    validate_project.py
    plan_project.py
    apply_project.py
    status_project.py
    inspect_job.py
    prune_project.py
  domain/
    models.py
    normalization.py
    diffing.py
  services/
    config_loader.py
    schema_validator.py
    state_store.py
    wrapper_renderer.py
    hash_service.py
    logging_paths.py
    backends/
      launchd_service.py
      cron_service.py
  infra/
    fs.py
    process.py
    clock.py

resources/
  schemas/
    schedules.schema.yaml
  templates/
    wrapper.sh.j2
    launchd.plist.j2

docs/
  dev/
    plans/
  user/
```

The exact Python packaging details may shift slightly during implementation, but
the action/service/thin-shell boundary should remain intact.

## Functional Scope for v1

### Required

- per-project manifest discovery
- schema validation
- normalized in-memory job model
- deterministic job identity generation
- dry-run planning
- idempotent apply behavior
- macOS `launchd` backend
- Linux `cron` backend
- managed wrapper generation
- managed log path generation
- drift detection through stable hashes
- `status`
- `inspect`
- `prune`

### Explicitly Deferred

- central multi-project config
- distributed scheduling
- retries and backoff
- job history database beyond minimal deployment metadata
- `systemd` timers
- API server
- web UI
- queue semantics

## Key Design Decisions

### 1. Project Identity

Every manifest must define a stable `project.id`.

This project identity becomes part of:

- native labels
- wrapper file names
- local state directory layout
- log file layout
- deployment metadata keys

This avoids collisions when many projects on one machine each manage their own
schedules.

### 2. Managed Local State

`xcron` needs a local state directory for derived artifacts only.

Suggested prototype default:

- `~/.local/state/xcron/` on Linux
- `~/Library/Application Support/xcron/` or equivalent on macOS

Managed local state should be partitioned by project id.

This local state is not a schedule source of truth and must never act as a
central manifest layer.

### 3. Logs

Projects should not be forced to define log targets in YAML in v1.

Instead:

- `xcron` assigns deterministic default stdout and stderr log files per
  project/job
- `inspect` shows those paths
- optional overrides can be added later if the model needs them

### 4. Wrappers

The scheduler should launch managed wrapper scripts rather than raw commands
directly.

Wrappers normalize:

- working directory
- environment
- shell invocation
- log redirection
- overlap locking
- embedded config hash metadata

This keeps `launchd` and `cron` behavior more consistent.

### 5. Drift Detection

Each normalized job definition should produce a stable hash that can be embedded
in generated artifacts and compared during `status`, `inspect`, and `apply`.

## Delivery Phases

### Phase 1: Foundation

- align the spec with the final per-project constraints
- create the repository skeleton
- define the schema and normalized domain model
- decide and document local state directory rules

### Phase 2: Core Engine

- implement config loading and validation
- implement normalization and hashing
- implement planning and diffing
- implement wrapper generation and log path rules

### Phase 3: Backends

- implement `launchd` rendering and apply/status/inspect/prune support
- implement `cron` rendering and apply/status/inspect/prune support

### Phase 4: CLI and UX

- implement thin CLI shells for all actions
- standardize output for plan/status/inspect
- add clear error handling and dry-run behavior

### Phase 5: Verification and Docs

- add tests across schema, diffing, and backends
- add sample manifests and user docs
- document the future Go rewrite contract

## Risks

### Backend Model Mismatch

`launchd` and `cron` do not share the same feature model. In particular,
portable support for interval semantics and timezone behavior may require
careful narrowing of the public spec.

### Scope Creep

It is easy to drift from "portable schedule reconciliation" into "scheduler
daemon" or "job orchestration". The task backlog must preserve the narrow scope.

### Project State Leakage

If local state is not clearly partitioned by project id, one project's deployed
artifacts or logs could interfere with another's.

### Incomplete Inspectability

If metadata and hashes are not embedded consistently, `status` and `inspect`
will be weak and difficult to trust.

## Open Questions

- Should manifest selection remain stem-based under `resources/schedules/`, or
  should explicit manifest paths also be accepted?
- Should `schedule.every` be part of public v1, or deferred until backend
  support is more uniform?
- What is the exact portable cron subset for v1?
- What exact local state root should be used on macOS and Linux?
- Should optional log overrides be included in the schema now but undocumented,
  or omitted entirely until needed?

## Proposed Task Breakdown

1. Align and finalize the design spec for the per-project model and repository
   structure.
2. Scaffold the repository with the required `apps/`, `libs/`, `resources/`,
   and `docs/` layout plus Python project setup.
3. Define the manifest schema, normalized domain model, and deterministic job
   identity rules.
4. Implement validation, normalization, and stable hash generation actions and
   services.
5. Implement the planning and diff engine for desired vs actual managed state.
6. Implement local state store, wrapper generation, log path generation, and
   overlap-lock support.
7. Implement the `launchd` backend with plan/apply/status/inspect/prune support.
8. Implement the `cron` backend with equivalent support.
9. Implement the CLI thin shells and user-facing output contract.
10. Add tests, sample manifests, and user/developer documentation for the
    prototype and the Go rewrite contract.

## Dependency Strategy

High-level dependency order:

- spec alignment and repository scaffold first
- schema/domain before planner and backends
- planner and local state before full backend apply logic
- backends before final CLI completion
- tests and docs throughout, with a dedicated final hardening/documentation task

Parallelizable work exists after the core schema/domain layer is stable, but the
backlog should initially assume a mostly sequential implementation path to keep
the prototype coherent.
