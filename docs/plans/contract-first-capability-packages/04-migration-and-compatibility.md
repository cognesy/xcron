# Migration and compatibility plan

<!-- markdownlint-disable MD013 -->

## Migration principle

Make a package boundary real before deleting its old internal owner. Every
stage is installed-artifact verified. A source-tree import passing while a
wheel lacks an entry point, asset, dependency, or namespace path is a failed
stage, not a follow-up.

## Phase 0: Freeze current external behavior

Before moving production code, add a black-box compatibility corpus covering:

- every supported SDK and CLI parity flow, including explicit request options;
- output JSON/TOON shape and exit codes for representative success, usage, and
  runtime failures;
- manifest YAML validation/editing and stable job hashes;
- marker, `project-state.json`, wrapper text/ownership markers, launchd labels,
  and managed crontab block literals;
- degraded drills proving the deployed data plane works without xcron and that
  metrics failure cannot stop reconciliation; and
- aggregate/lean installed-wheel import and missing-capability behavior.

The existing test suite is the source. The task extracts stable fixtures and
adds only missing black-box assertions; it must not weaken existing architecture
or durable-format checks to make movement easier.

## Phase 1: Establish the workspace and kernel seam

1. Convert root packaging to a `uv` workspace with package members and a shared
   lock. Keep current root commands as temporary delegating aliases.
2. Add `xcron-kernel`, `xcron-contracts`, and `xcron-testing`; prove that kernel
   imports no product code and that contracts import no provider mechanism.
3. Implement entry-point discovery, selection, descriptor validation, typed
   host construction, snapshot freeze, duplicate/cycle/incompatible diagnostics,
   and a no-op outcome sink.
4. Add architecture scans over all `packages/*/src/xcron` and
   `capabilities/*/src/xcron` roots. Retire root-only Import Linter assumptions
   that cannot observe namespace-distributed code; replace them with
   layout-agnostic AST/import tests.
5. Strengthen the existing `ops/` catalogue before package extraction: repair
   safe discovery routes, make operation manifests the only aggregate-lane
   source, and add the package-operation micropackage contract. Do not turn
   root aliases into duplicate implementations.

The old runtime remains in place during this phase. Nothing changes in native
scheduler behavior.

## Phase 2: Extract prerequisites and first provider

Extract in this exact dependency order:

1. `workspace:local` — marker and paths;
2. `settings:xcfg` — all configuration layer machinery and packaged defaults;
3. `observability:structlog` — logging resource/configuration only;
4. `manifest:yaml` — models use contracts, provider owns schema resource and
   editor/load/hash mechanics.

At each step the new provider is entry-point discoverable, self-contained,
contract-conformant, and used by one optional host-based adapter test. The old
module may delegate to the provider temporarily, but no new work lands in the
old module.

## Phase 3: Extract the scheduler compatibility unit

Move reconciliation into `scheduler:native` as one provider:

- backend registry and selection;
- launchd/cron adapters and subprocess port;
- deployment plan/status/inspect algorithms;
- wrapper renderer, overlap behavior, state store, and all native assets.

The new provider obtains `WorkspacePort` and `ManifestPort` from its host. It
reports only to `OutcomeSink`, which is optional and non-throwing. Run both
fake-backend tests and the explicit host scheduler harnesses before closing the
phase. Compare old and aggregate wheel output against the Phase 0 corpus.

## Phase 4: Extract management providers

1. Move job mutation into `jobs:manifest`, preserving typed request models and
   its no-scheduler-write rule.
2. Split log access into `logs:local` and metrics into `metrics:local`; wire the
   latter as the aggregate `OutcomeSink` without making it a scheduler
   dependency.
3. Move Codex/Claude integration into `agent-hooks:local`, including hook-file
   fixtures and packaged skill/help assets it owns.

The SDK compatibility `operations` group composes logs and metrics ports. No
provider gains a generic service locator or reaches another provider’s private
file subtree.

## Phase 5: Replace direct runtime composition and channels

1. Build `xcron-sdk` around `CapabilityHost`, preserving `Xcron` lifecycle and
   current group names. Remove every implementation import from client/runtime
   composition.
2. Move the CLI channel and help resources into `xcron-cli`. Attach commands
   from validated contributions and retain AXI contracts, field validation,
   renderer boundary, stdout/stderr behavior, and exit codes.
3. Add the `xcron` aggregate/meta distribution with the default provider set;
   confirm `pip install xcron` gives the SDK while `pip install 'xcron[cli]'`
   gives the unchanged command.
4. Delete the legacy root `src/xcron/capabilities`, `runtime`, `configuration`,
   `shared`, SDK, and channel implementation only after no compatibility test or
   architecture scan refers to them.
5. Register every shipped distribution's local Just entry point through the
   package-operation capability. The global catalogue delegates; package-local
   recipes remain the only canonical build/test implementation.

## Phase 6: Remove the bridge and prove substitution

The bridge ends only when:

- a clean aggregate install passes the entire compatibility corpus;
- a lean install can construct `Xcron`, list selected capabilities, and returns
  structured unavailable errors for absent groups;
- a test-only alternate provider can be selected for one port without changing
  SDK/CLI/kernal code;
- each wheel is independently built, tested, and inspected for only its declared
  source/resources/dependency closure; and
- no production code contains a direct import of a concrete provider outside
  its own capability distribution.

Only then delete all compatibility delegation and update `SPEC.md`, user docs,
architecture docs, Go rewrite contract, help pages, and operations catalogue to
describe capability packages as the implementation model.

## Compatibility decision table

| Artifact/surface | Migration rule | Evidence |
| --- | --- | --- |
| `xcron` command and output | Preserve path, flags, response envelopes, exit codes, and help behavior. | CLI parity/golden tests from aggregate wheel. |
| `Xcron` SDK | Preserve grouped methods and typed inputs/outputs; implementation imports disappear. | SDK compatibility and lean unavailable tests. |
| YAML/marker/native artifact formats | Byte/field compatible reader and writer behavior before any intentional version change. | Durable fixtures, installed integration harness. |
| Existing `xcron.capabilities.*` private paths | Delete on cutover; do not offer a permanent shim. | Architecture negative tests. |
| Default dependencies | SDK does not acquire CLI dependencies; each provider declares its own. | `pip inspect`/wheel closure tests. |
| Runtime selection | Explicit `CapabilitySelection` only; no user-controlled Python target. | malformed/duplicate/selection security tests. |

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Multi-wheel namespace mistakes hide in editable source runs. | Clean-environment aggregate, lean, and individual-wheel probes are mandatory per extraction. |
| A too-generic port recreates a service locator. | One port per hidden decision; descriptor/contract review rejects untyped `get(name)` and `dict[str, Any]` collaboration. |
| CLI contributions leak Typer into domain providers. | Separate channel adapter boundary and architecture test forbidding `xcron.channels`, Typer, Rich, TOON in provider core. |
| Scheduler extraction breaks deployed jobs. | Keep native scheduler as one compatibility provider; run degraded and real integration lanes before cutover. |
| Metrics becomes required. | Kernel no-op sink and tests where metrics provider is missing/broken. |
| Scope grows into a Cordis rewrite. | Use static entry-point composition only; reject hot reload/effect lifecycle unless a separately evidenced requirement appears. |
