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
  - `prune`
- default backend selection by host platform
- optional backend override via CLI
- project-scoped operation by default
- `status` remains an operator-facing state view using concepts such as
  `ok`, `missing`, `drift`, `disabled`, `extra`, and `error`
- `inspect` remains a detailed single-job view exposing normalized desired
  fields, deployed artifact/log paths, and backend-native raw detail

## Stable Model Contract

- manifest location remains under `resources/schedules/`
- job identity remains `<project.id>.<job.id>`
- `cron` and constrained `every` schedule forms remain part of the public model
- logs remain tool-managed by default rather than required in YAML
- machine-local state remains derived only, never a source of truth

## Architectural Contract

- thin shells stay in `apps/`
- use-case actions stay in `libs/actions/`
- reusable capabilities stay in `libs/services/`
- schemas/examples/templates stay in `resources/`
- docs stay in `docs/`

The Go rewrite can change package details but should not collapse the thin
shell -> action -> service separation.

## Areas Allowed To Improve

- stronger cron validation
- richer launchd/cron schedule translation
- better inspection output formatting
- more polished status/inspect presentation layers
- better cross-platform packaging and install flow
- replacement of JSON state files with a different derived-state mechanism

These improvements should not change the project-scoped source-of-truth model.
