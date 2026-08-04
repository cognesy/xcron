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

### Phase 2 result (2026-08-04)

Done, and it was the pure move the plan predicted: 1,299 lines changed path,
not content. `cli_contracts` → `apps/cli/contracts.py`, `cli_responses` →
`apps/cli/responses.py`, `cli_mappers` → `apps/cli/mappers.py`, and
`axi_presenter`, `toon_renderer`, `tmux_renderer`, `help_renderer` →
`apps/cli/presenters/`. `resources/help/` → `apps/cli/resources/help/`, so the
15 authored help pages are now packaged data of the channel that renders them
rather than of a shared `xcron_resources` package.

`pyproject.toml` gained `xcron_cli.presenters`, `xcron_cli.resources`,
`xcron_cli.resources.help`, and `xcron_cli.resources.help.jobs`, and the
help package-data keys moved off `xcron_resources`. `xcron_resources` now
carries only `logging` and `schemas`, which are genuinely library-owned.

The new contract is `test_no_library_module_imports_the_cli_channel`: every
`.py` file under `libs/` is parsed and may not import `xcron_cli` in any form.
`test_cli_projection_modules_live_in_the_cli_channel` pins the move itself so
the cluster cannot drift back. Three older tests listed the individual
projection modules as forbidden prefixes; those entries are now subsumed by the
`xcron_cli` prefix and were removed rather than rewritten.

- `./scripts/verify-core.sh`: 191 passed (was 189 — 2 new contracts).
- CLI golden: 36/36 files byte-identical to the Phase 0 baseline.
- Wheel check: built, installed into a clean venv, and all 15 help pages load
  from `xcron_cli.resources.help`. The installed `--help` differs from the
  baseline only in Typer's metavar rendering (`TEXT` vs `<str>`), because the
  clean venv resolved typer 0.27.1 against the project's pinned 0.23.2. That
  difference is not caused by this phase.

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

### Phase 3 result (2026-08-04)

Done, with one deliberate departure from step 2. `libs/services/` fell from
3,855 lines to 1,210; `reconciliation` grew to 2,944 and now owns everything
its decision depends on: `adapters/{cron,launchd,process}.py`, `domain.py`
(the former `libs/domain/diffing.py`), `ports.py`, `registry.py`,
`state_store.py`, and `wrapper.py`. `libs/services/backends/` is gone.

**Departure — `state_store` split rather than moved.** The plan said move it
whole, but `libs/services/logging_paths.py` and `operations` both need
`resolve_state_root`/`resolve_project_state_dir`, and moving those into
reconciliation would have forced `operations` to import a sibling's internals.
So *where* derived state lives stayed shared, in the new
`libs/services/state_paths.py` (39 lines), and *what goes in it* moved:
`project-state.json` load/save/delete is now reconciliation's. This preserves
the intent of the step — one owner per file — while keeping the declared edge
set intact. `default_backend_for_current_platform` moved to `registry.py`,
where backend selection already lives; all three call sites were reconciliation.

`contracts.py` split as planned: `ports.py` holds `DeploymentPlan`,
`SchedulerRuntimeOptions`, `SchedulerInspection`, and the `SchedulerBackend`
Protocol; `contracts.py` holds the use-case results and re-exports the port
values that appear inside them, so a caller still needs one import. The two
adapters now import `ports`, never `contracts` — a new test enforces exactly
that, since an adapter seeing a use-case result is the failure mode this split
exists to prevent.

`libs/domain/` no longer imports a capability. It had been re-exporting the
diffing names, which pointed the dependency arrow backwards the moment diffing
moved; a new test pins `libs/domain` as a leaf.

Tests moved to `tests/modules/reconciliation/` (8 files), and the scanner now
treats `tests/modules/<module>/` as part of the module, so a module-owned lane
may exercise internals while nothing else may. The new
`test_fake_backend_lane.py` drives plan, status, apply, prune, and the typed
unknown-backend error through an in-memory `FakeScheduler`, importing only
`api`, `contracts`, and `ports`.

- `./scripts/verify-core.sh`: 200 passed (was 191 — 6 fake-backend cases plus
  3 new structural contracts).
- CLI golden: 36/36 files byte-identical to the Phase 0 baseline.

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

### Phase 4 result (2026-08-04)

Done, with one deliberate departure from step 5 and its consequence for step 6.
`libs/services/` and `libs/infra/` no longer exist; every one of their files now
belongs to exactly one module or to the shared leaf. A new test asserts both
directories are absent and that nothing under `libs/` imports either package,
so the ownerless drawer cannot come back.

**Departure — `workspace` was created here, not in Phase 5.** Step 6 requires
deleting `libs/services/`, but three of its files (`logging_paths`,
`state_paths`, and the home/project-root half of `config_loader`) are destined
for `workspace/`, which step 5 defers. Parking them in `libs/shared/` would have
put persistence-adjacent path logic inside a strict leaf and moved it again one
phase later. So Phase 4 creates `capabilities/workspace/` as a Level 1 module
with `resolver.py` (xcron home, project root, schedules directory) and
`paths.py` (state root, per-job runtime paths), plus its `api`/`contracts` pair
and a module-owned lane. Phase 5 still owns everything it was scoped for —
`marker.toml`, the four-step resolution precedence, XCFG, and folding `home` in
— it now grows an existing module instead of creating one. `home` was left
untouched, exactly as step 5 permits.

`ProjectResolutionError` became `WorkspaceResolutionError` in the workspace
error family rather than staying a `ManifestLoadError` subclass; two modules
now raise two typed families and `validate_project` catches both. The message
text is unchanged, so the CLI surface did not move.

Steps 1-4 landed as written. `manifest/` holds `_loader.py`, `_schema.py`,
`_editor.py`, `_hashes.py` and its own `resources/schemas/`; `libs/shared/`
holds `observability.py`, `logging_config.py` and `resources/logging/`. Both
resource packages moved inside the module that reads them, so the
`xcron_resources` distribution package is gone and `pyproject.toml` no longer
maps a third top-level package.

The metrics split is closed. `MetricsService` moved to
`operations/metrics_store.py`, `operations.api.record_outcome` is the single
public write, and reconciliation names only the `OutcomeRecorder` port on
`ports.py`. `libs/runtime/composition.py` supplies `MetricsOutcomeRecorder`,
the one place the two capabilities meet. The default is `NullOutcomeRecorder`:
a bare `status_project()` call now records nothing, while the same call through
the CLI or SDK records exactly what it did before — both verified by hand
against a real `metrics.json`. Two tests pin it: reconciliation may not name
`MetricsService` or import operations, and every file naming `MetricsService`
must live under `operations/`.

Line counts: `libs/services/` 1,210 -> 0. `manifest` 794, `workspace` 234,
`shared` 299, `operations` 388, `reconciliation` 2,980.

- `./scripts/verify-core.sh`: 231 passed (was 200 — 21 new module-lane cases
  across `manifest`, `workspace`, and `operations`, plus 10 new structural
  contracts).
- CLI golden: 36/36 files byte-identical to the Phase 0 baseline.
- Planted negatives: four violations (reconciliation importing operations,
  reconciliation importing a manifest internal, shared importing a capability,
  reconciliation naming `MetricsService`) each failed the intended test.
- Clean-venv wheel: schema and logging resources load from their new packages;
  `xcron_libs.services`, `xcron_libs.infra`, and `xcron_resources` are absent
  from the installed distribution. A stale `build/` directory was masking this
  and was removed — worth knowing before trusting any future wheel check.
- The declared-edge table in `tests/test_reconciliation_architecture.py` is now
  the target graph from `02-target-architecture.md`, not a placeholder.

`AGENTS.md`, `README.md`, and `docs/dev/go-rewrite-contract.md` had layout and
layering blocks that Phase 4 falsified. They were corrected factually here
rather than left wrong until the Phase 9 rewrite.

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

### Phase 5 result (2026-08-04)

Done. All five steps landed, with four judgement calls recorded below and one
user-visible consequence that is not a refactor at all.

**The minimum supported Python is now 3.11.** This follows from decision 2
("Adopt XCFG") rather than from anything in the plan: xcfg requires ≥3.10, and
3.11 additionally gives the marker a stdlib `tomllib` instead of a dependency.
`requires-python` moved `>=3.9` → `>=3.11`, `.python-version` was added, and
`tests/integration/docker/cron.Dockerfile` moved to `python:3.11-slim-bookworm`.
Two consequences arrived with the newer floor: click 8.2 removed
`CliRunner(mix_stderr=...)`, and click 8.2 sends *argument-parser* usage errors
to stderr instead of stdout. The second is a real behaviour change and is
reported as one — xcron's own structured usage errors still go to stdout, exit
codes are unchanged, and the 36-file golden CLI surface is byte-identical.
`tests/test_cli_parser.py` now asserts the new split (stdout clean, prose on
stderr) instead of the old one.

**xcfg is pinned by PEP 508 direct reference, not `[tool.uv.sources]`.** A
clean-venv wheel install failed because sources are checkout-local and do not
travel in wheel metadata, while xcfg is on no index. `dependencies` now carries
`xcfg @ git+https://github.com/cognesy/xcfg@v0.5.0` and `[tool.uv.sources]` is
gone. The tag is pinned because xcfg's layer order *is* xcron's observable
configuration contract.

**Settings moved to `configuration`; identity stayed with `workspace`.** Step 3
calls `loader.py` "the only XCFG and `os.environ` reader", which cannot be
literally true: `XCRON_HOME` and `XCRON_PROJECT` select *which* config files are
read, so they cannot themselves come from one. The invariant that was actually
closed is narrower and enforceable — five named files may name `os.environ`,
pinned by set equality, and only `libs/runtime/composition.py` may import
`configuration.api`. `log_level`/`log_format` were dropped from `Settings` for
the same reason in the other direction: logging bootstraps before a runtime
exists, and making the `shared` leaf import `configuration` would invert the
dependency.

**`create_unscoped` / `open_unscoped` were added.** Step 4's "resolve workspace
and settings once in `XcronRuntime`" would have made `xcron init` resolve a
workspace before creating one — failing on precisely the machine that needs the
command. `init`, `metrics show`, and `metrics reset` now open unscoped clients;
everything else resolves normally.

**Durable-format tests live in the owner's lane.** Step 5's contract tests were
first written under `tests/contracts/`, which required `load_project_state` on
reconciliation's public surface. Widening a module's surface for a test is the
opposite of what the surface is for, so they moved to
`tests/modules/reconciliation/test_durable_state_format.py` and pin the literal
key sets rather than round-tripping through the writer.

`capabilities/home` is gone, folded into `workspace/initializer.py`;
`libs/actions/init_home.py` is now an alias shim. The initializer never
overwrites or deletes: a legacy `resources/schedules` is adopted in place and
reported as `migrated_paths`, and anything it cannot claim is reported as a
conflict. `apps/cli/common.py` lost `env_path`, `env_string`, `env_flag`,
`resolve_project_path`, and its `import os` — the CLI no longer reads the
environment at all.

A latent bug in `libs/shared/observability.py` surfaced under the new tests and
was fixed: `configure_logging` compared `id(sys.stderr)`, and CPython reuses
addresses after GC, so a replaced stream could be mistaken for the configured
one. It now holds the stream object, passes `force=True` to `basicConfig`, and
binds `PrintLoggerFactory(file=stream)`.

- `./scripts/verify-core.sh`: 282 passed (was 231 — 61 new module-lane cases
  across `workspace` marker/resolution/initializer, `configuration` layering,
  and reconciliation's durable format, plus 5 new structural contracts).
- CLI golden: 36/36 files byte-identical to the Phase 0 baseline, fifth
  consecutive phase.
- Planted negatives: five violations (an undeclared `os.environ` reader, a
  second xcfg importer, a capability importing `configuration`, a settings load
  outside the composition root, a resurrected `home` module) each failed the
  intended test.
- Hand checks: packaged-default → workspace → env precedence; all five legacy
  false spellings (`0`, `false`, `False`, `no`, `NO`) still turning a flag off
  while `yes` turns it on; walking-up resolution from `ws/src/deep`; a
  byte-exact `marker.toml` from `xcron init`; the missing-marker warning on
  stderr with stdout still parseable JSON.
- Clean-venv wheel: installs from the direct reference, ships
  `config.default.yaml`, and contains no `xcron_libs.capabilities.home`.

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

### Phase 6 result (2026-08-04)

Done, all five steps, with one deviation on step 1 and one on step 3.

**Step 1 — two markers, not twenty.** PEP 561 puts the marker in the top-level
package, where it covers everything beneath it, so `libs/py.typed` and
`apps/cli/py.typed` are the whole of it. Writing one into each of the twenty
sub-packages would be noise that says nothing extra, and no type checker looks
for them there. Both are declared in `package-data` and both are asserted
present *in the installed wheel*, which is the only place the claim can be
false.

**Step 2 — the extra, and the group that keeps it honest.** `typer`, `rich`,
and `python-toon` moved to a `cli` extra; the mandatory set is `PyYAML`,
`jsonschema`, `pydantic`, `structlog`, and `xcfg`. The split is only meaningful
because no file under `libs/` may import a renderer, which the architecture
tests already enforced before this phase made it a packaging fact. The test
suite exercises the CLI channel, so a `[dependency-groups] dev` entry asks for
`xcron[cli]`; uv installs that group by default, so `uv run pytest` is
unchanged. (`[tool.uv] default-extras` would have been the direct expression of
this, but uv 0.9.22 does not accept the key.)

**Step 3 — an equality test, not discovery.** Two package roots map into one
distribution (`apps/cli` → `xcron_cli`, `libs` → `xcron_libs`), which
setuptools' `find` directives express badly. Keeping the explicit list and
asserting it equals the discovered set gives the same guarantee and a better
failure message: the test names the package that was added and never declared.
`xcron_libs.infra` was already gone.

**Steps 4 and 5.** All 15 test modules now import the owning module's `api`;
`libs/actions/` is deleted and `test_the_actions_facade_is_gone` asserts both
that the directory is absent and that nothing under `libs/` imports the name.
`scripts/verify-wheel.sh` builds once and installs twice: a library-only
environment where importing the SDK must not reach a renderer and the renderers
must not even be installed, then an `xcron[cli]` environment where the console
script must run. It also re-checks that the four deleted packages
(`actions`, `services`, `infra`, `xcron_resources`) do not ship, which is
exactly the failure a stale `build/` directory produced in Phase 4.

The new `tests/test_packaging.py` reads `pyproject.toml` as data. It is a
separate lane from the architecture tests on purpose: those describe how the
code may depend on itself, these describe what leaves the repository.

- `./scripts/verify-core.sh`: 288 passed (was 282 — six packaging contracts).
- `./scripts/verify-wheel.sh`: both environments pass.
- CLI golden: 36/36 files byte-identical to the Phase 0 baseline, sixth
  consecutive phase.
- Planted negatives: six (an undeclared package, Rich back in the mandatory
  set, a missing `py.typed`, a resource pattern matching nothing, xcfg reverted
  to a bare specifier, a resurrected `libs/actions`) each failed the intended
  test.

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
