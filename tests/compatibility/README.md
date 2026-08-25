# External compatibility corpus

This directory freezes what a caller or an operator can observe while xcron
moves from one distribution to a kernel plus externally supplied capability
packages. It must only import `xcron`'s public SDK or execute the `xcron`
console command. It must not import current capability internals, adapters,
channels, renderers, or state stores.

`test_external_contract.py` is intentionally literal about JSON fields, TOON
markers, error exit code/payload, manifest mutation, durable-state keys,
wrapper independence, cron ownership, and launchd labels. A change to any of
these requires a compatibility decision and, where durable data is involved, a
migration—not a routine snapshot update.

## Future package-installation matrix

The tests presently exercise the aggregate development installation. During the
cutover tasks, retain these invariants and make each target a separately
installed wheel check:

<!-- markdownlint-disable MD013 -->

| Installation | Required observable contract | Must not accidentally depend on |
| --- | --- | --- |
| Aggregate `xcron` | Public SDK, all shipped capability providers, and the console script work together. | The repository checkout or `ops/`. |
| Lean SDK host | `import xcron` and typed request models work; missing optional providers fail with their declared structured selection error. | Typer, Rich, TOON, or any channel package. |
| Alternate provider | A third-party provider chosen through its descriptor/entry point performs the same contract use case and owns its own artifacts. | A hard-coded import of xcron's reference provider. |

<!-- markdownlint-enable MD013 -->

The installed-wheel task consumes this corpus from an isolated environment.
Until the package graph exists, the matrix is a target contract rather than a
test suite pretending those distributions already exist.
