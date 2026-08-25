# Metrics local capability

This provider owns the small local metrics store and returns a context-bound
`OutcomeSink` for the aggregate host. Every read, reset, and outcome write is
best effort: an unreadable or unwritable store never interrupts product work.

```sh
just ops packages test xcron-capability-metrics-local
just ops packages build xcron-capability-metrics-local
```
