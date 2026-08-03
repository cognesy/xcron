# Guardrails and acceptance

## Principle

Directory names are documentation; import checks are enforcement. Every
boundary this plan creates must be provable by a command in the default
quality gate, and every check must itself be proven to fail on a planted
violation.

## Enforcement layer 1 — declared import contracts

Import Linter, wired into `scripts/verify-core.sh`.

```toml
[tool.importlinter]
root_packages = ["xcron_libs", "xcron_cli"]

[[tool.importlinter.contracts]]
name = "capability modules are independent"
type = "independence"
modules = [
    "xcron_libs.capabilities.workspace",
    "xcron_libs.capabilities.manifest",
    "xcron_libs.capabilities.jobs",
    "xcron_libs.capabilities.reconciliation",
    "xcron_libs.capabilities.operations",
    "xcron_libs.capabilities.agent_hooks",
]

[[tool.importlinter.contracts]]
name = "declared cross-module contract dependencies only"
type = "forbidden"
source_modules = ["xcron_libs.capabilities"]
forbidden_modules = ["xcron_cli", "typer", "rich", "toon"]

[[tool.importlinter.contracts]]
name = "layers"
type = "layers"
layers = [
    "xcron_cli",
    "xcron_libs.sdk",
    "xcron_libs.runtime",
    "xcron_libs.capabilities",
    "xcron_libs.shared | xcron_libs.domain",
]

[[tool.importlinter.contracts]]
name = "shared and domain are leaves"
type = "forbidden"
source_modules = ["xcron_libs.shared", "xcron_libs.domain"]
forbidden_modules = [
    "xcron_libs.capabilities",
    "xcron_libs.sdk",
    "xcron_libs.runtime",
    "xcron_libs.configuration",
    "xcron_cli",
]

[[tool.importlinter.contracts]]
name = "only the configuration adapter reads settings sources"
type = "forbidden"
source_modules = ["xcron_libs.capabilities", "xcron_libs.sdk", "xcron_cli"]
forbidden_modules = ["xcfg"]
```

The `independence` contract is the important one: it protects a *new* module by
default, which the current hand-written test cannot do.

The declared cross-module edges from
[02-target-architecture.md](02-target-architecture.md) — `manifest -> workspace`,
`jobs -> manifest`, `reconciliation -> {workspace, manifest}`,
`operations -> workspace` — are expressed as explicit allowances against the
independence contract, each with a one-line justification. Any additional edge
requires a recorded decision in `docs/dev/architecture.md`, not a silent
allowlist entry.

## Enforcement layer 2 — public-surface scanner

An import graph cannot express "only `api` and `contracts` are importable from
outside". Keep the existing AST scanner, generalized from `agent_hooks` to
every module, and keep its coverage of all four import forms:

```python
import xcron_libs.capabilities.manifest._editor
from xcron_libs.capabilities.manifest import _editor
from xcron_libs.capabilities.manifest._editor import edit
from xcron_libs.capabilities.manifest import _editor as editor
```

Each form must have a planted forbidden example per module, asserting that the
scanner reports it. A scanner that only reads the current clean tree proves
nothing.

## Enforcement layer 3 — state ownership

One test per owned state family, asserting that no module outside the owner
writes it:

| State family | Sole writer | Test |
| --- | --- | --- |
| `<project>/resources/schedules/*.yaml` | `manifest` | no other module opens the manifest path for write |
| `<project>/.xcron/marker.toml` | `workspace` | marker written only by the initializer |
| `~/.xcron/<project>/project-state.json` | `reconciliation` | planted write from `operations` fails the test |
| generated wrappers, plists, crontab block | `reconciliation` adapters | artifact paths derive only from workspace paths |
| `~/.xcron/metrics/metrics.json` | `operations` | `MetricsService` is unreachable from `reconciliation` |
| `.codex/*`, `.claude/settings.json`, session history | `agent_hooks` | existing test, retained |

## Enforcement layer 4 — packaging

- `py.typed` present in every distributed package, asserted from the built
  wheel, not the source tree.
- The `packages` list equals setuptools' discovered set (or discovery is
  automatic and the assertion is dropped).
- A clean-environment install imports `xcron_libs` without importing `typer`,
  `rich`, or any CLI module — the existing fresh-process test, run against the
  installed artifact.
- Installing without the `cli` extra still imports the SDK; the console script
  is documented as requiring the extra.

## Test lanes

| Lane | Path | Rule |
| --- | --- | --- |
| Module | `tests/modules/<module>/` | Imports the module's public API plus fakes. Importing a sibling implementation fails the lane. |
| Channel | `tests/channels/{cli,sdk}/` | CLI wiring, output projections, exit codes; SDK lifecycle and grouped APIs. |
| Contracts | `tests/contracts/` | Durable-format compatibility: manifest, `project-state.json`, marker. Old-reader/new-writer cases where compatibility is promised. |
| Parity | `tests/parity/` | Spy-injected proof that CLI and SDK reach the same use case with equivalent inputs. |
| Architecture | `tests/architecture/` | Import contracts, public-surface scanner, state ownership, packaging. |
| Integration | `tests/integration/` | Explicit-only host launchd and Docker cron harnesses. Unchanged; never in the default gate. |

Each module lane must be runnable alone:

```sh
uv run pytest tests/modules/reconciliation
```

## Definition of done

Per `MODULE-ISOLATION.md`. Every applicable answer must be yes for each of
`workspace`, `manifest`, `jobs`, `reconciliation`, `operations`, and
`agent_hooks`:

- [ ] The module hides one named independently changing decision.
- [ ] Its complete vertical slice — rules, actions, ports, adapters,
      resources, tests — has one physical owner.
- [ ] Incoming imports use only `api` and `contracts`.
- [ ] It imports no sibling implementation.
- [ ] Cross-module workflows live in `libs/runtime/` or the SDK, not inside a
      sibling.
- [ ] State, resources, and schemas have exactly one writer.
- [ ] `libs/shared/` and `libs/domain/` are leaves, not dumping grounds.
- [ ] The dependency graph is acyclic and declared in Import Linter.
- [ ] Planted negative tests prove each check detects forbidden imports.
- [ ] The module has a focused test lane importing no sibling implementation.
- [ ] The installed wheel contains and imports the module correctly.
- [ ] The claimed isolation level — 1 — matches the evidence.

Repository-level:

- [ ] `libs/services/`, `libs/infra/`, and `libs/actions/` no longer exist.
- [ ] No module under `libs/` imports `xcron_cli`.
- [ ] The workspace marker, root precedence, and configuration precedence are
      tested at every adjacent edge.
- [ ] `py.typed` ships; CLI dependencies are an extra.
- [ ] The AXI CLI contract is byte-compatible with the pre-refactor capture.
- [ ] `AGENTS.md`, `docs/dev/architecture.md`, and
      `docs/dev/go-rewrite-contract.md` describe the implemented shape.
- [ ] The plane map records state ownership, cross-plane contracts, and
      degraded behaviour, with a drill for each failure row.

If any box is unchecked, describe the result honestly as a capability grouping
or migration-in-progress — not an isolated module. That honesty is what makes
the current `docs/dev/architecture.md` trustworthy today, and it must survive
this refactor.

## Regression guards specific to xcron

These protect the properties the previous refactor earned:

1. Capture `xcron --help`, every group's `--help`, and one golden invocation
   per command in TOON and JSON *before* Phase 2. Diff after every phase.
2. Assert the plan/status/apply sources of truth are unchanged: `plan` reads
   derived state, `status` queries the scheduler, `apply` baselines on
   `status`.
3. Assert the scheduler registry still rejects unknown and duplicate backend
   identities.
4. Assert `Xcron.close()` remains idempotent and use-after-close raises
   `ClientClosedError`.
5. Run the explicit host integration harnesses once, manually, before
   declaring Phase 3 complete — the adapters move in that phase, and the
   deterministic suite does not touch a real scheduler.
