# Go Rewrite Contract

The Python prototype is not the final shipping implementation. The later Go
rewrite should preserve the external contract below unless there is a deliberate
breaking change process.

## Stable External Contract

- one or more project-local manifests under `resources/schedules/`
- required `project.id`
- no central aggregate schedule file
- CLI commands:
  - `validate`
  - `plan`
  - `apply`
  - `status`
  - `inspect`
  - `jobs list|show|add|update|enable|disable|remove`
  - `prune`
- default backend selection by host platform
- optional backend override via CLI
- project-scoped operation by default
- global `--version` remains a project- and scheduler-free liveness probe that
  prints `xcron <version>` and exits successfully
- `status` remains an operator-facing state view using concepts such as
  `ok`, `missing`, `drift`, `disabled`, `extra`, and `error`
- default `status` output retains integer `desired` and `deployed` counts
  alongside the human-readable count summary and per-job status rows; both
  integer fields remain selectable through `--fields`
- `inspect` remains a detailed single-job view exposing normalized desired
  fields, deployed artifact/log paths, and backend-native raw detail
- `jobs` commands remain manifest-editing operations; backend reconciliation
  still happens through `apply`
- help remains available at root, command-group, and leaf-command levels

## Stable Model Contract

- manifest location remains under `resources/schedules/`
- job identity remains `<project.id>.<job.id>`
- `cron` and constrained `every` schedule forms remain part of the public model
- logs remain tool-managed by default rather than required in YAML
- machine-local state remains derived only, never a source of truth
- manifest-editing commands may rewrite YAML deterministically without
  preserving comments or formatting exactly

## Architectural Contract

- thin shells stay in `src/xcron/channels/<channel>/`, one package per way
  into the product
- use-case actions are capability-owned under `src/xcron/capabilities/` and reached
  only through each module's `api`; the flat `src/xcron/actions/` facade is gone
- every file belongs to one module or to a declared leaf; native scheduler
  adapters live inside the module that defines the port they implement
- scheduler adapters consume a backend-neutral contract and never import a
  coordinating action result
- scheduler adapters return a normalized inspection contract rather than
  leaking provider-specific result types into capability orchestration
- runtime composition stays explicit and channel-independent; it owns resolved
  invocation options and the provider registry, not product policy
- a public SDK may compose the same capability actions, but it must not import
  CLI/output code or duplicate business policy; capability results remain
  independent of output envelopes and renderers
- schemas/examples/templates stay in `resources/`
- docs stay in `docs/`

The Go rewrite can change package details but should not collapse the thin
channel -> capability action -> adapter/domain separation.

## Areas Allowed To Improve

- stronger cron validation
- richer launchd/cron schedule translation
- better inspection output formatting
- more polished status/inspect presentation layers
- better cross-platform packaging and install flow
- replacement of JSON state files with a different derived-state mechanism

These improvements should not change the project-scoped source-of-truth model.
