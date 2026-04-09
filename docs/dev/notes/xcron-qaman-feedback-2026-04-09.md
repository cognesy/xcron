# xcron qaman Feedback

Date: 2026-04-09

## Context

These notes capture early feedback about `qaman` tooling and workflow fit while
planning the first `xcron` pilot.

This is pre-rollout feedback from repository assessment, not yet full
dogfooding feedback.

## What already fits well

- `xcron` already has a clear deterministic default verification story:
  `uv run pytest` is documented as safe and non-mutating.
- The repo already distinguishes default verification from explicit integration
  checks.
- That makes `xcron` a good fit for `qaman`'s measurement-first workflow
  without needing a complex initial setup.
- `qa doctor` is especially relevant here because the repo currently has no
  `qaman` setup and needs a readiness diagnostic before profile/progress usage.

## Initial workflow decision

The first `qaman` rollout in `xcron` should stay intentionally small:

- `default` should wrap the deterministic core verification lane only
- `qa doctor` should validate readiness and optionally probe that profile
- `qa progress` should measure baseline/current/remaining-work against that
  deterministic lane

Deferred for the first pilot:

- `typing`
- `docs`
- architecture/policy-backed audit

Reason:

- those may become useful later, but they are not needed to validate whether
  `qaman` transfers cleanly into a smaller external repo
- adding them immediately would blur whether rollout friction is due to the
  base `qaman` path or due to extra repo-specific complexity

## Feedback for qaman tooling

### 1. Deterministic core lanes matter

`qaman` fits best when a repo has one clearly defined safe-default verification
lane.

For mixed environments like `xcron`, where some checks are explicit-only and
environment-specific, `qaman` should encourage:

- a deterministic `default` profile
- explicit separation of integration or host-gated verification

This suggests a reusable rollout heuristic for `qaman`:

- do not start by wrapping every available check
- start by identifying the deterministic core lane first

### 2. `qa doctor` is important for first adoption

In a repo with no prior `qaman` setup, the first questions are:

- is the config present?
- is it valid?
- will the configured commands resolve and run?

That makes `qa doctor` a first-class onboarding tool, not just a maintenance
feature.

### 3. `qa progress` depends on workflow clarity, not just command existence

`qa progress` will only feel useful if the compared lane is stable and
repeatable.

If the underlying lane is fuzzy or environment-sensitive, the progress output
becomes less trustworthy.

So one practical lesson is:

- stable progress depends on stable verification inputs

### 4. Small pilot scopes reduce false feedback

For external rollout validation, the pilot should avoid extra profiles or
policy packs unless they are necessary.

Otherwise, rollout friction gets mixed together with:

- policy complexity
- docs QA choices
- repo-specific audit design

That would make feedback less useful for improving `qaman` itself.

## Feedback for qaman workflow guidance

The workflow guidance should explicitly tell adopters to decide:

1. what is the deterministic core verification lane?
2. what should be the first `default` profile?
3. what checks are intentionally outside that default lane?

This could eventually become part of:

- rollout docs
- `qa init` guidance
- `qa doctor` hints
- generic skill templates

## Pilot-specific next steps

- implement the deterministic core lane task in `xcron`
- configure `qaman` around that lane
- dogfood `qa doctor`, `qa profile`, and `qa progress`
- capture post-rollout feedback separately once real execution has happened
