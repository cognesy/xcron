# xcron xqa Pilot Plan

Date: 2026-04-09

## Goal

Adopt `xqa` in `xcron` as the first smaller external validation repo and use
the rollout to harden transferability, onboarding, and measurement-first
quality workflows outside the `xqa` codebase itself.

The success condition is not only "xqa runs here". The success condition is
that an agent or operator can get from zero to:

- `xqa doctor`
- `xqa profile run <default>`
- `xqa progress --against <baseline>`
- `xqa report ...`

with minimal confusion and no custom code inside `xqa`.

## Why xcron

`xcron` is a good first external pilot because it is:

- smaller than the larger partner repos
- a real Python CLI app with tests and documented architecture
- structured enough to exercise profiles, doctor, progress, and reports
- currently lacking a strong, repo-specific quality operations layer

This makes it useful for validating:

- setup friction
- config defaults for a Python CLI repo
- policy/profile portability
- usefulness of `xqa doctor`
- usefulness of `xqa progress`
- where repo-local workflow guidance is still required

## Constraints

- `xcron` uses `bd` for all work tracking. All rollout work must be tracked in
  this repo's own `bd` database.
- `xcron` has repo-local guidance in `AGENTS.md` and architecture constraints
  documented in `SPEC.md` and `docs/dev/architecture.md`.
- The pilot should stay pragmatic. The point is not to invent elaborate
  `xcron`-specific audits up front; it is to validate the shared `xqa`
  rollout path and capture friction honestly.
- Prefer repo-local policy/config and documentation over changes to `xqa`
  unless the pilot reveals a genuine shared-tool gap.

## Current state

Observed baseline:

- Python project managed via `pyproject.toml`
- test suite exists and `uv run pytest` is already the normal verification lane
- no `.xqa/` directory exists yet
- no dedicated quality workflow surface beyond the existing test workflow is
  obvious from the current repo docs
- architecture is clearly documented:
  - `apps/` thin shells
  - `libs/actions/`
  - `libs/services/`
  - `resources/`
  - `docs/`

Likely initial `xqa` value here:

- create a stable `default` quality workflow
- introduce or clarify a deterministic core verification lane for the repo
- create readiness diagnostics with `xqa doctor`
- establish baseline/progress reporting for cleanup or refactor sessions
- prove that `xqa` can be rolled out quickly in a smaller external repo

## Proposed rollout

### 1. Assess and design the xcron quality workflow

Identify the smallest useful initial `xqa` surface for `xcron`:

- which tools should be in `default`
- whether `typing` is warranted yet
- whether a simple docs profile is useful
- whether any architecture/policy checks should be added now or deferred

This step should avoid over-design. The first pilot should bias toward a small,
working configuration.

### Assessment decision

The initial `xqa` scope for `xcron` should stay intentionally small:

- `default`: deterministic core verification lane only
- `doctor`: readiness and optional profile execution probe
- `progress`: baseline/current/remaining-work measurement over that core lane
- `report` / `remediate plan`: available as follow-up triage tools when useful

What should be in the first `default` profile:

- the existing safe default `uv run pytest` lane

Why:

- `docs/user/README.md`, `tests/integration/README.md`, and
  `docs/dev/architecture.md` already make the repo contract explicit:
  - default `uv run pytest` stays fast and safe
  - real scheduler integration is explicit-only
  - host- or environment-specific checks are intentionally outside the default lane
- that means `xcron` already has the beginnings of the deterministic core lane
  we want `xqa` to rely on
- using that lane as the first `default` profile keeps the pilot honest and
  avoids importing extra tool churn before the rollout path itself is proven

What is deferred in the first pilot:

- `typing`
  because no dedicated type-checking lane is currently part of the repo's
  established default workflow
- `docs`
  because docs QA is useful but not necessary to validate first-rollout
  transferability here
- architecture/policy-backed audit
  because `xcron` has strong architecture docs, but the first pilot should
  validate the base setup path before adding repo-specific structural checks

Implication for the next task:

- the `xcron` `xqa` setup should start with a minimal `default` profile built
  around the deterministic `uv run pytest` lane, then prove doctor/profile/
  progress/report flows on top of that

### 2. Add repo-local xqa setup

Create and validate the initial `xcron` `xqa` setup:

- `.xqa/config.yaml`
- any minimal policy packs if justified
- any supporting ignore entries

The setup must be valid under `xqa doctor` and executable under `xqa profile`.

### 2.5. Harden the deterministic core test lane

Use the pilot to make the main verification surface clearer and safer for
automation:

- separate deterministic core verification from host- or environment-specific
  scheduling mechanisms where needed
- make the intended default test lane explicit
- ensure the first `xqa` profile can rely on a stable, non-flaky core check

This is both `xcron` hardening and a transferability check for how `xqa`
should fit into repos with mixed deterministic and environment-specific tests.

### 3. Establish operator workflow and discoverability

Document how `xcron` should use `xqa`:

- when to run `xqa doctor`
- when to run `xqa profile run default`
- how to capture a baseline and use `xqa progress`
- when to use `xqa report` and `xqa remediate plan`

Keep this minimal and practical. The purpose is to make the pilot usable, not
to write a huge operations manual.

### 4. Dogfood the workflow on real xcron quality work

Actually run the new workflow in `xcron`:

- run `xqa doctor`
- run the profile(s)
- capture a baseline
- make or identify a cleanup slice
- run `xqa progress`
- use reports/remediation planning if needed

This is the proof step. It should show whether the workflow actually provides
clear before/current/remaining-work visibility in a non-`xqa` repo.

### 5. Capture transferability friction explicitly

The pilot should end with a clear list of what did not transfer cleanly:

- setup pain
- missing defaults
- unclear docs/help
- doctor blind spots
- profile/policy limitations
- output friction
- missing generic skill/template opportunities

Those findings should feed back into `xqa`, but they should first be
captured clearly from the `xcron` pilot itself.

## Task breakdown

1. Assess `xcron` and define the minimal initial `xqa` workflow surface.
2. Implement the repo-local `xqa` setup in `xcron`.
3. Harden or clarify the deterministic core verification lane in `xcron`.
4. Add minimal operator docs and discoverability for the pilot workflow.
5. Dogfood the workflow in `xcron` and prove `xqa doctor` / `xqa progress`.
6. Capture transferability gaps and create follow-up work in the right repo(s).

## Risks

- Over-configuring the pilot and confusing the signal about what is truly needed
- Treating `xcron`-specific quirks as shared-tool requirements too early
- Skipping the dogfooding pass and concluding the setup is good based only on
  command existence
- Failing to capture rollout friction while it is fresh

## Open questions

- Should the first `xcron` pilot include only `default`, or also `typing` and
  `docs` immediately?
- Is there enough value in an initial architecture audit here, or should that
  be deferred until after the basic rollout works?
- Should the first `default` profile rely only on the deterministic core lane,
  with environment-specific verification kept explicitly separate?
- Should repo-local `xqa` skills be added in `xcron` during the pilot, or
  only after the base workflow proves useful?

## Review status

This plan is being created in direct response to an explicit user request to
structure the `xcron` pilot in `bd` before execution, so it is treated as
approved for task creation unless new constraints are raised.
