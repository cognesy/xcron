# xcron Typer/Rich/Pydantic Migration Plan

## Goal

Replace xcron's current custom `argparse`-driven CLI declaration layer with a
cleaner, more maintainable stack built around:

- **Typer** for command and option declaration
- **Rich** for human-facing help and presentation
- **Pydantic** for typed CLI response models and serialization boundaries

This plan belongs to epic `xcron-mgq`.

The migration should preserve:

- the thin-shell -> action -> service architecture
- the stable command surface from `docs/dev/go-rewrite-contract.md`
- the current project-scoped source-of-truth model
- TOON as the machine-facing stdout contract where agent ergonomics still
  matter
- the repo-local hook subsystem and resource-backed help assets where they still
  provide value

## Problem Restatement

xcron's current AXI implementation is significantly better than the original
prototype, but it has reached the point where we are re-implementing concerns a
CLI framework can already do better.

The main problem is not the action layer or the TOON boundary. The main problem
is the custom shell declaration stack:

- `apps/cli/main.py`
- `apps/cli/parser.py`
- command registration boilerplate in `apps/cli/commands/*`
- custom parser/help integration layered on top of `argparse`

The current code is serviceable, but for tool developers it is heavier than it
should be:

- adding or changing a command still requires a lot of shell ceremony
- parser/help behavior is more custom than necessary
- some of the “contract” infrastructure overlaps with responsibilities Typer
  already handles more cleanly

The cleaner direction is:

> let Typer own command declaration and parser-facing help, let Pydantic own
> typed response envelopes, let Rich own human-facing rendering, and keep a
> much smaller AXI/TOON policy layer for machine-facing behavior.

## Constraints

- Preserve `apps/` as thin entrypoints, `libs/actions/` as use-case
  boundaries, and `libs/services/` as reusable infrastructure.
- Preserve the stable external command surface:
  - `validate`
  - `plan`
  - `apply`
  - `status`
  - `inspect`
  - `jobs list|show|add|update|enable|disable|remove`
  - `prune`
  - existing hook command surface where still intended
- Preserve the resource/help and hook work where it remains useful.
- Do not collapse the architecture into Typer command functions that embed
  action logic directly.
- Keep deterministic verification through `./scripts/verify-core.sh`.
- Keep the migration incremental enough that behavior can be compared against
  the current CLI.

## Current State

xcron already has the following CLI-edge pieces:

- declarative contract metadata
- typed response envelopes
- response mapping layer
- TOON rendering boundary
- resource-backed help
- repo-local hook subsystem

The important observation is that not all of this should be replaced.

### What should be replaced

- `argparse`-specific command declaration and parser wrapper logic
- parser-centric help composition responsibilities that belong naturally to
  Typer/Rich
- shell registration boilerplate that Typer can handle more directly

### What should be kept and adapted

- the action layer
- typed response-model concept
- mapping layer from action result to response model
- TOON output adapter
- hook subsystem
- runtime help assets under `resources/help/`

### What should be reduced in scope

- command contract metadata should shrink to machine-output policy only
  instead of trying to own both parser behavior and output behavior

## External Research Notes

I reviewed the official docs for the target stack:

- Typer command and subcommand model:
  - `https://typer.tiangolo.com/tutorial/commands/`
- Rich console, tables, and markdown:
  - `https://rich.readthedocs.io/en/latest/console.html`
  - `https://rich.readthedocs.io/en/latest/tables.html`
  - `https://rich.readthedocs.io/en/stable/markdown.html`
- Pydantic modeling and serialization:
  - `https://docs.pydantic.dev/latest/why/`
  - `https://docs.pydantic.dev/latest/concepts/serialization/`

Pragmatic conclusion:

- Typer is a better fit for developer-facing command declaration than continuing
  to build on custom `argparse` wrappers
- Rich should improve human-facing help and optional human output modes, but it
  should not replace TOON as the machine-facing contract by default
- Pydantic is a stronger fit than raw dataclasses for durable CLI response
  envelopes and serialization

## Migration Direction

The migration should separate three concerns clearly.

### 1. Command declaration

Owned by **Typer**.

Responsibilities:

- command groups and subcommands
- option/argument declaration
- parser-level usage/help behavior
- shell entrypoint wiring

### 2. Response modeling and mapping

Owned by **Pydantic + mapper layer**.

Responsibilities:

- define typed CLI response envelopes
- map action-layer results into response models
- validate response shape before rendering

### 3. Output mode and presentation

Owned by **TOON adapter + Rich rendering layer**.

Responsibilities:

- TOON output for agent/machine mode
- Rich/Markdown output for help and optional human-facing render flows
- truncation and field filtering behavior where still needed for machine output

## Design Decisions

### Keep TOON for machine-facing output

Rich is valuable for humans, but TOON remains the better default contract for
agent-facing command output.

Recommendation:

- keep normal machine-facing command output on TOON by default
- use Rich for help and optional human-oriented presentation mode
- optionally add explicit format selection later if needed

### Replace current dataclass response envelopes with Pydantic

The current typed response work is useful, but Pydantic gives:

- stronger validation
- cleaner serialization
- better schema introspection
- better long-term ergonomics across sibling CLIs

### Shrink the contract layer

After Typer lands, command contracts should only own what Typer does not:

- default output fields
- allowed machine-output fields
- nested output field rules
- truncation policy
- next-step hint policy if retained

They should stop owning parser/help declaration concerns.

## Proposed Implementation Slices

### Slice 1: Introduce Pydantic response models

- replace or supersede the current dataclass response envelope layer
- preserve the existing mapper separation concept
- keep command behavior stable while changing the model substrate

### Slice 2: Introduce a unified output service

- one service that renders Pydantic response models to TOON
- one Rich-based path for help and optional human-facing presentation
- preserve the machine-facing contract while making human presentation cleaner

### Slice 3: Build a parallel Typer shell

- add a Typer app and subapps that mirror the current command surface
- keep actions and mappers unchanged
- do not remove the old `argparse` shell yet

### Slice 4: Migrate command families incrementally

Recommended order:

1. `validate`
2. `plan`
3. `status`
4. `inspect`
5. `jobs`
6. `apply`
7. `prune`
8. `hooks`

This moves from low-risk read flows toward more stateful flows.

### Slice 5: Replace parser-centric help with Typer/Rich help

- integrate `resources/help/` authored content into a Rich/Markdown help path
- stop relying on raw `argparse` help composition
- keep help authoritative at runtime

### Slice 6: Retire obsolete `argparse` infrastructure

- remove `AxiArgumentParser`
- remove now-obsolete shell-registration boilerplate
- reduce the command contract layer to output policy only

## Proposed Task Breakdown

1. Replace the current CLI response envelope layer with Pydantic models while
   preserving the mapper boundary.
2. Build a unified output/render service that supports TOON machine output and
   Rich-based human/help rendering.
3. Add a parallel Typer app and migrate low-risk read commands first.
4. Migrate the remaining command families, including `jobs`, `apply`, `prune`,
   and `hooks`, onto the Typer shell.
5. Rework runtime help around Typer + Rich while preserving `resources/help/`
   as the authored source.
6. Remove obsolete `argparse`-centric infrastructure, update docs/tests, and
   run final verification.

## Risks

### Dual-shell transition complexity

Keeping `argparse` and Typer in parallel during the migration can create drift
or confusion.

Mitigation:

- keep one shell as the primary user entrypoint
- migrate command families in a planned order
- compare outputs through tests before removing the old shell

### Rich output overreach

If Rich starts replacing machine-facing output instead of complementing it, the
CLI can regress for agent usage.

Mitigation:

- keep TOON as the default machine contract
- constrain Rich to help and explicitly human-facing render paths

### Pydantic migration churn

Replacing the current dataclass response layer introduces model and test churn.

Mitigation:

- do it early in the migration
- preserve the mapper boundary so shell behavior remains stable

### Hook subsystem drift during shell replacement

`hooks` commands are operationally sensitive and easy to break during shell
migration.

Mitigation:

- migrate hooks late
- keep target-specific adapters intact
- retain temp-dir-based hook tests throughout

## Open Questions

- Should Rich remain limited to help and optional human-mode output, or should
  selected commands gain explicit Rich output modes?
- Do we want Pydantic v2 features such as stricter serializers/validators in
  the CLI response layer immediately, or only basic model/dump usage?
- During the migration, should Typer live under a parallel entrypoint first or
  replace the existing `xcron` script as soon as the first command family is
  ready?

## Recommendation

Proceed with the six slices above in order.

This plan intentionally pivots away from building more parser/declaration
infrastructure on top of `argparse`. It keeps the good parts of the recent AXI
work, but replaces the declaration/help shell with a stack better aligned with
developer DX:

- Typer
- Rich
- Pydantic
