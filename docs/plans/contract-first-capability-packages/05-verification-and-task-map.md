# Verification and task map

<!-- markdownlint-disable MD013 -->

## Completion proof

The refactor is complete only when all of the following are true in the current
worktree and clean install environments:

1. The source tree has the package/capability layout in
   [02-target-architecture.md](02-target-architecture.md), and every capability
   directory is independently buildable with code, tests, documentation,
   descriptor, and all owned assets present.
2. `xcron-kernel` names no product capability or provider package; contracts
   name no provider mechanism; SDK/CLI name only kernel/contracts and their
   own channel code.
3. Every production capability is discovered from an `xcron.capabilities`
   entry point, descriptor-validated, dependency-ordered, and selected only by
   the host. Duplicate/missing/incompatible/cyclic providers have typed tests.
4. The aggregate installation preserves all current user-visible behavior
   proven by CLI/SDK parity, durable format, degraded behavior, and integration
   suites. No deployed wrapper calls into xcron.
5. A lean installation and a selected alternate test provider prove that
   implementations are actually replaceable, not merely package-shaped.
6. Full quality, architecture, contract-conformance, each-package, aggregate,
   lean, and real scheduler lanes pass. Documentation and the operations
   catalogue describe the new source of truth.
7. The `ops/` catalogue proves every self-service capability is owned,
   described, safely discoverable, and executable through a local Justfile;
   package routes delegate to, rather than duplicate, package-local lanes.

## Required verification lanes

| Lane | What it proves | Final command shape |
| --- | --- | --- |
| Contract unit/conformance | Models, ports, host errors, and each provider satisfy its public protocol. | `uv run pytest packages/xcron-contracts capabilities/*/tests` |
| Architecture | No provider-private imports, channel leakage, kernel product names, or asset ownership conflicts across all package roots. | `just architecture` |
| Package lane | Every package works with only its declared dependency closure. | `just package-test <distribution>` |
| Aggregate compatibility | Full default provider set retains CLI/SDK and durable behavior. | `just verify-aggregate-wheel` |
| Lean selection | Missing capabilities and alternate selection are explicit and typed. | `just verify-lean-wheel` |
| Core behavior | Existing deterministic xcron behavior continues. | `just core` |
| Native integration | Real launchd and Docker cron still reconcile/run/prune correctly. | explicit `just integration-launchd` / `just integration-cron` |
| Operations metadata | The `ops/` catalogue delegates to package-local/aggregate lanes without duplicating them. | `just validate && just ops workflow ci` |
| Operations routing | Discovery routes and package-local Just delegation are safe from the root and a subdirectory. | `just ops && just ops list && just ops packages doctor` |

The final root `just` aliases are not the authoritative implementation. They
discover package-local recipes and compose the above checked lanes.

## Beads execution graph

The epic contains these tasks. Every task must cite the plan directory in its
description, claim itself before edits, update docs/tests with its code, run the
specified lane, and close only with evidence.

```text
compatibility corpus ──┐
workspace/kernel ──────┼─> contracts/testing ─> prerequisites ─> scheduler
                       │                            │               │
                       │                            ├─> management ──┤
                       │                            └─> SDK/CLI ─────┤
                       └──────────────────────────────────────────────┤
                                                               aggregate/cutover
```

| Order | Task | Depends on | Deliverable |
| --- | --- | --- | --- |
| 1 | Baseline compatibility corpus | none | Black-box behavior/durable/degraded fixtures and baseline report. |
| 2 | Operations micropackage foundation | none | Safe `ops` routing, validated package-operation contract, and delegated package-local Just model. |
| 3 | Workspace packaging and kernel host | 2 | `uv` workspace, minimal kernel, entry-point registry, host/error tests. |
| 4 | Contracts and testing harness | 3 | Frozen typed vocabulary, conformance kit, cross-package architecture scanner. |
| 5 | Prerequisite provider packages | 4 | Workspace, settings, observability, manifest providers with assets/tests/local Justfiles. |
| 6 | Native scheduler provider | 5, 1 | Reconciliation provider preserving wrapper/native artifact guarantees. |
| 7 | Management provider packages | 5, 6 | Jobs, logs, metrics, and agent-hook providers. |
| 8 | SDK host composition | 4, 5, 6, 7 | No direct provider imports; compatibility group facade/lifecycle. |
| 9 | CLI contribution channel | 4, 8 | Dynamic contribution attachment, AXI/help/output parity. |
| 10 | Aggregate packaging and installed verification | 1, 2, 3, 4, 5, 6, 7, 8, 9 | Default meta distribution plus aggregate/lean/alternate-provider wheel tests. |
| 11 | Cutover, docs, and operations | 10 | Remove bridge, register package operations, update specs/docs/ops, full completion audit and release proof. |

## Task sizing and coordination rule

Tasks 4 and 6 are parent tasks with provider-package child tasks if their
implementation cannot be completed as a cohesive dependency-ordered unit.
Every child must remain independently installable and may not reach into a
sibling source tree. The scheduler task is intentionally one compatibility
unit; do not create parallel launchd/cron extraction tasks until native shared
contracts are proven.

No task may merge an unresolved behavior change under the label “refactor.” A
desired product change gets a separately linked Beads issue with its own
contract and compatibility decision.
