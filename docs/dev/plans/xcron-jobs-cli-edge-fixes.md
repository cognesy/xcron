# xcron Jobs CLI Edge Fixes

## Goal

Fix the two retrospective follow-up bugs in the new `xcron jobs` CLI while
preserving the current manifest-first architecture:

- invalid `--env` input must fail cleanly without a traceback
- `xcron jobs update JOB_ID` must reject empty mutations and must not rewrite
  the manifest on disk when nothing was requested

This plan belongs to epic `xcron-mm2`.

## Problem Restatement

The main `jobs` workflow shipped successfully, but two operator-facing edge
cases remain:

1. The CLI currently lets a local `ValueError` escape when `--env` is malformed
   (`KEY=VALUE` expected), which produces a traceback instead of a normal
   command error.
2. The `update` command currently treats an empty mutation payload as success,
   which rewrites YAML unnecessarily and misleads the operator with
   `updated_job: ...`.

Both issues are small in code size but high in operator impact because the new
surface is meant to be agent-friendly and explicit.

## Constraints

- Keep the current architecture intact:
  - CLI shells in `apps/`
  - use-case orchestration in `libs/actions/`
  - file mutation in `libs/services/`
- Preserve the manifest-first model:
  - `jobs` commands edit YAML only
  - `apply` remains the backend reconciliation step
- Avoid broad refactors for a small bug-fix slice.
- Keep tests focused on operator-facing behavior and regression coverage.

## Current Code Observations

- `apps/cli/commands/jobs.py` builds add/update payloads directly in the shell.
- `_parse_env_assignments()` currently raises `ValueError` for malformed input.
- `handle_update()` does not validate that at least one mutation flag was
  provided before calling `update_job()`.
- `libs/services/manifest_editor.py` always writes after a mutation callback,
  which is fine for real mutations but currently allows a no-op update path to
  rewrite the manifest.
- Existing CLI coverage in `tests/test_cli_jobs.py` focuses on happy-path flows
  and help behavior, not invalid-input or no-op update paths.

## Proposed Approach

### 1. Normalize malformed `--env` into a normal CLI failure

Handle argument-shape problems in the CLI shell rather than allowing them to
escape as Python exceptions.

Pragmatic approach:

- convert `_parse_env_assignments()` failures into a stable user-facing error
- return the normal non-zero command code used for command/action failures
- avoid traceback output for malformed operator input

This keeps the error at the outer shell boundary where the input is parsed.

### 2. Reject empty update mutations before invoking the action layer

Treat `xcron jobs update JOB_ID` with no field or clear flags as invalid CLI
usage.

Pragmatic approach:

- after building the update payload, check whether both:
  - `updates` is empty
  - `clear_fields` is empty
- if both are empty, print a concise operator-facing error and return the same
  non-zero failure code used elsewhere
- do not call `update_job()`

This keeps no-op validation near the command semantics and avoids adding
artificial “no-op mutation” behavior to the manifest service layer.

### 3. Add focused regression coverage

Add CLI tests for:

- malformed `--env` input returns a clean failure without traceback
- empty `jobs update` returns a failure and leaves the manifest unchanged

The second test should assert file contents or hash stability to prove there was
no write.

## Task Breakdown

1. Fix malformed `--env` handling in the `jobs` CLI shell and add regression
   coverage.
2. Reject empty `jobs update` mutations and add regression coverage that proves
   the manifest is unchanged.

## Risks

### Error-path inconsistency

If the CLI introduces a one-off error-printing path that differs from the rest
of the tool, behavior will become harder to automate.

Mitigation:

- reuse the same non-zero exit code pattern already used for command failures
- keep the printed message concise and deterministic

### Over-fixing in the wrong layer

It would be easy to push these fixes too deep into actions or services even
though they are command-shape problems.

Mitigation:

- keep malformed `--env` and empty-update validation in the CLI shell unless a
  stronger cross-layer need appears during implementation

## Open Questions

None. The retrospective already narrowed the follow-up scope enough to proceed.
