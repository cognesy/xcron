# Python SDK

`xcron_libs.Xcron` is the supported in-process composition surface for Python
callers. The Typer CLI uses the same client, so the SDK and CLI do not maintain
separate scheduling implementations.

## Opening a client

```python
from xcron_libs import Xcron

with Xcron.open("/path/to/project", backend="cron") as xcron:
    plan = xcron.schedules.plan()
    if plan.valid:
        applied = xcron.schedules.apply()
```

`Xcron.open(...)` resolves path options once and captures the selected project,
schedule, backend, platform, state root, and isolated scheduler overrides. The
client is synchronous, is safe to close repeatedly, and raises
`ClientClosedError` if an API is used after close.

The current runtime owns no persistent scheduler connection. Lifecycle support
is still explicit so future owned resources can be added without changing the
public client shape.

## Grouped APIs

| API | Operations |
| --- | --- |
| `schedules` | `validate`, `plan`, `status`, `apply`, `inspect`, `prune` |
| `jobs` | `list`, `show`, `add`, `update`, `enable`, `disable`, `remove` |
| `operations` | `list_logs`, `clear_logs`, `show_metrics`, `reset_metrics` |
| `hooks` | `install`, `status`, `repair`, `session_end` |
| `home` | `initialize` |

Every public SDK method has an explicit typed return. Results are capability
models such as `PlanProjectResult`, `JobActionResult`, and `MetricsResult`, not
CLI response envelopes. TOON, JSON, tmux projection, field selection, stdout,
stderr, and exit codes remain owned by `apps/cli`.

Validation and operational failures normally return the same structured
`valid=False` results used by the CLI. Client lifecycle failures raise
`ClientClosedError`. Provider registration errors remain deterministic
`ValueError` failures from `SchedulerRegistry`.

## Provider injection

Tests and embedders may supply an explicit `SchedulerRegistry`:

```python
with Xcron.open(project, backend="test", scheduler_registry=registry) as xcron:
    result = xcron.schedules.plan()
```

The registry is a trusted in-process seam for first-party scheduler adapters,
not a plugin discovery system. The built-in runtime registers `launchd` and
`cron` explicitly. A future `systemd` adapter should implement the same typed
reconciliation port and be added at the runtime composition root.

Host-effect overrides (`state_root`, `launch_agents_dir`, `crontab_path`,
`manage_launchctl`, and `manage_crontab`) are available on `Xcron.open(...)` for
isolated integration tests. Callers remain responsible for choosing safe paths
and mutation flags.

## Dependency boundary

The SDK composes capability actions and the runtime registry only. It must not
import Typer, `xcron_cli`, CLI response models, field contracts, or renderers;
architecture tests enforce that boundary. Capability results likewise remain
independent of the CLI services facade so importing the SDK does not pull the
output channel into application code.
