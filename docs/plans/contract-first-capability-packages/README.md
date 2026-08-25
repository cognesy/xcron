# Contract-first capability packages

<!-- markdownlint-disable MD013 -->

> Status: implemented. The `packages/`, `capabilities/`, and `ops/` workspace
> described here is now the only runtime implementation; the legacy
> `src/xcron` tree has been removed. The phase files remain the design record.

## Decision in one sentence

Refactor xcron from one distribution containing internal capability modules into
an `uv` workspace of independently installable capability packages, composed
only through a minimal capability host and typed public contracts.

This is a real packaging and ownership boundary. Moving files below
`src/xcron/capabilities/` without separate metadata, entry points, assets,
tests, and installed-artifact checks would not satisfy the goal.

## Why now

xcron is already organized around six internal owner modules (`workspace`,
`manifest`, `reconciliation`, `jobs`, `operations`, and `agent_hooks`). Its
architecture tests correctly prevent private cross-module imports, but
`runtime/composition.py` still imports concrete implementations directly and
the root wheel ships every implementation. Replacing a scheduler, manifest
format, configuration source, or hook integration therefore requires changing
the main distribution and its composition root.

The desired end state is narrower at the center and stronger at the edge:

- the kernel knows how to discover, select, validate, order, and construct a
  capability implementation; it names no xcron product capability;
- contracts own the schedule vocabulary, typed requests/results, port
  protocols, descriptor schema, and stable errors;
- each implementation has one independently testable distribution with its
  code, tests, assets, configuration, documentation, and capability descriptor
  in its own directory;
- repository self-service stays in a separately validated `ops/` catalogue:
  every operational capability owns its manifest, README, safe Just entry
  points, and any scripts, schemas, tests, or agent procedures it needs;
- the SDK and CLI use the same frozen host snapshot and import contracts, never
  an implementation;
- the `xcron` aggregate package installs the historical full provider set,
  preserving the supported command and SDK surface; lean installs fail loudly
  with a typed `capability_unavailable` error rather than guessing or silently
  degrading.

## Source evidence and reference decisions

| Reference | Adopt | Do not adopt |
| --- | --- | --- |
| Current xcron | Its domain-specific ownership, data/control/management plane separation, typed SDK/CLI parity, durable format tests, and scheduler safety rules. | A single root wheel and direct first-party imports in `runtime/composition.py`. |
| Spotter | Descriptor-first registration, frozen host snapshots, explicit provider selection, package-owned schemas/assets, and CLI/SDK contributions from selected capabilities. | Its ledger/schema product semantics. |
| Gitman | PEP 420 capability namespace, entry-point discovery, on-demand typed `host.require`, a meta distribution, a test harness, architecture tests that scan every package root, and no implicit winner for duplicate implementations. | Any Gitman portfolio domain or its storage details. |
| skill-lib | The minimal kernel/contract/SDK/CLI/testing/meta topology, a self-contained capability distribution for every replaceable mechanism, and contract conformance tests. | Its retrieval pipeline and performance budgets. |
| Cordis Python | Versioned, YAML-backed capability specifications and explicit dependency/seam declarations; an `ops/` capability owns a manifest, README, Justfile, and its supporting assets, with a validated explicit provider catalogue. | A long-lived Context/Fiber/plugin runtime; xcron commands are process-scoped and do not need it as a dependency. |
| Intercom | Operations boundaries that keep product code out of `ops/`, schema/ownership/skill/command drift validation, and safe delegated Just discovery. | Its Node-specific operations implementation or agent-trial harness. |

## Invariants that migration must preserve

1. The external CLI, typed SDK use cases, YAML schedule format, marker format,
   wrapper protocol, crontab ownership markers, launchd labels, durable-state
   reader compatibility, output/exit-code rules, and degraded data-plane
   guarantees remain stable.
2. A deployed wrapper never imports or shells back into xcron. Repackaging the
   control plane must not weaken the data-plane outage guarantee.
3. The host never selects an arbitrary provider. Missing, malformed,
   incompatible, duplicate, cyclic, or unselected providers become structured
   startup/namespace errors with installation remedies.
4. A capability can import only `xcron.kernel`, `xcron.contracts`, its declared
   third-party dependencies, and its own code. It may obtain another capability
   only by a declared typed port from the host.
5. Each capability owns its assets and tests. There is no shared catch-all
   production package and no cross-capability private fixture import.
6. The first compatibility release is behaviorally equivalent to today’s full
   installation. Provider substitution is additive; it is not permission to
   rewrite schedules or native scheduler artifacts.
7. Runtime provider packages and repository-operation capabilities are
   different layers. A provider is selected at application host construction;
   an `ops/` capability makes repository maintenance discoverable and
   executable. Neither imports the other’s implementation.

## Plan documents

- [01-current-state-and-seams.md](01-current-state-and-seams.md) records the
  existing ownership map and concrete seams to extract.
- [02-target-architecture.md](02-target-architecture.md) specifies the package
  topology, boot sequence, provider discovery, selection, and ownership model.
- [03-contract-catalogue.md](03-contract-catalogue.md) defines the kernel and
  capability contracts each package must implement.
- [04-migration-and-compatibility.md](04-migration-and-compatibility.md) gives
  the staged execution order, strangler rules, and compatibility proofs.
- [05-verification-and-task-map.md](05-verification-and-task-map.md) maps the
  plan to delegation-ready Beads tasks and completion evidence.
- [06-operations-micropackages.md](06-operations-micropackages.md) specifies
  the metadata-rich, delegated `ops/` catalogue that operates the workspace.

## Explicit non-goals

- No remote plugin marketplace, runtime code download, workspace-supplied
  executable import paths, or arbitrary user Python import target.
- No dynamic in-process unload/reload lifecycle. A normal CLI command creates a
  new host; an embedder obtains an immutable `Xcron` snapshot and closes it.
- No scheduler behavior rewrite, distributed scheduling, or replacement of the
  native `launchd`/`cron` control plane.
- No compatibility shim for private `xcron.capabilities.*` imports. The stable
  surface is the documented SDK and CLI, not implementation paths.
