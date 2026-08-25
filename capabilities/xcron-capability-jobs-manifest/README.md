# Jobs manifest capability

This provider is the typed, YAML-only job-management boundary. It validates a
selected project through `ScheduleControlPort`, then reaches `ManifestPort` for
every read and mutation. It never writes scheduler artifacts.

```sh
just ops packages test xcron-capability-jobs-manifest
just ops packages build xcron-capability-jobs-manifest
```
