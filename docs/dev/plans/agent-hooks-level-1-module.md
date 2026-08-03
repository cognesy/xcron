# Agent Hooks Level 1 Module

## Goal

Establish one honest Level 1 code module in xcron by moving the complete
repository-local Codex and Claude hook vertical slice under
`xcron_libs.capabilities.agent_hooks`.

This is a deliberately small proof of the module-isolation pattern. It does not
claim that every directory under `libs/capabilities/` is already an isolated
module.

Parent Beads epic: `xcron-0wu`.

## Why Agent Hooks First

Agent hooks are the smallest capability that already has the properties needed
for a meaningful module:

- one independently changing decision: repository-local agent-hook lifecycle
  and file formats;
- explicit state: `.codex/config.toml`, `.codex/hooks.json`,
  `.claude/settings.json`, and `session-history.jsonl`;
- a small typed SDK surface;
- no scheduler, manifest, or domain-model dependency; and
- existing focused behavior tests.

Starting with reconciliation would not be minimal. Reconciliation currently
shares manifest interpretation, wrapper generation, derived project state,
domain models, and native scheduler infrastructure. Those ownership decisions
must be resolved before it can be called an isolated module.

`jobs`, `operations`, and `home` are also poor first candidates: jobs edits the
same manifest interpreted by reconciliation, operations is a grouping of logs
and metrics rather than one hidden decision, and home is too small to establish
a useful ownership boundary.

## Current Coupling

The implementation is split horizontally across:

```text
libs/capabilities/agent_hooks/actions.py
libs/services/hook_installer.py
libs/services/codex_hooks.py
libs/services/claude_hooks.py
libs/services/hook_paths.py
libs/sdk/hooks.py
apps/cli/typer_app.py
tests/modules/agent_hooks/test_api.py
tests/modules/agent_hooks/test_payloads.py
tests/test_cli_hooks.py
```

The SDK imports the capability aggregate, while the CLI also imports
`resolve_xcron_executable` directly from the service implementation. The hook
result types are owned by implementation files rather than a stable public
contract.

## Module Card

```yaml
module: agent_hooks
hidden_decision: repository-local Codex and Claude hook lifecycle and file formats
public_entrypoints:
  - xcron_libs.capabilities.agent_hooks.api
  - xcron_libs.capabilities.agent_hooks.contracts
owned_state:
  - .codex/config.toml
  - .codex/hooks.json
  - .claude/settings.json
  - session-history.jsonl
owned_resources: []
allowed_dependencies:
  - Python standard library
cross_module_flows:
  - caller: xcron_libs.sdk.hooks.HooksAPI
    contract: agent_hooks public API and typed results
failure_behavior: stable AgentHooksError subclasses; no undocumented partial mutation
isolation_level: 1
verification:
  - architecture import contract with planted forbidden cases
  - module-owned test lane
  - state-ownership tests
  - installed-wheel import smoke
```

## Target Layout

Keep the module flat because it is small. The ownership boundary matters more
than empty layer directories.

```text
libs/capabilities/agent_hooks/
  __init__.py       # empty; no eager aggregate imports
  api.py            # install, status, repair, session_end, resolve_executable
  contracts.py      # closed result/status models and stable errors
  _codex.py         # private Codex file adapter
  _claude.py        # private Claude file adapter
  _paths.py         # private state-path declarations

tests/modules/agent_hooks/
  test_api.py
  test_payloads.py
```

The following old horizontal implementation paths are removed after callers
have migrated:

```text
libs/capabilities/agent_hooks/actions.py
libs/services/hook_installer.py
libs/services/codex_hooks.py
libs/services/claude_hooks.py
libs/services/hook_paths.py
```

## Contract Decisions

- Outside callers import only `agent_hooks.api` or
  `agent_hooks.contracts`; the package initializer does not aggregate symbols.
- Public contracts use immutable typed values and represent paths as strings.
- `AgentHooksError` is the stable module error base.
- Missing executable discovery uses a typed `ExecutableNotFoundError`, not a
  leaked `RuntimeError` or `shutil` failure.
- The SDK may adapt a contract string back to `Path` if preserving its existing
  public return type avoids an unnecessary SDK break.
- The CLI reaches the module only through `Xcron.hooks`; it does not import
  module implementation or service paths.
- Install and repair remain idempotent and preserve the current file formats.

## Migration Stones

### 1. Define contracts and the public facade

Add the module card, typed contracts, stable errors, and `api.py`. Initially the
facade may delegate to the existing service implementation so the repository
stays green. Move result ownership into `contracts.py` and cover contract
construction and error identities.

### 2. Move the complete implementation

Relocate Codex, Claude, path, executable-resolution, install/status/repair, and
session-history behavior into private files under the module. Keep any old
service import paths only as explicit temporary forwarding shims during this
stone. There must be one implementation source, not copied logic.

### 3. Route callers and remove compatibility paths

Change `HooksAPI`, CLI hook commands, and tests to use only the public
API/contracts. Map module errors through the SDK/CLI structured error boundary.
Delete the capability action wrapper and all four service shims after searches
show no supported caller remains.

### 4. Add mechanical isolation evidence

Add architecture checks that:

- allow outside imports only from `.api` and `.contracts`;
- forbid module imports from sibling capabilities, SDK, CLI, presentation, and
  global service implementations;
- detect all relevant `import` and `from ... import ...` forms; and
- include planted forbidden examples proving that the scanner fails.

Move implementation tests into `tests/modules/agent_hooks/`. Add explicit
state-ownership assertions and a focused lane that imports no sibling
implementation.

### 5. Verify the installed module and document the achieved level

Run focused, full, and installed-artifact verification. Update architecture
documentation to call only `agent_hooks` a Level 1 module and continue to call
the remaining capability directories groupings or migration-in-progress.

## Verification

Focused module and channel checks:

```bash
uv run pytest tests/modules/agent_hooks tests/test_cli_hooks.py tests/test_sdk.py
```

Architecture and complete deterministic checks:

```bash
uv run pytest tests/test_reconciliation_architecture.py
./scripts/verify-core.sh
```

Installed artifact and source hygiene:

```bash
uv run --project ../xpack xpack verify "$(pwd)" --output json --full
markdownlint --disable MD013 -- docs/dev/architecture.md docs/dev/plans/agent-hooks-level-1-module.md
git diff --check
```

The installed-wheel check must import
`xcron_libs.capabilities.agent_hooks.api` outside the source checkout and run
the existing hook CLI smoke without relying on an editable install.

## Acceptance Criteria

- The module hides the named hook lifecycle/file-format decision.
- The complete implementation and state-path declarations have one physical
  owner under `libs/capabilities/agent_hooks/`.
- Outside imports use only the declared API/contracts.
- The module imports no sibling implementation.
- The CLI uses the SDK rather than the module or an old service directly.
- Stable typed errors cross the module boundary.
- Planted negative architecture tests prove forbidden imports are detected.
- The focused module lane, full suite, and installed-wheel smoke pass.
- The old action and service implementation paths are absent.
- Documentation claims Level 1 only for the evidence actually established.

## Execution evidence

The five migration stones are tracked under epic `xcron-0wu`. Stones 1 through 4
established the contracts, moved the implementation, migrated callers, removed
legacy paths, and added executable isolation checks. Verification completed with:

- 27 tests in the focused module/channel/architecture lane;
- 165 tests in `./scripts/verify-core.sh`;
- `xpack verify --output json --full` with zero blockers and zero warnings;
- an isolated wheel install importing both `agent_hooks.api` and
  `agent_hooks.contracts` outside the checkout; and
- Markdown lint plus `git diff --check` passing.

## Constraints and Non-Goals

- Keep one Python distribution and the existing release cadence.
- Do not introduce plugins, entry-point discovery, dependency injection
  frameworks, or process boundaries.
- Do not migrate reconciliation, jobs, operations, or home in this epic.
- Do not change hook commands, generated JSON/TOML structure, or CLI output.
- Do not add compatibility shims without a confirmed consumer and explicit
  removal condition.

## Risks

| Risk | Mitigation |
| --- | --- |
| File relocation accidentally changes generated hook payloads | Preserve existing golden assertions and compare exact JSON/TOML content. |
| Temporary shims become permanent | Give shim removal its own blocking task and require zero old imports before closure. |
| Architecture scanner misses an import form | Plant negative examples for direct import, submodule import, and root `from` import forms. |
| SDK compatibility changes unnecessarily | Adapt module strings at the SDK boundary where the current SDK returns `Path`. |
| Packaging omits moved files | Inspect and import the built wheel outside the checkout. |

## Open Questions

No product decision is currently blocking. During implementation, preserve the
existing SDK return shape unless executable evidence shows it is not part of
the supported surface.
