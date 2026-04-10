# xcron AXI Refactoring Lessons

Date: 2026-04-10

## Purpose

Capture the practical lessons from xcron's CLI refactoring journey so teams
working on sibling tools such as `xfind`, `xqueue`, and similar agent-facing
CLIs can reuse the good decisions and avoid the bad ones.

This note covers:

- what worked in the first AXI migration
- what turned out to be the wrong level of abstraction
- why the follow-up migration moved to Typer, Rich, and Pydantic
- what architecture patterns are worth copying
- what sequencing and migration strategy reduced risk

## Executive Summary

The biggest lesson is:

> Separate **command declaration** from **machine-output policy**.

The initial AXI migration improved the user and agent experience, but it also
started pulling too much command-definition behavior into custom infrastructure.
That was the key mistake.

The cleaner end state was:

- **Typer** owns command declaration, grouping, options, and parser-facing help
- **Pydantic** owns typed response envelopes
- **Rich** owns human-facing help rendering
- **TOON** remains the machine-facing output contract
- the action layer stays untouched

That split gave better developer ergonomics and a cleaner codebase.

## What Worked In The First AXI Migration

These ideas were good and should be reused.

### 1. Contract-first planning

Writing the contract down before coding reduced ambiguity.

Why it worked:

- forced explicit decisions on output shape, truncation, no-op behavior, and
  help semantics
- made task planning realistic
- made later refactors easier because the intent was recorded

Recommendation:

- always start an AXI refactor with a concrete plan document
- treat it as executable architecture, not project prose

### 2. Preserve the action layer

xcron already had a useful thin-shell -> action -> service architecture.

Keeping `libs/actions/` stable was the right move because it meant:

- business logic did not churn during shell/framework changes
- migration risk stayed at the CLI edge
- future framework swaps remained possible

Recommendation:

- if the action layer already returns structured results, do not rewrite it
- do the migration at the shell/model/render boundary

### 3. Introduce a real output boundary

Keeping TOON behind a dedicated adapter was the right design choice.

Why it worked:

- isolated the third-party dependency
- prevented output-format logic from leaking through the codebase
- made later Rich/Pydantic integration much easier

Recommendation:

- always put machine-output formatting behind one small adapter/service
- do not let commands or actions call the third-party output library directly

### 4. Resource-backed help was the right direction

Moving command reference content under `resources/help/` was a good call.

Why it worked:

- made runtime help a real product surface
- separated “docs for humans” from “reference content for the CLI”
- made later Rich-based help migration much cleaner

Recommendation:

- authored help should live with runtime resources, not only in `docs/`

## What Turned Out To Be The Wrong Direction

This is the most important part for other teams.

### 1. Overbuilding the command-contract layer

The first hardening pass pushed too much into custom command contracts:

- command identity
- command kind
- parser-facing help keys
- shell behavior
- output behavior

That started to overlap with what Typer already does better.

Why it was flawed:

- command declaration and parser help are framework responsibilities
- custom infra became a shadow CLI framework
- developer DX suffered because too much had to be encoded manually

Recommendation:

- if you adopt Typer, keep your contract layer narrow
- it should only own machine-output policy, not command declaration

### 2. Using parser-specific infrastructure as long-term architecture

The initial `argparse` customization was useful as a bridge, but it was not a
good long-term foundation once developer DX became a first-class goal.

Why:

- parser wrappers become custom framework code
- command registration stays heavy
- help composition becomes awkward

Recommendation:

- use a real CLI framework for command declaration once the tool outgrows
  bootstrap/prototype mode

### 3. Treating “better output” and “better command authoring” as the same problem

They are different.

- TOON, field filtering, truncation, and machine errors are output-policy
  concerns
- commands, subcommands, options, and help flow are declaration concerns

When those were mixed, the code got heavier than necessary.

Recommendation:

- split those concerns early

## Why The Typer / Rich / Pydantic Stack Was Better

### Typer

Typer was better for:

- subcommand declaration
- argument and option typing
- shell ergonomics for maintainers
- reducing shell boilerplate
- better default help behavior

Key lesson:

- do not rebuild command-declaration ergonomics inside your own service layer

### Rich

Rich was better for:

- rendering authored help content
- human-facing markdown output
- giving the CLI a better terminal-native help experience

Key lesson:

- Rich should improve the human path
- it should not replace TOON as the machine contract by default

### Pydantic

Pydantic was better for:

- typed response envelopes
- serialization via `model_dump()`
- stronger validation
- easier schema evolution

Key lesson:

- once a CLI has many structured responses, ad-hoc dicts and hand-rolled model
  dumping become a maintenance burden

## Target Architecture To Copy

For future tools, the clean architecture should look like this:

- command declaration:
  - Typer
- action layer:
  - existing use-case layer
- response modeling:
  - Pydantic models
- mapping:
  - action result -> response model
- machine output:
  - TOON adapter
- human help/rendering:
  - Rich + authored help resources
- operational integration:
  - separate hook subsystem

In other words:

1. Typer owns command declaration
2. Pydantic owns structured response models
3. Rich owns human-facing help/rendering
4. TOON owns machine-facing output
5. Actions remain separate and reusable

## Recommended Migration Sequence

This sequence worked well and should be reused.

### Phase 1: Protect the business logic

- identify and preserve the action layer
- do not mix shell migration with use-case refactors

### Phase 2: Introduce typed response models

- move response structure into typed models first
- keep mapper boundaries explicit

### Phase 3: Centralize output rendering

- unify machine-output rendering first
- only then add the human-facing rendering path

### Phase 4: Introduce Typer in parallel

- add a parallel shell first
- migrate the lowest-risk read-only commands first

### Phase 5: Migrate the full command surface

- after read-only commands work, move stateful commands
- keep tests focused on behavior, not shell internals

### Phase 6: Retire obsolete shell infrastructure

- remove the old shell only after the new shell is proven
- do not keep two shells around indefinitely

## Testing Lessons

### 1. Test behavior, not framework internals

The most useful tests were:

- command behavior tests
- output-shape tests
- mutation/no-op tests
- help behavior tests

The least useful tests were:

- framework-implementation-specific tests that froze old shell assumptions

Recommendation:

- test the stable command contract
- avoid tests that overfit to the temporary shell implementation

### 2. Keep machine-output and help tests separate

This reduced confusion:

- TOON tests verify machine-facing behavior
- Rich/help tests verify human-facing help rendering

Recommendation:

- split those test concerns explicitly

### 3. Migration aliases should be temporary

Temporary aliases such as `xcron-typer` can be useful during a migration, but
they should be removed once the main entrypoint has switched.

Recommendation:

- treat migration aliases as disposable scaffolding

## Hook-System Lessons

The hook subsystem should remain separate from the shell framework.

Why:

- hooks are operational integration, not command declaration
- they should survive framework swaps
- they should be testable independently of the CLI declaration layer

Recommendation:

- implement hook targets as app-specific adapters
- keep hook install/status/repair as explicit operations
- avoid hiding hook behavior inside shell registration logic

## Cleanup Lessons

After the big migration lands, always do a cleanup pass.

Things to look for:

- compatibility wrappers using testing helpers in production code
- duplicate script aliases
- parser-era scaffolding/templates
- contract metadata that still owns framework-specific concerns
- docs that still describe the previous shell stack

Recommendation:

- do not stop immediately after “tests pass”
- do one final leftover-review pass before declaring the migration complete

## Concrete Advice For xfind / xqueue

If a sibling project has not started yet:

- start directly with Typer + Pydantic + TOON adapter
- use Rich for help from the beginning
- avoid building a big parser-centric contract layer

If a sibling project is already on raw argparse:

- preserve the action layer
- add typed response models first
- add a rendering boundary
- then migrate to Typer in parallel
- remove the old shell only after the Typer shell is fully proven

## What To Avoid Next Time

- Do not let custom command contracts own parser/help declaration concerns.
- Do not use testing helpers as runtime execution infrastructure.
- Do not leave migration aliases and templates around after cutover.
- Do not keep the old shell “just in case” once the new shell is verified.
- Do not mix command-framework migration with business-logic refactors.

## Bottom Line

The most reusable lesson from xcron is:

> Use a real CLI framework for command declaration, a real model layer for
> structured responses, and a small dedicated output adapter for machine-facing
> formats. Keep those concerns separate.

For agent-facing Python CLIs, the stack that emerged cleanest here was:

- Typer
- Pydantic
- Rich
- TOON adapter
- stable action layer underneath

That is the pattern I would recommend other teams copy unless they have a very
strong reason not to.
