# xcron AXI Hardening And DX Refactor Plan

## Goal

Refactor xcron's current AXI implementation into a cleaner, more declarative,
more maintainable internal architecture that gives tool developers a better
experience when adding or evolving commands.

This plan belongs to epic `xcron-o8o`.

The desired end state is not “more AXI features.” It is:

- cleaner separation between action results, CLI mapping, and rendering
- one central source of truth for command contracts
- less command-local AXI boilerplate
- stricter, more predictable field filtering and error behavior
- more maintainable help and hook subsystems
- easier reuse of the same pattern in sibling CLIs such as `xqueue` and
  `xfind`

## Problem Restatement

The first AXI migration made xcron materially better from a user and agent
perspective:

- TOON-first stdout exists
- structured stdout errors exist
- resource-backed runtime help exists
- a content-first bare `xcron` home view exists
- field filtering, truncation, and no-op reporting exist
- hook installation and path repair support exist

That work improved the product surface, but the implementation still places too
much AXI knowledge inside individual command modules.

Today, a developer adding or changing a command still needs to reason about:

- which fields are allowed
- which fields are default
- how nested fields are filtered
- whether `--full` applies
- how next-step hints are generated
- how mutation/no-op outcomes are shaped
- how help text relates to parser metadata

The code works, but the developer experience is still too procedural and too
easy to drift.

## Constraints

- Preserve the thin-shell -> action -> service boundary from
  `docs/dev/architecture.md`.
- Do not push AXI, TOON, or hook logic into `libs/actions/`.
- Preserve the stable external command surface from
  `docs/dev/go-rewrite-contract.md` unless there is an explicit breaking-change
  decision later.
- Keep runtime help under `resources/help/` as the authoritative command
  reference.
- Preserve deterministic core verification through `./scripts/verify-core.sh`.
- Keep the implementation practical for sibling CLI reuse; avoid xcron-specific
  abstractions where a generic CLI-edge pattern would suffice.

## Current State Assessment

The current implementation already has several good pieces:

- parser wrapper:
  - `apps/cli/parser.py`
- presentation helpers:
  - `libs/services/axi_presenter.py`
- TOON adapter:
  - `libs/services/toon_renderer.py`
- help loader:
  - `libs/services/help_renderer.py`
- hook installer:
  - `libs/services/hook_installer.py`

These were the right first-generation extractions, but the design still has
three structural weaknesses.

### 1. AXI contract metadata is still distributed

Allowed fields, default fields, truncation behavior, and command-family
semantics are still scattered across shell modules and the plan doc.

Effect:

- harder to evolve consistently
- easier for new commands to drift
- higher cognitive load for tool developers

### 2. Response shaping is still dict-oriented and command-local

Command handlers still assemble payload dicts inline before rendering.

Effect:

- output shape is not strongly modeled
- mapping logic and shell glue are still mixed together
- reuse across commands and across repos is weaker than it should be

### 3. Help and hooks are correct but not yet “subsystems”

Help is resource-backed and hooks work, but:

- help composition still relies too much on raw parser help
- hook installation is more implicit than ideal
- app-specific hook shapes are still handled in one generalized service

Effect:

- maintainability is acceptable, but not clean enough for a long-lived pattern

## Research Notes

This plan is based primarily on the local retrospective and codebase analysis.
I also reviewed a small set of external references to evaluate alternatives for
the next generation of the design:

- Typer documentation (`typer.tiangolo.com`) as a possible longer-term parser
  replacement for typed command definitions and richer help workflows
- Pydantic model documentation (`docs.pydantic.dev`) as a candidate foundation
  for typed CLI response envelopes
- `tomlkit` as a style-preserving TOML option if repo-local Codex config
  mutation needs better formatting/comment preservation

Recommendation from this research:

- do not replace `argparse` yet
- do move toward typed response models
- consider `tomlkit` only if preserving `.codex/config.toml` formatting becomes
  important

## Design Direction

The simplest framing is:

> Move xcron from a working AXI implementation to a declarative AXI framework.

That means five architecture moves.

### 1. Add a central command contract registry

Introduce a shared module such as:

- `libs/services/cli_contracts.py`

Each command contract should declare:

- command name
- help key
- command kind (`home`, `list`, `detail`, `mutation`)
- default fields
- allowed top-level fields
- allowed nested fields
- whether `--fields` is supported
- whether `--full` is supported
- truncation policy
- next-step hint policy
- usage-error recovery hints

This becomes the source of truth for command behavior at the CLI edge.

### 2. Introduce typed response envelopes

Introduce shared response models such as:

- `HomeResponse`
- `ListResponse`
- `DetailResponse`
- `MutationResponse`
- `ErrorResponse`

Likely location:

- `libs/services/cli_responses.py`

Use `dataclasses` or `pydantic` models.

Recommendation:

- prefer `pydantic` if we want stronger validation and schema-aware
  ergonomics
- prefer dataclasses if we want the lightest additional dependency surface

My recommendation for xcron specifically is to adopt Pydantic for CLI response
envelopes because it improves validation and developer ergonomics while keeping
the action layer unchanged.

### 3. Split mapping from rendering

Introduce a dedicated mapping layer such as:

- `libs/services/cli_mappers.py`

Responsibilities:

- convert action-layer results into typed CLI response envelopes
- keep command modules thin
- keep rendering logic out of command modules

The desired layering becomes:

- shell parses args
- action returns domain result
- mapper returns response model
- renderer outputs TOON or help text

### 4. Harden field filtering and command validation

Current field filtering should become strict:

- unknown requested fields should return structured usage errors
- nested-field requests must validate against explicit contract metadata
- help text should expose allowed fields where useful

This improves:

- predictability
- debuggability
- DX for tool developers and users

### 5. Turn help and hooks into clearer subsystems

#### Help

Keep `resources/help/` as the source of authored runtime help, but reduce
reliance on raw appended parser help.

Instead, generate structured help sections from:

- authored help body
- parser metadata
- contract metadata

#### Hooks

Make hook lifecycle more explicit and inspectable via:

- `xcron hooks install`
- `xcron hooks status`
- `xcron hooks repair`

Split hook-target behavior into app-specific adapters instead of one mixed
installer.

## Proposed Implementation Slices

### Slice 1: Centralize the AXI contract

- add `cli_contracts.py`
- move command field/default/full/hint metadata out of shell modules
- make shells depend on contract lookup instead of local constants

### Slice 2: Introduce typed response models and mappers

- add `cli_responses.py`
- add `cli_mappers.py`
- refactor shell modules to stop building raw payload dicts inline

### Slice 3: Harden field filtering and help composition

- make `--fields` validation strict
- emit structured usage errors on invalid field requests
- rework help rendering to compose structured sections instead of dumping raw
  parser output beneath the authored body

### Slice 4: Redesign the hook subsystem for maintainability

- add explicit hook status/repair commands
- split Codex and Claude config mutation into separate adapters
- optionally adopt `tomlkit` if preserving repo-local Codex config formatting is
  worth the added dependency

### Slice 5: Add developer ergonomics scaffolding

- add shared CLI contract assertion helpers for tests
- add command/help/test scaffolding templates or scripts
- reduce copy-paste when introducing new commands

## Proposed Task Breakdown

1. Create a central CLI contract registry and move command AXI metadata into it.
2. Introduce typed CLI response models and a mapping layer between actions and
   renderers.
3. Refactor xcron shell modules to use contracts plus mappers instead of
   command-local payload assembly.
4. Make field validation strict and redesign runtime help composition around
   contracts plus parser metadata.
5. Redesign the hook subsystem into explicit install/status/repair flows with
   app-specific adapters.
6. Add shared CLI DX tooling: reusable test helpers, scaffolding, and final
   verification/docs updates.

## Risks

### Over-engineering the contract layer

If the contract registry becomes too abstract, it may be harder to use than the
current shell-local constants.

Mitigation:

- keep the registry declarative and small
- favor explicit data over clever indirection

### Introducing typed responses without real leverage

If typed response models are added but command modules still manually shape
everything, the refactor adds ceremony without enough payoff.

Mitigation:

- land response models together with mappers, not separately

### Hook redesign can introduce config churn

Repo-local hook/config mutation is operationally sensitive.

Mitigation:

- test against temp directories
- keep auto-install best-effort or reduce its implicitness
- make hook status/repair explicit and inspectable

### Parser replacement distraction

Switching parser libraries now would widen scope and delay the meaningful DX
refactor.

Mitigation:

- keep `argparse` for this refactor
- revisit parser replacement only after the contract/model/mapping layers are
  stable

## Open Questions

- Should typed response envelopes use Pydantic or plain dataclasses?
- Should auto-install of hooks remain enabled by default once explicit
  `hooks status` / `hooks repair` commands exist?
- Should the contract registry also own example generation, or only output/help
  field metadata?

## Recommendation

Proceed with the six slices above in that order.

The first three slices are the real core of the DX refactor. They reduce the
amount of AXI knowledge embedded in command modules and make the implementation
significantly easier to reuse across sibling CLIs.

The last three slices harden and operationalize the design once that central
contract/model/mapping architecture exists.
