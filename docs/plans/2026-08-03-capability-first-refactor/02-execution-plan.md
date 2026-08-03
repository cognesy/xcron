# Execution plan

Each phase is a separately reviewable stone. Complete and verify it before
starting its dependent phase.

## Phase 0 — baseline and tracking

1. Run the deterministic core suite before implementation and record the
   result.
2. Create the Beads epic and the dependent tasks below. If the shared Beads
   database refuses safe writes, record the exact migration gate and do not run
   `bd migrate` or `bd bootstrap` without designated-migrator authority.
3. Keep the local QMD index ignored (`.qmd/`) as developer-local derived data.

Verification: `uv run pytest`, `git diff --check`, and `git status --short`.

Execution result: the user explicitly designated this checkout as the
migrator. The pending database state was preserved, the schema migration was
completed, and the migrated database was pushed before tracker writes began.

## Phase 1 — break the reverse backend dependency

1. Introduce the backend-neutral deployment contract and typed scheduler port
   under `capabilities/reconciliation` (or the lowest leaf package justified by
   the imports).
2. Change cron and launchd adapters to accept that contract rather than
   `PlanProjectResult`.
3. Move backend selection into an explicit scheduler registry and use it from
   reconciliation actions for status, apply, inspect, and prune.
4. Preserve current function signatures through compatibility delegates and
   retain the plan/status/apply semantics exactly.
5. Add unit tests for registry selection and architecture tests that make the
   old service-to-action import impossible to reintroduce.

Verification: relevant planner, status, cron, and launchd backend tests plus
`uv run pytest`.

## Phase 2 — capability facades and public SDK

1. Create capability packages for reconciliation, jobs, operations, and hooks;
   move use-case ownership there incrementally or delegate through clearly
   marked facades where a physical move would be pure churn.
2. Keep `xcron_libs.actions` as compatibility re-exports with no business
   logic of its own.
3. Add `xcron_libs.sdk.Xcron`, grouped APIs, typed options/errors, lifecycle
   guard, and explicit backend-registry injection for deterministic tests.
4. Export only intentional public names from `xcron_libs` and include the new
   packages in wheel packaging.
5. Add SDK lifecycle, grouped API, injection, and import-boundary tests.

Verification: SDK tests, action compatibility tests, installed-package/import
smoke, and full core suite.

## Phase 3 — make CLI a pure channel

1. Split the Typer command declarations by command group if this reduces the
   current 806-line module without changing option parsing/help.
2. Replace direct action imports/calls with a short CLI client helper that
   opens `Xcron` from resolved project options and maps typed SDK errors at the
   output boundary.
3. Keep `Output`, stdout/stderr, and exit-code decisions in `apps/cli`. Retain
   the existing contracts, mappers, and TOON/JSON/tmux renderers as CLI-owned
   leaf modules under `libs/services/`; enforce the boundary by allowing only
   that projection cluster and the CLI channel to consume those modules in
   production code.
4. Add CLI-to-SDK wiring tests and retain existing CLI contract cases.

Verification: `uv run xcron --help`, `uv run xcron jobs --help`, focused CLI
tests, `git diff --check`, and full core suite.

## Phase 4 — documents and acceptance review

1. Update `docs/dev/architecture.md` and `docs/dev/go-rewrite-contract.md` to
   describe capability ownership while retaining the thin-channel -> action ->
   adapter separation.
2. Record the no-plugin decision, future systemd addition path, SDK contract,
   migration compatibility promise, and architecture guardrails.
3. Inspect the final import graph and confirm every core operation still uses
   the correct plan/status/apply source of truth.
4. Close completed Beads tasks and epic after their recorded verification
   commands pass.

Verification: full core suite, CLI smokes, diff check, and a final clean
architecture-import test run.

## Intended Beads dependency graph

```text
epic
  └─ phase 0: baseline/tracking
       └─ phase 1: reconciliation port and adapters
            └─ phase 2: capability facades and SDK
                 └─ phase 3: CLI composition
                      └─ phase 4: docs and acceptance review
```

The implemented graph is epic `xcron-c81`, with child tasks `xcron-c81.1`
through `xcron-c81.5` and explicit blocking dependencies in the order shown.
The migration was performed only after the user supplied designated-migrator
authority.
