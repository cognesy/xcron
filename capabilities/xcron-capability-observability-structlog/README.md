# Observability structlog capability

This provider owns the structured logging configuration and its package-local
resource. Its public logging functions accept explicit environment snapshots;
the kernel-facing port yields a best-effort outcome sink and never takes over
metrics persistence.

```sh
just ops packages test xcron-capability-observability-structlog
just ops packages build xcron-capability-observability-structlog
```
