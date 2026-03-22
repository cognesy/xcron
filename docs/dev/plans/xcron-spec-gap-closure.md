# xcron SPEC Gap Closure Plan

## Goal

Close the remaining meaningful gaps between the current Python prototype and the
original `SPEC.md`, without widening scope beyond the intended v1 prototype.

The work should make the prototype more honest against the documented operator
contract in three areas:

- `status` semantics
- `inspect` depth
- real Linux cron integration coverage

This plan belongs to epic `xcron-7u6`.

## Current State

The prototype already delivers the main architecture and backend behavior:

- per-project manifests under `resources/schedules/`
- validation, normalization, and stable hashing
- wrapper rendering and deterministic logs
- `launchd` backend
- `cron` backend
- CLI commands for `validate`, `plan`, `apply`, `status`, `inspect`, and
  `prune`
- real host `launchd` integration test gated outside the default suite

Recent review work also improved:

- action and subprocess observability via `structlog`
- wrapper-level execution lifecycle markers
- backend-derived log-path reconstruction
- `inspect` surfacing of artifact/wrapper/log paths

## Remaining Gaps Against SPEC

### 1. `status` contract mismatch

`SPEC.md` describes `status` as an operator-facing desired-vs-actual state view
with status concepts such as:

- `ok`
- `missing`
- `drift`
- `disabled`
- `extra`
- `error`

The current implementation largely exposes planner change kinds instead. That is
useful internally but is not the same contract.

### 2. `inspect` still does not expose the full intended depth

The spec expects `inspect` to show:

- normalized desired job definition
- selected backend
- generated native artifact path
- generated wrapper path
- native scheduler status
- relevant log paths
- native config snippet or raw rendered artifact

The current CLI improved, but it still does not surface the normalized desired
definition or rich backend-native detail consistently enough.

### 3. Linux cron lacks true end-to-end integration coverage

The repo has:

- safe cron backend tests using temp crontab files
- a real host-gated `launchd` integration test

What it still lacks is a real Linux cron integration lane that:

- runs in an isolated environment
- uses the real `crontab` command and cron daemon
- validates scheduled execution end to end

## Constraints

- Preserve the thin-shell -> action -> service boundary from
  `docs/dev/architecture.md`.
- Do not let `status` collapse back into planner terminology.
- Keep default `uv run pytest` fast and safe.
- Real integration tests must be explicit-only and must not mutate the host
  Linux crontab.
- Prefer Colima/Docker for Linux cron integration.
- Keep docs and Go rewrite contract aligned with any user-facing output changes.

## Affected Areas

### `status` alignment

- `apps/cli/commands/status.py`
- `libs/actions/status_project.py`
- `libs/domain/diffing.py`
- possibly a new status-specific result/presentation model under `libs/domain/`
  or `libs/actions/`
- tests covering user-facing status output

### `inspect` alignment

- `apps/cli/commands/inspect.py`
- `libs/actions/inspect_job.py`
- `libs/services/backends/launchd_service.py`
- `libs/services/backends/cron_service.py`
- docs in `docs/user/README.md`
- tests for CLI inspect output and backend-specific detail

### Linux cron integration lane

- `tests/integration/`
- a small Dockerfile and runner script
- documentation for explicit execution
- possibly a marker or naming convention so the integration test remains outside
  default collection

## Approach

Break the work into three focused slices plus one documentation/verification
close-out.

### Slice 1: Make `status` operator-first

Introduce an explicit status interpretation layer that maps desired-vs-actual
conditions to the spec language.

Likely shape:

- keep planner internals intact for reconciliation
- add a status-specific projection for CLI presentation
- preserve enough detail for debugging without exposing raw planner terms as the
  primary contract

Desired output should distinguish:

- desired job is present and healthy
- desired job is missing from actual state
- desired job is present but drifted
- desired job is intentionally disabled
- unmanaged or unexpected managed extra state exists
- backend inspection failed

### Slice 2: Deepen `inspect`

Expand the CLI and result model so `inspect` reliably includes:

- normalized desired job fields
- backend-native artifact path
- wrapper path
- stdout/stderr log paths
- backend-loaded/enabled state
- raw cron entry or launchd plist / launchctl detail where appropriate

The main design choice is how much to expose by default. For the prototype, bias
toward explicitness over terseness.

### Slice 3: Add isolated real cron integration coverage

Use a slim Linux container under Colima/Docker rather than the host.

Likely shape:

- Debian slim image
- install cron and required shell tools
- mount or copy the repo
- run `uv sync --extra dev`
- create a temp project in the container
- run real `xcron apply --backend cron`
- install the managed block into the real container user crontab
- run cron daemon
- wait for a scheduled marker command to fire
- assert managed stdout/stderr logs and wrapper lifecycle markers
- run `status`, `inspect`, and `prune`

This should be driven by an explicit script such as:

```sh
tests/integration/run_cron_it.sh
```

and remain opt-in only.

### Slice 4: Documentation and contract alignment

After the behavior lands:

- update `docs/user/README.md`
- update any relevant developer docs
- verify `docs/dev/go-rewrite-contract.md` still reflects the intended external
  contract

## Proposed Task Breakdown

1. Align `status` output with the spec’s operator-facing state model.
2. Expand `inspect` output to expose the remaining desired and native backend
   details required by the spec.
3. Add isolated Linux cron real integration coverage using Docker/Colima.
4. Update docs and verification guidance for the new `status`, `inspect`, and
   integration-test workflows.

## Risks

### Status semantics drift

There is a risk of layering status concepts on top of planner concepts in a way
that is confusing or lossy.

Mitigation:

- keep reconciliation planning and status presentation separate
- test user-facing output explicitly

### Launchd/cron asymmetry in `inspect`

The two backends naturally expose different native detail.

Mitigation:

- define the minimum common inspect contract
- allow backend-specific extra fields where helpful

### Cron timing flakiness in containers

Real cron integration tests can be slow or timing-sensitive.

Mitigation:

- keep them out of the default suite
- use deterministic marker commands
- give the runner a bounded polling loop and good failure output

## Open Questions

- Should `status` remain text-only for now, or should it start moving toward a
  more structured output contract in the prototype?
- For `inspect`, should launchd include raw plist by default, raw `launchctl
  print`, or both?
- Should the Linux cron integration harness live entirely in shell, or should
  pytest invoke the Docker/Colima runner?

## Recommendation

Proceed with the four tasks above in that order.

The first two are contract-correctness work and should land before the Linux
integration harness. The cron integration lane should then verify the prototype
behavior on Linux the same way the new host-gated `launchd` test verifies macOS.
