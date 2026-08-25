# `scheduler:native`

This self-contained runtime capability provides `ScheduleControlPort` as
`scheduler:native`. It owns the complete native compatibility unit:

- desired-vs-actual planning, status, apply, prune, and inspect;
- the durable `project-state.json` reader/writer and managed wrapper protocol;
- cron ownership blocks and launchd labels/plists; and
- native subprocess and scheduler-registry boundaries.

It consumes the selected `workspace` and `manifest` capabilities only through
their public typed ports. It does not import a concrete peer provider or make
metrics/observability a prerequisite for scheduler convergence. Its deployed
wrappers are deliberately self-contained and never call the xcron control
plane.

The local command surface is executable from this repository:

```sh
just --justfile capabilities/xcron-capability-scheduler-native/justfile doctor
just --justfile capabilities/xcron-capability-scheduler-native/justfile check
just --justfile capabilities/xcron-capability-scheduler-native/justfile build
```

`check` exercises cron, launchd, fake-adapter, durable-state, wrapper, inspect,
prune, and broken-event-sink behavior through the provider port. The explicit
host integration harnesses remain at `tests/integration/`, because they verify
the aggregate distribution's public CLI against real launchd and cron.
