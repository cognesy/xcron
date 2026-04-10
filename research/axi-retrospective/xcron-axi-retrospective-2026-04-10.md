# xcron AXI Retrospective

Date: 2026-04-10

## Purpose

Capture the engineering approach, reusable mechanisms, and design tradeoffs from
the xcron AXI migration so teams working on similar CLI refactors in sibling
projects such as `xqueue` and `xfind` can reuse what worked and avoid the same
mistakes.

This note focuses on:

- how the redesign was approached
- which reusable components/mechanisms were implemented
- what I would do differently starting from scratch
- how I would harden the current AXI implementation if we continue with the
  same overall architecture
- which components or libraries I would consider replacing

## Executive Summary

The migration worked because it was treated as a contract migration, not a
formatting pass.

The key move was to preserve the existing domain/action architecture and insert
an explicit presentation boundary at the CLI edge. Once that existed, AXI
requirements such as TOON output, structured stdout errors, field filtering,
truncation, resource-backed help, and session hooks could be implemented as
shared infrastructure instead of per-command hacks.

The biggest reusable lesson is this:

> If the project already has structured action results, do not rewrite the
> business logic. Replace the CLI edge with a contract-driven presentation
> layer.

## How The Redesign Was Approached

### 1. Freeze the target contract before changing runtime code

The first step was not implementation. It was turning AXI into a concrete local
contract in:

- `docs/dev/plans/xcron-axi-cli-compliance.md`

That contract pinned:

- which commands are list/detail/mutation/home/help
- the default fields for each command family
- where `--fields` and `--full` apply
- the structured error envelope
- truncation rules
- no-op semantics
- the expected file/module write set

That reduced thrash later. Without this step, every command rewrite becomes a
fresh policy decision.

### 2. Preserve the existing architectural boundary

The migration deliberately kept:

- `apps/` as thin shells
- `libs/actions/` as use-case boundaries
- `libs/services/` as reusable infrastructure

TOON and AXI logic were kept out of the action layer. Actions still return
structured dataclasses and domain models. The CLI edge now translates those
results into AXI-compliant payloads.

This matters because the same pattern can be reused in other projects without
touching core logic.

### 3. Sequence the work in dependency order

The work was staged as:

1. Define the contract.
2. Add TOON dependency and wrapper.
3. Add parser/presenter infrastructure.
4. Move help into packaged runtime resources.
5. Convert commands to the new output model.
6. Add hook installation/path repair and packaging verification.

That sequencing kept failures local and made it possible to verify each layer
before stacking more complexity on top.

### 4. Rewrite tests around the new contract, not legacy strings

The test strategy changed from:

- “does the old text still appear?”

to:

- “does this command satisfy the new structured contract?”

That was the right move. Preserving legacy text assertions while migrating to a
structured-output CLI just creates noise and false failures.

## Reusable Mechanisms Implemented

These are the pieces most worth copying into `xqueue`, `xfind`, or any other
agent-facing CLI.

### AxiArgumentParser

File:

- `apps/cli/parser.py`

Purpose:

- override `argparse` usage failures
- emit structured stdout errors instead of parser-owned stderr text
- support resource-backed help rendering

Why it matters:

- `argparse` is fine for parsing
- `argparse` is not fine as the long-term owner of agent-facing UX

### AXI presenter helpers

File:

- `libs/services/axi_presenter.py`

Purpose:

- parse `--fields`
- filter top-level, list-row, and nested object fields
- create truncation metadata
- build common structured error envelopes
- centralize presentation rules

Why it matters:

- this is the real refactoring seam
- without this layer, every command starts re-implementing AXI manually

### TOON output adapter

File:

- `libs/services/toon_renderer.py`

Purpose:

- isolate the third-party TOON package behind one module
- normalize Python containers before encoding
- keep the output dependency from leaking through the codebase

Why it matters:

- upstream library behavior is not your CLI contract
- if you need to swap or fork the encoder later, you only change one place

### Resource-backed help system

Files:

- `libs/services/help_renderer.py`
- `resources/help/**/*.md`

Purpose:

- treat runtime help as packaged product surface
- move detailed help out of `docs/` and into runtime-owned assets
- combine authored help with parser-derived flag/argument reference

Why it matters:

- `docs` should explain workflows and concepts
- runtime help should be the authoritative command reference

### Hook installer and hidden hook commands

Files:

- `libs/services/hook_installer.py`
- `apps/cli/commands/hooks.py`

Purpose:

- install repo-local Codex and Claude hook config
- repair stale executable paths
- expose hook entrypoints for session-start/session-end actions

Why it matters:

- AXI session hooks are operational infrastructure, not just documentation
- path repair needs to be implemented, not merely recommended

### Real no-op detection at the mutation source

Files:

- `libs/services/manifest_editor.py`
- `libs/actions/manage_jobs.py`

Purpose:

- detect whether a mutation actually changed the manifest
- surface that signal up to the CLI

Why it matters:

- the presenter should not guess whether something was a no-op
- if the source layer cannot tell, the CLI is likely to lie

## What Worked Well

### Contract-first planning

This was the highest leverage decision. It lowered ambiguity for every later
step and made task planning more realistic.

### Keeping actions structured and untouched

Because actions already returned dataclasses and domain models, the migration
stayed mostly in:

- `apps/cli/`
- `libs/services/`

That drastically reduced risk.

### Separating help migration from output migration

Help was treated as:

- content work
- packaging work
- parser integration work

Command migration was treated as:

- runtime behavior work
- contract enforcement work

Keeping those separate made debugging much easier.

### Verifying packaging, not just source-tree execution

Running `uv build` was essential. It proved that:

- `resources/help` was actually shipped
- runtime help lookup worked with package data

Many CLI refactors stop too early and verify only in editable/source-tree mode.

### Hook tests against temp directories

Testing hook installation against temporary directories, instead of touching
real home config, made the hook work safe and deterministic.

## What Was Tricky

### argparse as a UX owner

`argparse` works well until you need:

- structured stdout errors
- authored runtime help
- command-family-specific help behavior

At that point, its default UX becomes a liability.

### Upstream TOON behavior vs CLI contract

The selected TOON library works, but its exact header formatting is not fully
aligned with what I would pick as the long-term canonical xcron output. That is
why the wrapper exists.

### Hook schema uncertainty on the Codex side

Claude had an obvious local settings structure to anchor on.
Codex had a feature flag and config surface, but no locally available sample
hook file in this environment.

That pushed the implementation toward a conservative, repo-local installer with
tests around the generated file shape rather than deep assumptions about a
globally documented schema.

### Auto-install side effects during tests

If hook self-installation runs unguarded in tests, the CLI becomes
side-effect-heavy and flaky. Explicit guardrails were necessary.

## If I Were Starting From Scratch

This is the section I would hand directly to teams starting a greenfield or
near-greenfield agent-facing CLI.

### 1. I would define the contract before writing any command shells

I would start with:

- one command taxonomy
  - home
  - list
  - detail
  - mutation
  - help
- one error envelope
- one field selection model
- one truncation model
- one no-op model

Then I would generate or scaffold command shells around that contract.

### 2. I would build a dedicated CLI response model, not use loose dicts

In xcron, the presenter currently works over Python dict payloads. That was
pragmatic and fast, but if I were starting clean I would introduce typed
response envelopes such as:

- `HomeResponse`
- `ListResponse[T]`
- `DetailResponse`
- `MutationResponse`
- `ErrorResponse`

That would improve:

- consistency
- validation
- discoverability
- test ergonomics

### 3. I would not let `argparse` be the help/reference source at all

I would still use a parser library for argument handling, but I would treat:

- runtime help content
- examples
- field descriptions
- next-step hints

as first-class authored content from day one.

### 4. I would design list/detail field sets as data, not scattered constants

Right now, command field sets are defined as module-level constants in command
shells. That works, but from scratch I would centralize them in a schema
registry such as:

- `libs/services/cli_contracts.py`

with one declarative contract per command.

### 5. I would unify hook installation behind a clearer public command

I would likely make hook management an explicit public group from the start:

- `xcron hooks install`
- `xcron hooks status`
- `xcron hooks repair`

and then choose whether auto-install remains on by default.

### 6. I would choose package metadata conventions more cleanly

This refactor had to adjust packaging after the fact to include `resources`.
From scratch, I would define package-data strategy early and avoid retrofitting
it into an existing setuptools layout.

## If I Were Hardening The Current AXI Support

This is the “keep the same direction, but make it production-grade” section.

### 1. Move from presenter helpers to a declarative command contract registry

The current implementation works, but the field and payload rules are still
distributed across command modules.

I would introduce:

- a central registry of command contracts
- schema metadata for:
  - allowed fields
  - nested fields
  - truncation rules
  - next-step hint generation
  - default visible fields

That would reduce duplication and drift.

### 2. Introduce typed response envelopes

Even without a full rewrite, I would move away from free-form payload dicts and
toward typed response models. That would make it easier to reason about the
allowed output shapes and catch regressions earlier.

### 3. Separate command mapping from command execution even more cleanly

Some command modules still do too much translation inline. I would add a thin
presentation mapping layer such as:

- `libs/services/cli_mappers.py`

so command shells become almost pure glue:

- parse args
- call action
- map result to response model
- render response

### 4. Tighten hook management

The current hook support is intentionally conservative. To harden it, I would
add:

- hook status inspection
- explicit repair command
- conflict detection with existing non-xcron hooks
- better session-end capture beyond a timestamped JSONL stub

### 5. Add end-to-end installed-binary tests

`uv build` proves packaging, but I would go further and add tests that install
the wheel in an isolated environment and exercise:

- `xcron --help`
- bare `xcron`
- one list command
- one detail command
- hook install

### 6. Make auto-install more policy-aware

Right now the best-effort auto-install is project-sensitive, but still fairly
simple. I would refine this with:

- explicit opt-out env var
- explicit repo config toggle
- command to show whether hooks are installed or stale

### 7. Improve docs synchronization rules

The runtime help is now authoritative, but README and skill drift can still
happen. I would add one lightweight verification rule or test that asserts
critical concepts are present in:

- runtime help
- user guide
- relevant skills

## What I Would Redesign Or Refactor Next

If the current path continues, these are the highest-value refactors.

### Command contract registry

This is the single most important structural improvement left.

Today:

- field sets live in command modules
- payload shaping is partly local
- nested-field behavior is partly convention

Next step:

- one central, declarative registry for command contract metadata

### Response model typing

This would remove a lot of accidental flexibility and make command migration in
other projects faster and safer.

### Help templating strategy

Right now help pages are all Markdown, which is appropriate. If multiple
projects adopt the same pattern, I would extract a small shared convention for:

- examples
- generated flag sections
- reusable common snippets

without overcommitting to full Jinja templating everywhere.

### Hook file schema abstraction

The installer currently knows about:

- repo-local Codex config file conventions
- Claude settings JSON conventions

I would separate that into:

- generic hook target adapters
- one adapter per app

so future hook targets can be added without growing one monolithic installer.

## What Components Or Libraries I Would Replace

This section is intentionally concrete.

### 1. `argparse`

Would I replace it?

- Not immediately, but probably eventually.

Why:

- it is fine for parsing
- it becomes awkward once you need full control over:
  - help rendering
  - usage failures
  - subcommand-specific UX
  - richer argument metadata

Alternatives:

- `click`
  - strong ecosystem
  - pleasant command definition
  - still somewhat human-first
- `typer`
  - better typing ergonomics
  - decent for modern Python CLIs
  - still sits on Click
- `cloup`
  - if structured help and option grouping matter more

Recommendation:

- For greenfield: I would seriously consider `typer` or `click`
- For existing CLIs like xcron/xqueue/xfind: only replace `argparse` if the
  command surface is already moving significantly; otherwise keep the parser and
  own the UX above it

### 2. `python-toon`

Would I replace it?

- Possibly, if AXI becomes strategic across multiple repos.

Why:

- it works
- but its output details are not necessarily the exact long-term canonical
  format we would want

Alternatives:

- keep `python-toon`, but fork or wrap more aggressively
- build a tiny in-house encoder for the subset of TOON patterns we actually use
  across internal CLIs

Recommendation:

- For one repo: keep it wrapped
- For a family of agent-facing CLIs: strongly consider a small shared in-house
  encoder layer with deterministic formatting and narrower surface area

### 3. Ad-hoc dict payload shaping

Would I replace it?

- Yes.

Alternative:

- Pydantic models or dataclasses for response envelopes

Why:

- response shapes become self-documenting
- field filtering and test assertions become easier to reason about

Recommendation:

- If hardening current AXI support, this is worth doing

### 4. Manual JSON/TOML hook config mutation in one file

Would I replace it?

- Not with an external dependency immediately, but I would refactor the code.

Alternative:

- app-specific adapter classes
- possibly `tomlkit` for preserving TOML layout if that becomes important

Why:

- current direct file mutation is pragmatic
- but preserving user config style/comments may matter more over time

Recommendation:

- Introduce adapters first
- adopt `tomlkit` only if preserving formatting becomes a real requirement

### 5. Runtime help assembly strategy

Would I replace it?

- Not the concept, but the implementation could evolve.

Alternative:

- declarative help metadata + authored markdown body + generated examples

Why:

- current approach works
- but if three or four sibling CLIs adopt it, a shared help composition layer
  becomes valuable

## Practical Guidance For xqueue / xfind

If another team is about to do the same migration, the recommended playbook is:

1. Write one AXI migration contract doc before editing code.
2. Keep the action/domain layer intact if it already returns structured data.
3. Add one parser wrapper, one presenter layer, one output adapter, one help
   renderer.
4. Move detailed help into packaged runtime resources before rewriting every
   command.
5. Implement no-op semantics at the mutation source, not in presentation.
6. Add a content-first home view early.
7. Rewrite tests around the new contract, not old string snapshots.
8. Verify installed/package execution, not only source-tree execution.
9. Treat session hooks as infrastructure with tests, not just documentation.

## Bottom Line

The xcron migration succeeded because the work stayed disciplined:

- contract first
- architecture preserved
- shared mechanisms extracted
- tests rewritten to match the new reality
- packaging and hooks treated as real product surface

For sibling projects, the highest-value insight is that AXI support should be
implemented as reusable CLI-edge infrastructure, not as a series of per-command
string rewrites.
