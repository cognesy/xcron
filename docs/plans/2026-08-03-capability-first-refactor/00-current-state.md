# Current-state evidence

## xcron as observed on 2026-08-03

The code is structured globally by technical layer:

```text
apps/cli/typer_app.py       806-line Typer shell
libs/actions/               validate, plan, status, apply, jobs, logs, metrics
libs/services/              manifest/state/rendering/logging/config services
libs/services/backends/     cron and launchd implementations
libs/domain/                normalized manifest, diffing, state models
```

The documented direction is `apps/cli -> libs/actions -> libs/services ->
libs/domain`, but the live implementation does not fully hold it:

- `libs/services/backends/cron_service.py` imports
  `xcron_libs.actions.plan_project.PlanProjectResult`.
- `libs/services/backends/launchd_service.py` imports the same action result.
- `apply_project` constructs that action result solely to pass it back down to
  a backend.

That coupling makes it difficult to use the backends from an SDK or a future
channel and makes action result evolution an adapter compatibility change.

Other relevant observations:

- `plan` compares desired state with xcron's derived state; `status` compares
  it with the actual scheduler; `apply` deliberately starts from `status`.
  This distinction is a product invariant, not a folder concern.
- `jobs` changes YAML only; reconciliation remains the explicit `apply` step.
- Existing CLI response models, contracts, mappers, and `Output` correctly
  keep TOON/JSON/tmux projection at the channel edge and must stay there.
- Tests import legacy actions and some backend functions directly. Compatibility
  re-exports and focused boundary tests allow migration without a flag day.

## Directional references used

### XQA and CXTK

XQA organizes code as capability vertical slices and proves boundaries with
architecture tests. Its metadata-only process extension protocol is valuable
when independently released code needs dependency/crash isolation. CXTK also
uses closed protocol models, provider identity checks, and a public SDK with
the CLI kept at the projection boundary.

xcron needs the *capability and contract* lessons, but not their process
extension mechanism. `cron` and `launchd` are first-party adapters with a
shared release and runtime lifecycle; their proper isolation tier is a typed
in-process provider port.

### xfind SDK

xfind's `Xfind.open(...)` is a composition root: it resolves workspace and
configuration once, owns only resources it creates, exposes grouped APIs, is a
context manager, and prevents use after close. Its CLI opens that client and
maps typed errors/output only at the shell edge. xcron should use the same
channel relationship without copying xfind's database-specific machinery.

### Stepping Stones

The principles call for small verifiable stones, information hiding around
volatile implementation decisions, typed data flow to channel boundaries, one
owner per durable state family, and import enforcement rather than reliance on
folders. They also distinguish data/control/management planes from package
layout. For xcron:

- desired manifest editing and hooks are management-plane capabilities;
- reconciliation is control-plane work; and
- wrapper execution and logs are data/runtime evidence.

These labels clarify state ownership but do not require a separate process or
top-level directory for each plane.
