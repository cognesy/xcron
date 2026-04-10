# xcron Architecture

This prototype follows the repository and code-architecture rules defined in
`SPEC.md`.

Top-level layout:

- `apps/` contains runnable thin shells
- `libs/` contains reusable actions, services, domain logic, and infra helpers
- `resources/` contains schemas, templates, and other static assets
- `docs/` contains developer and user documentation

Code-architecture rules:

- thin shells translate inputs to action parameters
- actions coordinate use cases
- services provide context-independent capabilities

Current model decisions:

- schedule manifests live under `resources/schedules/`
- the manifest is per-project only
- every manifest must define `project.id`
- backend-neutral job identity is derived as `<project.id>.<job.id>`
- `schedule.every` remains part of the public model, constrained to a simple
  duration string for v1

The Python prototype should preserve these boundaries so the later Go rewrite
can keep the same external contract and internal separation of concerns.

Implemented prototype components:

- validation, normalization, and stable hashing
- planner and per-project derived local state
- manifest editing service for job-level YAML updates
- wrapper rendering with default logs and overlap control
- `launchd` backend
- `cron` backend
- operator-facing `status` projection layered on top of planner diffing
- richer `inspect` results that expose normalized desired data plus
  backend-native detail
- nested `jobs` CLI group for manifest-side job management
- CLI thin shells that call actions rather than embedding backend logic
- declarative CLI contract metadata for AXI-facing command behavior
- typed CLI response envelopes plus mapper helpers at the CLI edge
- resource-backed runtime help under `resources/help/`
- repo-local Codex and Claude hook adapters plus install/status/repair flows

Verification model:

- deterministic core lane is `./scripts/verify-core.sh`
- today that core lane runs the safe default `uv run pytest`
- default core verification stays safe and does not mutate the host scheduler
- host-gated `launchd` integration exists for real macOS verification
- Docker/Colima-gated cron integration exists for real Linux cron verification

See `docs/dev/go-rewrite-contract.md` for the external behavior that should
remain stable in the later Go implementation.
