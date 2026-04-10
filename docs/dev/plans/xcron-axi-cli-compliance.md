# xcron AXI CLI Compliance Plan

## Goal

Bring `xcron`'s CLI into full alignment with the `axi` skill while preserving
the existing thin-shell -> action -> service architecture and the stable
operator command surface defined in `docs/dev/go-rewrite-contract.md`.

This plan belongs to epic `xcron-sd4`.

The target outcome is an agent-first CLI with:

- TOON on stdout by default
- small default schemas with explicit `--fields` expansion
- structured stdout errors and usage failures
- definitive empty states and idempotent mutation responses
- a content-first home view when `xcron` runs without subcommands
- contextual help backed by runtime resource files under `resources/help/`
- automatic Codex/Claude session hook support

## Current State

The current Python prototype already has the right architectural seam for an AXI
migration:

- shells live under `apps/cli/`
- actions return structured dataclasses under `libs/actions/`
- reusable services live under `libs/services/`
- documentation and static assets already belong in `docs/` and `resources/`

The gap is not that `xcron` lacks structure. The gap is that its CLI
presentation layer is still conventional `argparse` text:

- `apps/cli/main.py` requires a subcommand and exits with `argparse` usage
  errors when invoked bare
- each command shell prints ad-hoc human text directly to stdout
- `--help` is parser-generated rather than authored as an explicit runtime
  contract
- detailed command guidance lives only in `docs/user/README.md`
- there is no output abstraction for TOON, field selection, truncation, or
  contextual next-step hints
- there is no hook installation or session bootstrap integration for Codex or
  Claude Code

## Constraints

- Preserve the stable command surface from
  `docs/dev/go-rewrite-contract.md`:
  - `validate`
  - `plan`
  - `apply`
  - `status`
  - `inspect`
  - `jobs list|show|add|update|enable|disable|remove`
  - `prune`
- Keep thin shells thin. Shells should translate CLI input into action calls and
  presentation requests; business logic stays in actions and services.
- Keep internal domain and action results structured in Python objects and
  convert to TOON only at the output boundary.
- Preserve the project-scoped source-of-truth model under
  `resources/schedules/`.
- Keep the default home view safe: it should not mutate scheduler state.
- Static help assets should live under `resources/`, not `docs/`.

## AXI Gap Assessment

### 1. Token-efficient TOON output

Current gap:

- Every command writes custom text lines directly with `print(...)`.
- There is no common serializer or output envelope.
- The project has no TOON dependency or local TOON encoder.

Impact:

- No command is AXI-compliant on stdout.
- Output schemas cannot be standardized across commands.

### 2. Minimal default schemas

Current gap:

- List commands output whatever the shell happens to print.
- There is no `--fields` flag or schema registry.
- Detail commands have no explicit compact-vs-expanded modes.

Impact:

- Agents pay for unused fields.
- Adding richer output later would risk breaking parsability.

### 3. Content truncation with escape hatches

Current gap:

- `inspect` prints raw snippets in full.
- Help content is outside the runtime CLI entirely.
- There is no `--full` mode or truncation metadata.

Impact:

- Detail views can become arbitrarily expensive on stdout.
- Agents cannot tell whether content is partial or complete.

### 4. Pre-computed aggregates

Current gap:

- List views do not report totals consistently.
- Mutation commands do not report lightweight summaries that inform next steps.
- The home view does not exist, so there is no compact dashboard at startup.

Impact:

- Agents need follow-up calls for basic counts and orientation.

### 5. Definitive empty states

Current gap:

- Some commands simply print nothing beyond a header when collections are empty.
- `xcron` with no subcommand fails with a usage error instead of returning a
  meaningful empty or home state.

Impact:

- Empty results are ambiguous and not self-describing.

### 6. Structured errors and exit codes

Current gap:

- `argparse` writes usage failures to stderr in its own format.
- Shell validation errors are plain text, not structured AXI errors.
- Suggestions are generally absent.
- Mutations are not consistently modeled as no-op acknowledgements when the
  desired state already exists.

Impact:

- Errors are difficult for agents to recover from automatically.
- Usage failures do not follow the AXI stdout contract.

### 7. Ambient context via session hooks

Current gap:

- No `.codex` or `.claude` hook integration exists.
- No auto-install or path-repair mechanism exists.
- No directory-scoped startup dashboard exists.

Impact:

- Agents always begin blind and spend extra calls orienting themselves.

### 8. Content-first top-level invocation

Current gap:

- `xcron` without arguments exits 2 and prints `argparse` usage.

Impact:

- The top-level command violates AXI directly.

### 9. Contextual disclosure

Current gap:

- List and mutation responses do not include suggested next commands.
- No command carries forward selection flags into help hints.

Impact:

- Agents must infer the next command surface manually.

### 10. Consistent help backed by resources

Current gap:

- Root/group/leaf `--help` exists, but only through `argparse`.
- Rich command guidance lives in `docs/user/README.md`, not runtime resources.
- There is no `resources/help/` tree, no renderer, and no packaging contract
  for help assets.

Impact:

- Help is shallow at runtime and duplicated in docs instead of sourced from one
  reusable place.

## Codebase Observations

- `apps/cli/main.py` is the right place to centralize parser, top-level home
  view, global flags, and error handling.
- `apps/cli/commands/_common.py` is a natural starting point for replacing raw
  `print(...)` helpers with structured presentation helpers.
- `libs/actions/*` already return structured dataclasses that can be adapted
  into output models without moving business logic into the shells.
- `pyproject.toml` currently ships only the Python packages; help resources will
  need explicit packaging treatment if the installed console script is expected
  to load them reliably.
- `docs/user/README.md` currently contains the detailed narrative help that
  should move into runtime-addressable resources under `resources/help/`.

## Recommended Architecture

### 1. Add a dedicated AXI presentation layer

Introduce a small service slice responsible for turning action results into a
  stable output contract:

- `libs/services/axi_presenter.py`
- `libs/services/toon_renderer.py`
- `libs/services/help_renderer.py`

Suggested responsibilities:

- normalize result dataclasses into plain dict/list payloads
- enforce per-command default schemas
- apply truncation policies and `--full`
- render TOON on stdout and optionally plain text for debugging if retained
- render structured errors, empty states, and help hints

This keeps shells thin while preventing presentation logic from leaking into
actions.

### 2. Install TOON support behind an xcron-owned adapter

Recommended path:

- add `python-toon` as the initial runtime dependency
- wrap it behind `libs/services/toon_renderer.py`
- keep the adapter responsible for deterministic field ordering and any
  xcron-specific normalization

Why this shape:

- it satisfies the explicit request to install TOON support
- it preserves the option to replace the library later without changing shells
  or tests
- it keeps internal logic on Python objects, with TOON only at the output
  boundary

### 3. Define command output contracts explicitly

Each command should have a documented output shape and affordances:

- `xcron` home:
  - executable path
  - one-line description
  - selected project/manifest/backend
  - compact counts and recent plan/status summary
  - next-step hints
- list views:
  - total count
  - compact row schema
  - `--fields` support
  - definitive zero-state messaging
- detail views:
  - compact default fields
  - truncation metadata
  - `--full`
- mutations:
  - target id
  - action outcome or no-op
  - follow-up hints when useful

### 4. Move detailed help to `resources/help/`

Create a runtime help content tree such as:

- `resources/help/root.j2`
- `resources/help/validate.md`
- `resources/help/plan.md`
- `resources/help/apply.md`
- `resources/help/status.md`
- `resources/help/inspect.md`
- `resources/help/prune.md`
- `resources/help/jobs/index.md`
- `resources/help/jobs/list.md`
- `resources/help/jobs/show.md`
- `resources/help/jobs/add.md`
- `resources/help/jobs/update.md`
- `resources/help/jobs/enable.md`
- `resources/help/jobs/disable.md`
- `resources/help/jobs/remove.md`

Markdown should be the default.

Use Jinja2 only where runtime interpolation is genuinely needed, especially for:

- collapsed executable path display such as `~/.local/bin/xcron`
- shared examples carrying current command names
- reusable snippets across root/group/leaf help pages

The goal is not to template everything. It is to keep authored help readable and
maintainable while supporting a few dynamic values.

### 5. Add an AXI-aware parser wrapper

`argparse` can still parse flags, but its default failure/help behavior should no
longer own the UX.

Recommended approach:

- subclass `argparse.ArgumentParser`
- override `error(...)` and help rendering paths
- route usage errors through structured stdout envelopes
- keep exit codes aligned with AXI:
  - `0` success and acknowledged no-ops
  - `1` command/runtime errors
  - `2` usage errors

### 6. Add self-installing session hooks

Add a small installation/check service that:

- detects Codex and Claude Code hook configuration files
- idempotently installs session-start hooks for a compact dashboard
- repairs absolute executable paths on subsequent invocations
- optionally installs session-end capture hooks for future context enrichment

The session-start payload should be intentionally small and directory-scoped.

## Implementation Slices

### Slice 1: Foundation and contract definition

- introduce the AXI presenter and TOON adapter
- add global output flags such as `--fields` and `--full` where appropriate
- define explicit output schemas for home, list, detail, and mutation responses

### Slice 2: Help resource migration

- move detailed help content out of `docs/user/README.md` and into
  `resources/help/`
- implement markdown/Jinja help rendering for root, group, and leaf `--help`
- keep README as overview documentation and point to runtime help behavior

### Slice 3: Command migration

- convert every shell command to return structured envelopes through the AXI
  presenter
- implement empty states, truncation, counts, no-op responses, and contextual
  hints
- add a content-first home view when `xcron` runs without subcommands

### Slice 4: Hooks and packaging

- add Codex/Claude hook installation and path repair
- ensure help resources ship with the installed package
- document and test installed-script behavior, not just source-tree execution

## Proposed Task Breakdown

1. Define the AXI command contracts and presentation architecture for `xcron`.
2. Install TOON support and implement an xcron-owned TOON rendering adapter.
3. Build the shared AXI shell layer: parser overrides, structured errors,
   contextual hints, empty states, `--fields`, and `--full`.
4. Migrate detailed help into `resources/help/` and render root/group/leaf help
   from Markdown or Jinja2 resources.
5. Convert the top-level home view and all existing commands to the AXI output
   model.
6. Add Codex/Claude session hook self-installation, packaging updates, and
   end-to-end verification.

## Verification Strategy

- extend CLI tests to assert stdout structure rather than ad-hoc strings
- add explicit tests for:
  - bare `xcron` home output
  - usage errors on stdout with exit code `2`
  - detail truncation and `--full`
  - list totals and zero states
  - `--fields` selection
  - root/group/leaf help sourced from `resources/help/`
  - hook installation idempotence and path repair
- run deterministic verification through `./scripts/verify-core.sh`
- keep any scheduler-touching verification explicit-only

## Risks

### Parser migration churn

Replacing default `argparse` help and error behavior can create noisy regressions.

Mitigation:

- centralize parser customization in one shell layer
- add root/group/leaf help and usage-error tests first

### TOON library mismatch

The selected TOON dependency may not provide the exact deterministic layout
needed for AXI-focused tests.

Mitigation:

- isolate it behind `libs/services/toon_renderer.py`
- keep xcron-specific schema shaping outside the third-party dependency

### Help drift between runtime and docs

Moving detailed help out of `docs/user/README.md` could create duplication if
README continues to carry full command walkthroughs.

Mitigation:

- keep README as overview and workflow guide
- treat `resources/help/` as the runtime source of truth

### Session hook overreach

Heavy session-start output would violate AXI's token-budget guidance.

Mitigation:

- keep the startup dashboard minimal
- include only compact counts/status plus a few next actions

## Open Questions

- Should TOON be the only stdout format, or should `text` remain as a
  transitional debug/testing format behind an explicit flag?
- Should the home view summarize `plan` state only, or include a lightweight
  `status` summary when backend inspection is cheap enough?
- Do we want Jinja2 only for the root help page, or also for command pages that
  share repeated example blocks?

## Recommendation

Proceed in the six-task order above.

The first three tasks create the reusable CLI infrastructure. The fourth task
turns help into a runtime resource system. The fifth task migrates user-facing
commands onto the new model. The sixth task finishes the agent ergonomics and
distribution details needed for full AXI compliance.
