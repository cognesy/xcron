# xcron qaman Pilot Retrospective

Date: 2026-04-09

## Scope

This note captures the transferability feedback from the first `qaman` pilot in
`xcron`.

Pilot outcomes validated:

- repo-local `.qaman/` setup works
- `qa doctor` works in an external repo
- a deterministic `default` profile works
- baseline storage works
- `qa progress` works in both `toon` and `text` output modes

## What transferred well

### 1. Minimal rollout is enough to prove value

Starting with a single deterministic `default` profile was the right choice.

This let the pilot prove:

- readiness via `qa doctor`
- execution via `qa profile run default`
- measurement via `qa snap store` and `qa progress`

without mixing in unnecessary policy-pack or multi-profile complexity.

### 2. Deterministic core lane fit the model well

`xcron` already had a safe-default `uv run pytest` lane and explicit integration
harnesses outside that lane.

That made it easy to define:

- deterministic core verification
- explicit integration checks

which maps well onto `qaman`'s default-profile philosophy.

### 3. `qa doctor` is useful during adoption

`qa doctor` immediately answered the setup questions that matter in a new repo:

- is config present?
- does it load?
- do commands build?
- does the default profile execute?

That made it a real onboarding tool, not just a maintenance command.

### 4. `qa progress` proved the before/current story

Using a controlled temporary failing test produced a concrete measured flow:

- failing baseline snapshot: `4ee1084fd30e...`
- baseline findings: `1`
- current findings after cleanup: `0`
- resolved findings: `1`
- progress percent: `100.0`

That proved the workflow is not only conceptually sound in `qa-man`, but also
useful in an external repo.

## Transferability friction

### 1. Shared `qa` executable discoverability is weak

In this environment, `qa` was not on `PATH` inside `xcron`.

The pilot had to use the shared checkout binary explicitly:

```sh
/Users/ddebowczyk/projects/qa-man/.venv/bin/qa
```

This is acceptable for a development pilot, but poor for general rollout UX.

Implication:

- `qa-man` still needs a better installation/onboarding story for use from
  other repos

### 2. Pytest file-path mapping is wrong for Python test module failures

The temporary failing test in:

```text
tests/test_qaman_pilot_temp.py
```

was normalized as:

```text
file: tests.py
```

That is a real quality/data bug in the shared tool, not an `xcron` issue.

Implication:

- `qa-man` needs a pytest normalizer fix so findings point at the real Python
  test file

### 3. Progress on a clean repo needs a real slice to be meaningful

Because `xcron` was already green on the deterministic lane, a trivial
baseline/current run would have produced a 0-to-0 result with little value.

For the pilot, a temporary controlled failure slice was used to prove the
workflow.

This is not a product bug, but it is a rollout lesson:

- on already-clean repos, proving `qa progress` value may require either:
  - a real pending cleanup slice, or
  - a small controlled demonstration

## Follow-up destinations

### qa-man follow-up

- `qaman-dss` — improve shared `qa` executable and install discoverability
  across repos
- `qaman-6ut` — fix pytest normalizer file-path mapping for Python test
  failures

### xcron follow-up

No critical `xcron`-local blocking issue was discovered during the pilot.

Potential future enhancement, but not required for this pilot:

- decide whether to grow beyond the minimal `default`/`tests` profile surface

## Template lessons

What should likely become part of generic `qaman` rollout guidance later:

1. identify the deterministic core verification lane first
2. start with one useful `default` profile
3. use `qa doctor` before quality execution if setup confidence is low
4. use `qa progress` only after the lane being measured is stable
5. keep integration or environment-specific checks outside the initial default
   profile unless the repo truly needs more
