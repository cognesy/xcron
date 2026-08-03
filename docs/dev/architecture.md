# xcron Architecture

This prototype keeps the public product contract in `SPEC.md` while organizing
application work by capability. The implementation is deliberately a small
brownfield step: it retains low-level services where they are useful, but makes
the high-level ownership and scheduler boundary explicit.

Top-level layout:

- `apps/cli/` contains the thin Typer/output channel;
- `libs/capabilities/` contains capability-owned use cases:
  `reconciliation`, `jobs`, `operations`, `agent_hooks`, and `home`;
- `libs/domain/` contains canonical models, normalization, identities, and
  desired-vs-deployed diffing;
- `libs/services/` contains reusable low-level mechanisms and native scheduler
  adapters;
- `libs/runtime/` composes the deterministic first-party provider set;
- `libs/sdk/` exposes the typed `Xcron` client for embedders and CLI use; and
- `libs/actions/` is a compatibility import facade for the previous action
  paths.

The dependency direction is:

```text
apps/cli -> xcron_libs.Xcron -> capability actions -> domain + ports
runtime  -> explicit scheduler registry -> native scheduler adapters
adapters -> reconciliation contracts + domain
```

Rules:

- CLI code parses Typer input, opens `Xcron`, maps typed results/errors through
  `Output`, and chooses exit codes. It does not import action implementations,
  native backend functions, or output encoders below its channel boundary.
- Capabilities own use-case policy and return typed results. They do not import
  `xcron_cli`, Typer, Rich, TOON, JSON, or tmux renderers.
- `reconciliation` owns the typed scheduler port, backend-neutral
  `DeploymentPlan` and `SchedulerInspection` contracts, and registry selection.
  Backends must never import an action result or the SDK.
- `runtime` composes only. It owns immutable resolved invocation options and
  the scheduler registry, owns no product policy, and provides the same
  first-party provider set to all channels.
- `Xcron` is a synchronous context-managed SDK. It owns no native scheduler
  connection today, has idempotent `close()`, rejects use after close, and does
  not import CLI/output code. See [sdk.md](sdk.md) for its public surface and
  lifecycle contract.
- `libs/actions` preserves compatibility for current callers while code moves;
  it must not grow new business logic.
- `libs/services/__init__.py` stays non-aggregating. Callers import explicit
  leaf modules so capability/SDK imports cannot transitively load CLI response
  models or rendering dependencies.
- CLI projection leaf modules (`cli_contracts`, `cli_mappers`,
  `cli_responses`, `toon_renderer`, and `tmux_renderer`) remain physically in
  `libs/services/` during the brownfield migration. They are owned by the CLI
  channel through import direction: the projection leaf modules may depend on
  one another, but production entry into that cluster comes from `apps/cli/`.
  Capability, domain, runtime, SDK, and backend code must not import them.
  Physical location alone does not make them reusable product services.

## Verified Level 1 module

`xcron_libs.capabilities.agent_hooks` is the first capability with executable
Level 1 isolation evidence. It owns the repository-local Codex and Claude hook
lifecycle and file-format decision, including these four state paths:

- `.codex/config.toml`
- `.codex/hooks.json`
- `.claude/settings.json`
- `session-history.jsonl`

Its only cross-module entrypoints are `agent_hooks.api` and
`agent_hooks.contracts`. The SDK `HooksAPI` is the sole product/channel adapter;
the CLI reaches hooks through that SDK. The implementation is standard-library
only and imports no sibling capability, SDK, CLI, presentation, or global
service implementation. AST checks cover direct, submodule, root-`from`, and
aliased forbidden imports, with planted negative examples. A focused module
test lane covers payload preservation, idempotency, typed failures, and exact
state ownership.

This is a Level 1 code-module result, not a new distribution, dependency set,
process boundary, plugin system, or service deployment. `reconciliation`,
`jobs`, `operations`, and `home` remain capability groupings or migration-in-
progress; this result does not claim they are isolated modules.

Current model decisions:

- schedule manifests live under `resources/schedules/`
- the manifest is per-project only
- every manifest must define `project.id`
- backend-neutral job identity is derived as `<project.id>.<job.id>`
- `schedule.every` remains part of the public model, constrained to a simple
  duration string for v1

The Python prototype should preserve these boundaries so the later Go rewrite
can keep the same external contract and internal separation of concerns.

## Migration compatibility

`xcron_libs.actions` remains an import-compatible facade for the prior action
module paths. The former `xcron_libs.services` package-root aggregate is not
part of that promise: its re-exports were removed deliberately. Callers must
replace imports such as `from xcron_libs.services import get_logger` with the
owning leaf-module import, such as
`from xcron_libs.services.observability import get_logger`.

This is an intentional internal compatibility break. It prevents a low-level
package import from eagerly loading unrelated CLI projections and makes actual
module ownership visible at each call site.

## Distribution shape

`xcron` deliberately ships as one root Python distribution. The root
`pyproject.toml` maps `apps/cli` to `xcron_cli`, `libs` to `xcron_libs`, and
`resources` to `xcron_resources`; its `xcron` console script targets
`xcron_cli.typer_app:run`. `apps/cli` therefore does not have a second
`pyproject.toml`.

The CLI channel, native SDK, capability implementation, and packaged runtime
resources share one version, dependency graph, and release lifecycle. Splitting
the CLI into a separate distribution would introduce a cross-distribution
dependency on the SDK/capabilities and a second release/install boundary
without providing independent ownership, dependencies, or release cadence.
Reconsider the split only if one of those operational boundaries becomes real.

Older xpack versions warned about the root entry point and missing app-local
metadata. Those warnings are accepted when using such a version because the
single-distribution mapping is intentional, not accidental. Current xpack
recognizes both the scoped root entry point and `apps/cli` package mapping as
passing x-style structures: the live structure check reports six passes and no
warnings. `.xpack/config.toml` remains the installed-wheel verification
contract.

Implemented prototype components:

- validation, normalization, and stable hashing
- planner and per-project derived local state
- manifest editing service for job-level YAML updates
- wrapper rendering with default logs and overlap control
- `launchd` backend
- `cron` backend
- operator-facing `status` projection layered on top of planner diffing
- richer `inspect` results that expose normalized desired data plus
  backend-native detail
- nested `jobs` CLI group for manifest-side job management
- capability-owned reconciliation, manifest jobs, runtime operations, home,
  and agent-hook use cases, with legacy `libs/actions` import shims
- explicit `cron`/`launchd` scheduler registry and backend-neutral deployment
  and scheduler-inspection contracts
- embeddable `Xcron.open(...)` SDK with grouped schedules, jobs, operations,
  hooks, and home APIs
- CLI thin shells that call the SDK rather than embedding backend logic
- Typer-based command declaration and command grouping
- Pydantic response envelopes plus mapper helpers in CLI-owned projection leaf
  modules under `libs/services/`
- unified machine/human output rendering:
  - TOON for machine-facing output
  - Rich-backed help and human-facing presentation paths
- resource-backed runtime help under `resources/help/`
- repo-local Codex and Claude hook adapters plus install/status/repair flows

Verification model:

- deterministic core lane is `./scripts/verify-core.sh`
- today that core lane runs the safe default `uv run pytest`
- default core verification stays safe and does not mutate the host scheduler
- host-gated `launchd` integration exists for real macOS verification
- Docker/Colima-gated cron integration exists for real Linux cron verification

See `docs/dev/go-rewrite-contract.md` for the external behavior that should
remain stable in the later Go implementation.
