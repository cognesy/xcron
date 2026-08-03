# Gap analysis against the house standard

Source: `_kb-docs/stepping-stones/templates/agentic-python-multichannel-app`.

Verdicts:

- **holds** — the rule is satisfied and mechanically checked;
- **partial** — satisfied in intent but not enforced, or satisfied for one
  module only;
- **gap** — not satisfied;
- **n/a** — the rule addresses a channel or tier xcron deliberately lacks.

Every **gap** and **partial** maps to a phase in
[03-execution-plan.md](03-execution-plan.md).

## MODULE-ISOLATION.md

| Rule | Verdict | Evidence | Phase |
| --- | --- | --- | --- |
| Named isolation level per module | partial | Only `agent_hooks` claims Level 1; `architecture.md` honestly calls the rest "groupings". | 1 |
| Module card before moving code | partial | One card exists, in the agent-hooks plan. | 1 |
| Module-first layout; layers inside the module | gap | `libs/services/` holds 3,855 lines of four other owners' code. | 2–4 |
| Complete vertical slice, one physical owner | gap | Reconciliation's adapters sit in `libs/services/backends/`. | 3 |
| Incoming calls enter one public surface | partial | `agent_hooks` only; siblings deep-import `.apply`, `.planning`, `.actions`, `.scheduler_registry`. | 1 |
| No sibling implementation imports | holds | No capability imports another capability's internals. | — |
| Cross-module workflows outside the modules | holds | `runtime/composition.py` and the SDK compose; no product policy there. | — |
| Module declares its ports; composition supplies adapters | partial | `SchedulerBackend` is a real port; manifest, state, and metrics access is by direct import. | 3, 5 |
| Acyclic, explicit dependency graph | partial | Acyclic in practice; no declared graph, so nothing fails when it stops being. | 7 |
| `shared/` is a leaf | gap | No `shared/` exists; `libs/services/` performs the role without the constraint. | 4 |
| Composition root is the only privileged place | holds | `libs/runtime/` is composition only. | — |
| Contracts are closed typed values | partial | Capability results are Pydantic; `extra="forbid"` is not applied uniformly. | 6 |
| No import-time side effects | holds | Verified by the fresh-process import test. | — |
| One owner per table/file subtree/schema | gap | Metrics store written by two capabilities. | 5 |
| Independence contract (Import Linter/Tach) | gap | Neither tool is configured. | 7 |
| Public-surface check for every module | partial | Implemented for `agent_hooks`, including all four import forms. | 7 |
| Planted negative tests | partial | `agent_hooks` only. | 7 |
| Package-manifest check | gap | Hand-listed `packages = [...]`, containing dead `xcron_libs.infra`. | 6 |
| Module-owned test lane | partial | `tests/modules/agent_hooks/` only; 34 flat test modules remain. | 1–5 |
| Clean-break / degraded-mode tests | n/a | Nothing is optional or independently installed at Level 1. | — |
| Time-boxed compatibility shims | gap | `xcron_libs.actions` has no expiry; 15 test modules still use it. | 6 |

## REFERENCE-STRUCTURE.md

| Rule | Verdict | Evidence | Phase |
| --- | --- | --- | --- |
| Capability-first organization | holds | Five capability packages in product vocabulary. | — |
| Domain imports no channel/adapter/framework | holds | Enforced by the architecture test. | — |
| Actions own the transaction boundary, no rendering | holds | Capability results are channel-neutral. | — |
| Ports name volatile dependencies | partial | Scheduler only. Filesystem, clock, and subprocess are imported directly. | 3, 5 |
| Runtime is composition without product policy | holds | `XcronRuntime` resolves options and builds the registry. | — |
| Workspace resolved before composition and passed in | gap | `resolve_project_root` is called from `apps/cli/common.py` and re-derived downstream. | 5 |
| Settings validated before composition | gap | No `Settings` model exists. | 5 |
| Public naming follows user vocabulary | partial | `app.jobs`, `app.schedules` are good; the import root `xcron_libs` exposes repository layout. | 8 |
| Module-owned resources | gap | `xcron_resources.{help,schemas,logging}` is a shared resource package. | 4 |

## CHANNELS.md

| Rule | Verdict | Evidence | Phase |
| --- | --- | --- | --- |
| Channels do only validate/translate/invoke/project | holds | Typer commands open `Xcron` and map results. | — |
| One documented root import, `open()`, idempotent `close()` | holds | `from xcron_libs import Xcron`. | — |
| Stable `ClientClosedError` and use-after-close | holds | Tested in `tests/test_sdk.py`. | — |
| Typed capability APIs, not one god client | holds | `schedules`, `jobs`, `operations`, `hooks`, `home`. | — |
| Optional dependency injection for tests | holds | Backend registry injection is supported. | — |
| `py.typed` in the built wheel | gap | No marker file anywhere in the tree. | 6 |
| Examples tested against the installed wheel | partial | An installed-import smoke exists; no example is executed. | 6 |
| CLI fully argumented, non-interactive, structured stdout | holds | AXI contract, exit codes 0/1/2, structured usage errors. | — |
| Logs and diagnostics on stderr | holds | structlog to stderr. | — |
| Command maps to one use case | holds | 26 commands, one SDK call each. | — |
| Plane-aware CLI metadata | partial | Behaviour is correct; authority is not stated in help or docs. | 9 |
| Local SDK versus remote client named separately | n/a | No remote client exists. | — |
| REST / web / generated client | n/a | Deliberate non-goal. | — |
| Declared channel parity matrix | gap | No parity table exists. | 9 |

## WORKSPACES-AND-CONFIGURATION.md

| Rule | Verdict | Evidence | Phase |
| --- | --- | --- | --- |
| Validated marker, not directory name | gap | Any directory with `schedules/` is accepted. | 5 |
| Declared root precedence with a typed not-found error | partial | Precedence exists and has typed errors, but no environment root and no marker validation. | 5 |
| Workspace schema version and migration policy | gap | No version is recorded on disk. | 5 |
| Typed `Workspace` with owned paths | gap | Paths are re-derived in `state_store`, `logging_paths`, and `metrics`. | 5 |
| No process-global active workspace | holds | Options are resolved per call and passed explicitly. | — |
| Trackable config separated from generated state | partial | True on disk (`resources/schedules` versus `~/.xcron`); not expressed as a typed contract. | 5 |
| Idempotent init returning a typed change set | partial | `init_home` is idempotent; it returns a result but writes no marker. | 5 |
| One app-owned XCFG adapter | gap | Hand-written single-layer loader. | 5 |
| Strict `Settings` with `extra="forbid"` | gap | No settings model. | 5 |
| Only the configuration adapter reads the environment | gap | Read in `config_loader` and `metrics`. | 5 |
| Precedence tested at every adjacent edge | gap | No layered precedence to test yet. | 5 |
| Two workspaces in one process | partial | Structurally possible; untested. | 5 |

## CONVENTIONS-AND-GUARDRAILS.md

| Rule | Verdict | Evidence | Phase |
| --- | --- | --- | --- |
| Typed flow to the channel boundary | holds | Pydantic in, Pydantic out, projection at the edge. | — |
| Three serialization owners | partial | Correct in practice; the projection cluster physically sits in `libs/`. | 2 |
| Stable semantic error hierarchy below channels | holds | `XcronError` family plus `AgentHooksError`. | — |
| No `typer.Exit` below the channel | holds | Enforced by the architecture test. | — |
| Versioned durable/wire contracts | partial | `project-state.json` and manifests are durable; no literal schema discriminator is asserted in tests. | 5 |
| One writer per state family | gap | Metrics. | 5 |
| Least privilege / authorization per action | n/a | Single-user local tool; no multi-tenant surface. | — |
| Observability through a port, correlation context at edges | partial | structlog is imported directly by capability code. | 4 |
| Small mandatory dependency set, channels as extras | gap | `typer`, `rich`, `python-toon` are mandatory. | 6 |
| Import enforcement in the quality gate | partial | One hand-written test file; no declared contracts. | 7 |
| Required test lanes (unit/SDK/CLI/parity/architecture) | partial | Unit, SDK, CLI, and architecture exist; no parity lane, no per-module lanes. | 1–5, 7 |

## COMPOSITION-AND-EXTENSIONS.md

| Rule | Verdict | Evidence | Phase |
| --- | --- | --- | --- |
| Choose the least powerful extension tier | holds | Tier 1 typed registry; no plugin platform. Recorded as a deliberate exclusion. | — |
| Explicit registration; deterministic duplicate policy | holds | `SchedulerRegistry` rejects duplicates and unknown identities, with tests. | — |
| Composition order: workspace → settings → adapters → actions → channels | partial | Adapters and actions are correct; workspace and settings stages are missing. | 5 |
| One composition policy across channels | holds | CLI and SDK share `XcronRuntime`. | — |
| Tier 2 / Tier 3 mechanisms | n/a | Deliberate non-goal for first-party backends. | — |

## PLANE-MAP.md and SEPARABLE-PLANES

| Rule | Verdict | Evidence | Phase |
| --- | --- | --- | --- |
| Written plane map for real behaviour | gap | A five-row ownership sketch exists in the previous plan; no boundary, contracts, or degraded behaviour. | 9 |
| One authoritative writer per plane state family | gap | Metrics. | 5 |
| Cross-plane contracts typed and versioned | partial | `project-state.json` is the real control-plane snapshot; its schema version is not asserted. | 5, 9 |
| Degraded behaviour documented and drilled | gap | No drill exists for "scheduler unavailable" or "derived state missing/stale". | 9 |

## Summary

- **holds:** 25 rules — mostly the results of the previous refactor, and they
  must not regress.
- **partial:** 24 rules — real intent, missing enforcement or applied to one
  module only.
- **gap:** 22 rules — concentrated in three clusters: the unowned
  `libs/services/` bucket, the missing workspace/configuration contract, and
  missing mechanical enforcement.
- **n/a:** 7 rules — REST, web, remote client, Tier 2/3 extensions, and
  multi-tenant authorization, all deliberate non-goals.

The three clusters are independent and can be executed in any order, but the
plan sequences ownership first, because the workspace and enforcement work is
cheaper to do once each module owns its own paths.
