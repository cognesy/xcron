# xcron module-first isolation refactor

## Purpose

Close the remaining distance between xcron's current shape and the house
standard in
`_kb-docs/stepping-stones/templates/agentic-python-multichannel-app`.

The capability-first refactor
([2026-08-03-capability-first-refactor](../2026-08-03-capability-first-refactor/README.md))
introduced capability packages, a typed scheduler port, a runtime composition
root, and the `Xcron` SDK. It deliberately stopped at "capability grouping plus
one verified Level 1 module" and left the horizontal `libs/services/` bucket in
place as a brownfield remainder.

This plan finishes that migration: every capability becomes a Level 1 module
with one owner for its code, state, resources, and tests; the CLI projection
cluster moves to the channel that owns it; the workspace and configuration
contracts become explicit; and enforcement moves from a single hand-written
test file to declared, mechanically checked contracts.

## Why now

The measured evidence in [00-current-state.md](00-current-state.md) shows the
failure smells the standard names explicitly:

- `libs/services/` holds 3,855 lines across 21 modules — more code than all
  five capability packages combined (2,349 lines) — with no declared owner.
- Reconciliation's implementation spans two top-level owners: its port and use
  cases live in `libs/capabilities/reconciliation/`, but the adapters that
  implement that port live in `libs/services/backends/` and import back into
  the capability for `DeploymentPlan`.
- Two capabilities (`reconciliation`, `operations`) both write one metrics
  state family through a shared service.
- The CLI's projection cluster (1,299 lines: contracts, responses, mappers,
  presenter, TOON/tmux/help renderers) sits under `libs/` and is held in place
  only by an import-direction convention.
- Project-root resolution accepts any directory containing `schedules/`; there
  is no validated workspace marker.
- The wheel ships no `py.typed`, and `typer`/`rich` are mandatory runtime
  dependencies of the embeddable SDK.

Each of these is a named finding in `MODULE-ISOLATION.md`,
`WORKSPACES-AND-CONFIGURATION.md`, or `CONVENTIONS-AND-GUARDRAILS.md`, not a
stylistic preference.

## Scope

In scope:

1. Dissolve `libs/services/` into the modules that own each mechanism.
2. Give every capability a module card, a public surface (`api.py` +
   `contracts.py`), owned resources, and a module-owned test lane.
3. Move the CLI projection cluster into `apps/cli/` and split the 805-line
   Typer shell by command group.
4. Introduce the validated workspace marker and an explicit root-resolution
   precedence.
5. Introduce an app-owned XCFG adapter and a strict `Settings` model.
6. Fix packaging: `py.typed`, CLI dependencies as an extra, module-owned
   packaged resources, and a wheel-manifest check.
7. Replace the single architecture test file with declared Import Linter
   contracts plus per-module public-surface checks with planted negatives.
8. Record the plane map, channel parity matrix, and state ownership.
9. Retire the `libs/actions` compatibility shim and the dead `libs/infra`
   package; correct the stale layering contract in `AGENTS.md`.

Out of scope (explicit non-goals):

- No REST channel, no FastAPI, no web application. The standard says add them
  when remote, multi-user, or multi-language use is real. It is not.
- No Level 2 (separate distributions) or Level 3 (process isolation). `cron`
  and `launchd` share xcron's release, dependency, and failure domain; the
  typed in-process registry remains the correct tier.
- No plugin platform, entry-point discovery, or extension manifests.
- No change to the AXI CLI contract: commands, flags, TOON/JSON/tmux output,
  exit codes, and structured error bodies stay byte-compatible.
- No change to the schedule language, YAML schema, artifact ownership markers,
  derived-state semantics, or native scheduler behaviour.
- No change to the Go-rewrite public contract in
  `docs/dev/go-rewrite-contract.md`.

## Decisions

1. **Module-first layout wins over layer-first.** Each capability keeps its
   complete vertical slice — contracts, domain rules, actions, ports,
   adapters, resources, tests — under one directory. Layers apply inside the
   module.
2. **`libs/services/` is dissolved, not renamed.** Every module in it is
   assigned to exactly one owner: a capability, the CLI channel, or a genuinely
   shared leaf. Nothing stays because moving it is inconvenient.
3. **`shared/` is a strict leaf.** It may hold observability, clock/identity
   primitives, and stable value types with several real owners. It may not hold
   workflows, persistence, or capability-specific results.
4. **The CLI owns its projections.** `cli_contracts`, `cli_responses`,
   `cli_mappers`, `axi_presenter`, `toon_renderer`, `tmux_renderer`, and
   `help_renderer` move under `apps/cli/`. Import direction stops being the
   only thing keeping them channel-local.
5. **One state family, one writer.** The metrics store gets a single owning
   module; reconciliation records outcomes through that module's public
   command rather than constructing `MetricsService` directly.
6. **Workspace identity is validated, never inferred.** A `marker.toml` under
   the project's xcron directory identifies product and schema. A directory
   that merely contains `schedules/` is no longer sufficient evidence.
7. **Configuration goes through one app-owned XCFG adapter.** Capability code
   consumes a strict `Settings` model and never reads the environment.
8. **Enforcement is declared, not implied.** Import Linter contracts plus
   public-surface scanners with planted negative cases replace ad-hoc
   assertions.
9. **Compatibility shims are time-boxed.** `xcron_libs.actions` is deleted in
   this plan's Phase 6 after tests migrate; it is not carried indefinitely.

## Open decisions for the maintainer

These change the public import surface and are recorded rather than assumed.
Phase 0 resolves them before any code moves.

| # | Question | Recommendation |
| --- | --- | --- |
| 1 | Rename import packages `xcron_libs` / `xcron_cli` / `xcron_resources` to one product package `xcron` with `xcron.channels.cli`? | Yes, in a dedicated final phase with a one-release shim. The current names expose repository layout (`libs`, `apps`) as the public API, which the standard's public-naming rule forbids. |
| 2 | Adopt XCFG now, or keep the hand-written loader and only add the strict `Settings` model? | Adopt XCFG (pin an approved tag; portfolio adopters are on `v0.3.0`–`v0.4.0`). xcron already has three layers in practice: packaged defaults, `~/.xcron`, and project. |
| 3 | Introduce the workspace marker as required, or as an optional advisory file for one release? | Advisory for one release: write it on `init`, warn on absence, refuse only from the following release. xcron already has live projects on disk. |

## Documents

- [00-current-state.md](00-current-state.md) — measured evidence, with the
  commands used to produce it.
- [01-gap-analysis.md](01-gap-analysis.md) — rule-by-rule comparison against
  the template, with a verdict per rule.
- [02-target-architecture.md](02-target-architecture.md) — target layout,
  module cards, dependency law, and public surfaces.
- [03-execution-plan.md](03-execution-plan.md) — ordered phases, each a
  separately reviewable stone with its verification command.
- [04-guardrails-and-acceptance.md](04-guardrails-and-acceptance.md) —
  enforcement contracts, test lanes, and the definition of done.
- [05-plane-map.md](05-plane-map.md) — filled plane map, state ownership,
  degraded behaviour, and the channel parity matrix.

## Tracking

Create a Beads epic with one task per phase and explicit blocking
dependencies, mirroring the shape used by the previous refactor
(`xcron-c81.1` … `xcron-c81.5`). Do not run `bd migrate` or `bd bootstrap`
without designated-migrator authority; if the shared database refuses safe
writes, record the exact gate and stop.
