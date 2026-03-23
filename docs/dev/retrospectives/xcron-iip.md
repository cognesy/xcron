# xcron-iip Retrospective

## Scope

Epic: `xcron-iip`

Delivered scope:

- manifest-first job management for one selected schedule YAML
- action-layer support for list/show/add/remove/update/enable/disable
- nested `xcron jobs` CLI group
- explicit root/group/leaf `--help` coverage
- user and developer docs for the new workflow

At retrospective time:

- epic `xcron-iip` is closed
- all four child tasks are closed
- no scoped open or in-progress work remains under the epic

## What Was Delivered

The implementation stayed aligned with the intended architecture:

- CLI shells remain in `apps/`
- use-case coordination remains in `libs/actions/`
- file and YAML mutation logic lives in `libs/services/`

The delivered slice added a reusable manifest editor, job-management actions,
the `jobs` command group, focused tests, and updated user/developer docs.

## Plan Versus Reality

What matched the plan:

- the task split was accurate
- the dependency order was correct
- the manifest-first model held through implementation
- thin-shell -> action -> service boundaries were preserved

What diverged during execution:

- the largest friction did not come from the new manifest-editing logic itself
- it came from edge-case CLI behavior and observability interactions discovered
  while verifying the new command surface
- a logger configuration bug surfaced during task execution because pytest
  swapped output streams under `capsys`

That logging issue was fixed during execution and covered by the final green
test run, but it was discovered later than the original task descriptions
implied.

## Implementation Findings

Two follow-up bugs remain open after review.

### 1. Invalid `--env` input crashes with a traceback

In `apps/cli/commands/jobs.py` (around lines 233 and 269),
the CLI raises `ValueError` directly from `_parse_env_assignments()`. Invalid
input such as `--env BAD` currently escapes the shell boundary and produces a
full traceback instead of a normal command failure.

Tracked in `bd` as `xcron-3ca`.

### 2. `jobs update` accepts a no-op mutation and rewrites the manifest

In `apps/cli/commands/jobs.py` (around line 200)
and `libs/services/manifest_editor.py` (around line 124),
`xcron jobs update JOB_ID` succeeds even when no update or clear flags are
provided. Because `libs/services/manifest_editor.py` (around line 160)
always validates and writes after mutation, the command reports success and
rewrites the YAML file even though no semantic change was requested.

Tracked in `bd` as `xcron-1hs`.

## Verification Review

What was verified well:

- manifest editor CRUD paths
- action-layer success and invalid-mutation behavior
- CLI help coverage at root/group/leaf levels
- representative CLI add/list/show/update/disable/remove flow

What remains thinner than ideal:

- there is no CLI test yet for malformed `--env` input
- there is no CLI test yet proving `jobs update` rejects empty mutations

Those gaps map directly to the two follow-up bugs above.

## Friction Patterns

- Edge-case CLI behavior was under-specified compared with the happy-path
  command contract.
- Shell quoting can easily corrupt `bd` issue descriptions if command text is
  pasted with backticks or angle brackets unescaped.
- The repo still has no configured git or Dolt remote, so mandatory push steps
  cannot complete even when implementation work is done cleanly.

## What Worked Well

- The plan decomposed the work at the right boundaries.
- The manifest editor abstraction made the CLI expansion straightforward.
- Focused tests for each layer kept the implementation changes local and easy
  to verify.
- The docs were updated in the same slice rather than deferred.

## Next-Cycle Adjustments

Process adjustments:

- Add explicit invalid-input cases to CLI tasks during planning, not only
  happy-path examples.
- Treat “does this mutate when nothing was requested?” as a standard check for
  any command named `update`.
- When creating `bd` issues from shell commands, avoid unescaped backticks and
  angle brackets in inline descriptions.

Implementation adjustments:

- Normalize CLI argument-shape errors into ordinary non-zero command failures.
- Reject empty mutation payloads before the action/service layer writes
  manifests.
- Add one small regression test for each operator-facing error path, not just
  success paths.

## Final State

- the epic delivered its planned scope
- the architecture stayed intact
- tests passed at close-out
- two retrospective follow-up bugs were filed:
  - `xcron-3ca`
  - `xcron-1hs`
