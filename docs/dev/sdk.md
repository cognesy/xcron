# Python SDK

`xcron.sdk` is the stable in-process API. It is a typed facade over the same
capability ports the CLI uses; it does not import the terminal channel or a
concrete provider.

## Opening a client

```python
from xcron.sdk import Xcron

with Xcron.open("/path/to/project", backend="cron") as xcron:
    plan = xcron.schedules.plan()
    if plan.valid:
        xcron.schedules.apply()
```

`Xcron.open(...)` resolves workspace identity and settings once, selects the
installed capability descriptors, and captures immutable invocation options.
It is synchronous, context-managed, safe to close repeatedly, and raises
`ClientClosedError` after close.

## Grouped APIs

| API | Operations |
| --- | --- |
| `schedules` | `validate`, `plan`, `status`, `apply`, `inspect`, `prune` |
| `jobs` | `list`, `show`, `add`, `update`, `enable`, `disable`, `remove` |
| `operations` | `list_logs`, `clear_logs`, `show_metrics`, `reset_metrics` |
| `hooks` | `install`, `status`, `repair`, `session_start`, `session_end` |
| `home` | `initialize` |

Every method returns a contract model, not a CLI response envelope. TOON, JSON,
tmux, field selection, stdout, stderr, and exit codes belong to
`packages/xcron-cli/src/xcron_cli/`.

## Typed job mutations

```python
from xcron.sdk import (
    JobCreateRequest,
    JobUpdateField,
    JobUpdateRequest,
    ScheduleRequest,
    Xcron,
)

with Xcron.open("/path/to/project", backend="cron") as xcron:
    xcron.jobs.add(
        JobCreateRequest(
            job_id="cleanup",
            command="./scripts/cleanup.sh",
            schedule=ScheduleRequest.every("1h"),
            env={"MODE": "safe"},
        )
    )
    xcron.jobs.update(
        "cleanup",
        JobUpdateRequest(
            schedule=ScheduleRequest.cron("0 * * * *"),
            clear_fields=frozenset({JobUpdateField.ENV}),
        ),
    )
```

`JobsAPI.add` accepts `JobCreateRequest`, and `JobsAPI.update` accepts
`JobUpdateRequest`; raw mappings are intentionally not a public mutation API.
`JobUpdateRequest` requires at least one change or explicit clear and rejects a
field being set and cleared in one request.

## Provider selection

Normally `Xcron.open` discovers the default installed descriptors. Tests and
advanced embedders can pass a `CapabilityRegistry` and `CapabilitySelection`
to choose an installed alternative deterministically. Capability discovery errors
are typed and explain unavailable, malformed, incompatible, cyclic, ambiguous,
or colliding providers rather than silently selecting one.

The plain `xcron` aggregate installs the SDK and default providers without
Typer, Rich, or TOON. Install `xcron[cli]` only when the `xcron` console command
is required.
