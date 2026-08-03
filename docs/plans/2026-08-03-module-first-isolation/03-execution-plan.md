# Execution plan

Each phase is one separately reviewable stone. Complete, verify, and commit a
phase before starting its dependent phase. A phase that grows past its stated
scope is a signal to stop and re-plan, not to continue.

Every phase ends with:

```sh
./scripts/verify-core.sh
git diff --check && git status --short
```

Phase-specific verification is listed per phase and runs first.

## Phase 0 — decisions, baseline, and tracking

No code changes.

1. Resolve the three open decisions in [README.md](README.md#open-decisions-for-the-maintainer)
   and record the answers in this file's decision log below.
2. Record the baseline: current test count, `rg --files -g '*.py' | wc -l`, and
   the per-package line counts in [00-current-state.md](00-current-state.md).
3. Create the Beads epic and one task per phase with blocking dependencies in
   the order below. If the shared database refuses safe writes, record the
   exact gate; do not run `bd migrate` or `bd bootstrap` without
   designated-migrator authority.

Verification: `./scripts/verify-core.sh` recorded as the green baseline.

### Baseline record (2026-08-03, commit `e5bdadc`)

| Measurement | Value |
| --- | --- |
| Deterministic core suite | 165 passed in 5.28s |
| Python modules under `libs/`, `apps/`, `resources/` | 85 |
| Unowned `libs/services/` | 21 modules, 3,855 lines |
| All capability packages | 23 modules, 2,349 lines |
| Beads epic | `xcron-0wt`, tasks `xcron-0wt.1` … `xcron-0wt.10` |

`scripts/capture-cli-golden.sh` captures the AXI CLI surface — 36 files: every
command and group `--help`, `--version`, `validate` / `plan` / `jobs list` /
`jobs show` in both TOON and JSON, and the four exit-code cases. Two
consecutive captures are byte-identical, so any diff in a later phase is a real
contract change. Re-run it after every phase:

```sh
./scripts/capture-cli-golden.sh /tmp/xcron-golden-after
diff -ru /tmp/xcron-golden-baseline /tmp/xcron-golden-after
```

### Decision log

| # | Decision | Answer | Date |
| --- | --- | --- | --- |
| 1 | Rename import packages to a single `xcron` package | **Yes** — Phase 8 runs, with one-release deprecating shims for `xcron_libs`, `xcron_cli`, `xcron_resources` | 2026-08-03 |
| 2 | Adopt XCFG now | **Yes** — pin an approved tag; Phase 5 adds the app-owned adapter and strict `Settings` | 2026-08-03 |
| 3 | Workspace marker required or advisory for one release | **Advisory for one release** — `init` writes it; missing warns on stderr and proceeds; invalid or unsupported schema errors from day one | 2026-08-03 |

## Phase 1 — public surfaces and module cards, no code movement

Give every capability the shape `agent_hooks` already has, before anything
moves. This makes later phases pure relocation behind a stable surface.

1. Add `api.py` and `contracts.py` to `reconciliation`, `jobs`, `operations`,
   and `home`. Initially they may re-export from the existing implementation
   modules; result *ownership* moves into `contracts.py`.
2. Empty each capability's `__init__.py`; remove aggregate re-exports.
3. Repoint `libs/sdk/*`, `libs/runtime/composition.py`, and `libs/actions/*`
   at `api`/`contracts` only. No caller may reference `.apply`, `.planning`,
   `.status`, `.actions`, or `.scheduler_registry` from outside the module.
4. Write the five module cards from
   [02-target-architecture.md](02-target-architecture.md) into
   `docs/dev/architecture.md`.
5. Extend the public-surface scanner (currently `agent_hooks`-only) to every
   capability, with planted forbidden examples per module.

Verification:

```sh
uv run pytest tests/test_reconciliation_architecture.py tests/test_sdk.py
rg -n 'xcron_libs\.capabilities\.[a-z_]+\.(?!api|contracts)' libs apps
```

The `rg` result must be empty except for intra-module imports.

### Phase 1 result (2026-08-04)

Done. All five capabilities — `agent_hooks`, `home`, `jobs`, `operations`,
`reconciliation` — now expose exactly `api.py` and `contracts.py` behind a
docstring-only `__init__.py`. Result ownership moved into `contracts.py`
(reconciliation gained eight result types plus `UnknownSchedulerBackendError`;
`jobs`, `operations`, and `home` gained theirs). `libs/sdk/*`,
`libs/runtime/composition.py`, all ten `libs/actions/*` shims, and three test
modules were repointed. `tests/test_inspect_action.py` no longer monkeypatches
a private module: the stub backend now implements `collect_project_state` and
`schedule_errors`, so the real `status_project` runs.

The scanner is parameterised over all five modules and adds three new checks —
no source file outside a module imports below its surface, no package
initializer aggregates, and no module takes an undeclared cross-module edge
(`DECLARED_MODULE_EDGES`: `jobs → reconciliation`, `operations →
reconciliation`, nothing else). Planted negatives cover all eight forbidden
import forms per module. The cross-file scan was checked against a temporary
planted violation to confirm it is not vacuous.

- `./scripts/verify-core.sh`: 189 passed (was 165 — 24 new architecture cases).
- CLI golden: 36/36 files byte-identical to the Phase 0 baseline.
- Five module cards written into `docs/dev/architecture.md`.

Carried forward, unchanged from the plan: `metrics.json` still has two writing
capabilities (Phase 4), manifest writes still go through a shared service
(Phase 4), and workspace resolution is still inside `reconciliation` (Phase 5).
Each card's `isolation_level` states this rather than claiming Level 1.

## Phase 2 — the CLI takes ownership of its projections

1. Move `cli_contracts` → `apps/cli/contracts.py`, `cli_responses` →
   `apps/cli/responses.py`, `cli_mappers` → `apps/cli/mappers.py`.
2. Move `axi_presenter`, `toon_renderer`, `tmux_renderer`, `help_renderer`
   into `apps/cli/presenters/`.
3. Move `resources/help/` to `apps/cli/resources/help/` and update the
   packaged-data configuration.
4. Update `pyproject.toml` packages and package-data accordingly.
5. Add the architecture contract: nothing under `libs/` may import
   `xcron_cli`, in any import form.

This is a pure move: 1,299 lines change path, not content. Import updates are
mechanical.

Verification:

```sh
uv run pytest tests/test_cli_output.py tests/test_cli_contracts.py \
  tests/test_cli_mappers.py tests/test_axi_presenter.py \
  tests/test_toon_renderer.py tests/test_tmux_renderer.py \
  tests/test_help_renderer.py
uv run xcron --help && uv run xcron jobs --help && uv run xcron inspect --help
```

Help output must be byte-identical to the pre-phase capture.

## Phase 3 — reconciliation absorbs its adapters

1. Move `backends/cron_service` → `reconciliation/adapters/cron.py` and
   `backends/launchd_service` → `reconciliation/adapters/launchd.py`.
2. Move `wrapper_renderer` → `reconciliation/wrapper.py` and `state_store` →
   `reconciliation/state_store.py`.
3. Move `run_logged_subprocess` and `check_output_logged` out of
   `observability` into `reconciliation/adapters/process.py`; they have no
   other caller.
4. Move `libs/domain/diffing.py` → `reconciliation/domain.py`. Keep
   `libs/domain/` as manifest value types and normalization only.
5. Rename `scheduler_registry.py` → `registry.py` and `contracts.py`'s port
   definitions into `ports.py`, leaving `contracts.py` for the public
   request/result models.
6. Delete `libs/services/backends/`.

Verification:

```sh
uv run pytest tests/test_cron_backend.py tests/test_launchd_backend.py \
  tests/test_planning.py tests/test_status_projection.py \
  tests/test_wrapper_renderer.py tests/test_reconciliation_architecture.py
```

Move the same tests into `tests/modules/reconciliation/` in this phase and add
a fake-backend lane that imports no sibling implementation.

## Phase 4 — extract `manifest`, `shared`, and the metrics owner

1. Create `capabilities/manifest/` from `manifest_editor`, `schema_validator`,
   `hash_service`, and the manifest-loading half of `config_loader`. Move
   `resources/schemas/` under it.
2. Create `libs/shared/` from the remaining `observability` and
   `logging_config`; move `resources/logging/` under it. Record the leaf rule
   in `docs/dev/architecture.md`.
3. Move `MetricsService` into `operations/metrics_store.py`. Add
   `operations.api.record_outcome(...)` as the single public write command.
4. Add the `OutcomeRecorder` port to `reconciliation/ports.py`; wire the
   adapter in `libs/runtime/composition.py`. Remove every direct
   `MetricsService` construction from `reconciliation/`.
5. Fold `capabilities/home/` into `workspace/initializer.py` (created in
   Phase 5) or, if Phase 5 has not run, leave `home` untouched and defer this
   step to Phase 5.
6. Delete `libs/services/` and `libs/infra/`.

Verification:

```sh
uv run pytest tests/modules/manifest tests/modules/operations \
  tests/test_cli_metrics.py tests/test_validation.py tests/test_job_actions.py
rg -n 'xcron_libs\.services|xcron_libs\.infra' libs apps tests
```

The `rg` result must be empty.

## Phase 5 — workspace contract and layered configuration

Depends on decisions 2 and 3.

1. Create `capabilities/workspace/` with:
   - `marker.py` — write and validate `marker.toml`
     (`kind = "xcron-workspace"`, `schema = 1`, `created_by`);
   - `resolver.py` — precedence
     `explicit option > XCRON_PROJECT > nearest validated parent > typed error`,
     with `~/.xcron` as the explicit home fallback the CLI already relies on;
   - `paths.py` — typed `XcronHome` and `ProjectWorkspace` absorbing
     `logging_paths`, `resolve_project_state_dir`, and `resolve_metrics_path`;
   - `initializer.py` — idempotent init returning a typed change set
     (created / retained / migrated / conflicts), absorbing `init_home`.
2. Honour decision 3: for one release, a missing marker produces a structured
   warning on stderr and proceeds; an invalid or unsupported marker is an
   error with a recovery hint from the start.
3. Create `libs/configuration/` with `settings.py` (strict, `extra="forbid"`),
   `loader.py` (the only XCFG and `os.environ` reader), and `errors.py`.
4. Resolve workspace and settings once in `XcronRuntime`, before constructing
   capability services. Pass typed values down; delete every downstream path
   re-derivation and environment read.
5. Assert the durable-format version of `project-state.json` in a contract
   test, and add the same for the marker.

Verification:

```sh
uv run pytest tests/modules/workspace tests/configuration tests/contracts
uv run pytest tests/test_init_home.py tests/test_cli_home.py
```

New cases required: explicit/env/parent precedence; a directory containing
`schedules/` but no marker; malformed marker; unsupported schema version; init
idempotency and non-destructive `--force`; two workspaces open in one process;
every adjacent configuration-precedence edge; unknown keys rejected.

## Phase 6 — packaging, typing, and shim removal

1. Add `py.typed` to every distributed package and include it in package data.
2. Move `typer`, `rich`, and `python-toon` into a `cli` extra; keep the SDK's
   mandatory set to `PyYAML`, `jsonschema`, `pydantic`, and `structlog`. Keep
   `xcron = "xcron_cli..."` in `[project.scripts]` and document that the
   console script needs the `cli` extra.
3. Replace the hand-maintained `packages = [...]` with automatic discovery, or
   add a test that asserts the list equals the discovered set. Remove
   `xcron_libs.infra`.
4. Migrate the 15 test modules off `xcron_libs.actions`, then delete
   `libs/actions/` and its architecture-shim assertions.
5. Add the wheel check: build, install into a clean virtual environment,
   import `xcron_libs`, assert `py.typed` is present, assert no Typer import,
   and run the console script's `--help`.

Verification:

```sh
uv build && uv run --isolated --with dist/*.whl python -c \
  "import xcron_libs, importlib.resources as r; print(xcron_libs.__all__)"
uv run pytest tests/architecture
rg -n 'xcron_libs\.actions' libs apps tests
```

The `rg` result must be empty.

## Phase 7 — declared enforcement

1. Add Import Linter with, at minimum:
   - an `independence` contract across the six capability modules;
   - `forbidden` contracts: `libs/* -> xcron_cli`, `libs/sdk -> typer|rich`,
     `libs/domain -> everything`, `libs/shared -> capabilities`,
     `capabilities/* -> libs.configuration` (settings arrive as values);
   - a `layers` contract: `apps.cli > libs.sdk > libs.runtime > capabilities >
     libs.shared|libs.domain`.
2. Keep the AST public-surface scanner for the `api`/`contracts` rule, which
   an import graph alone cannot express, with planted negatives per module.
3. Split `tests/test_reconciliation_architecture.py` into
   `tests/architecture/` by concern and give it a name that matches its scope.
4. Add the parity lane: for each capability exposed on both channels, inject a
   spy and assert the CLI and SDK reach the same use case with equivalent
   inputs.
5. Wire Import Linter into `scripts/verify-core.sh`.

Verification:

```sh
uv run lint-imports
uv run pytest tests/architecture tests/parity
```

Each contract must be proven to fail: add a temporary forbidden import, watch
the gate fail, revert.

## Phase 8 — public naming (only if decision 1 is yes)

1. Introduce `src/xcron/` as the single import package: `xcron.capabilities`,
   `xcron.channels.cli`, `xcron.sdk`, `xcron.runtime`, `xcron.shared`,
   `xcron.domain`, `xcron.configuration`.
2. Keep `xcron_libs`, `xcron_cli`, and `xcron_resources` as deprecating
   re-export shims for one release, with a test asserting no first-party code
   imports them.
3. Update `[project.scripts]`, documentation, and skills.

Verification: full suite, installed-wheel smoke under both import roots, and a
grep proving no first-party module uses the old roots.

## Phase 9 — plane map, parity matrix, and documentation

1. Fill [05-plane-map.md](05-plane-map.md) against the implemented code and
   move its stable content into `docs/dev/architecture.md`.
2. Add the channel parity matrix to `docs/dev/architecture.md`.
3. Rewrite the stale "Repo Layout" and "Layering Contract" sections of
   `AGENTS.md` to match the implemented architecture. This is the file agents
   read first; leaving it stale silently re-teaches the old layout.
4. Add the degraded-behaviour drills named in the plane map.
5. Confirm `docs/dev/go-rewrite-contract.md` still describes the shipped
   contract.

Verification:

```sh
./scripts/verify-core.sh
markdownlint --disable MD013 -- docs/dev/architecture.md AGENTS.md \
  docs/plans/2026-08-03-module-first-isolation/*.md
```

## Dependency graph

```text
phase 0: decisions and baseline
  └─ phase 1: public surfaces and module cards
       ├─ phase 2: CLI owns projections
       ├─ phase 3: reconciliation absorbs adapters
       │    └─ phase 4: manifest, shared, metrics owner
       │         └─ phase 5: workspace and configuration
       │              └─ phase 6: packaging, typing, shim removal
       │                   └─ phase 7: declared enforcement
       │                        └─ phase 8: public naming (conditional)
       │                             └─ phase 9: plane map and docs
       └─ (phase 2 may run in parallel with 3)
```

Phases 2 and 3 touch disjoint file sets and may be executed in either order or
in parallel branches. Everything from Phase 4 onward is strictly sequential.

## Stop conditions

Stop and re-plan rather than continue if any of these occur:

- a move reveals a genuinely shared invariant that two modules must update
  atomically — assign it one owner before proceeding;
- the declared cross-module dependency list needs a new edge that is not in
  [02-target-architecture.md](02-target-architecture.md);
- an architecture contract needs an exception without an expiry condition;
- CLI output, exit codes, or help text change in any phase;
- the deterministic core suite is red at a phase boundary.
