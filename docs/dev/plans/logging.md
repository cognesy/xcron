# Logging Configuration Plan

## Goal

Make `xcron`'s structured logging contract explicit and configurable through a checked-in logging configuration file, while preserving AXI output boundaries:

- stdout remains command output in TOON/JSON/text.
- stderr receives operational logs and diagnostics.
- launchd/cron wrapper logs remain job-run logs, separate from CLI result output.

## Current State

`xcron` already depends on `structlog` and has `libs/services/observability.py`.
It configures logs from environment variables:

- `XCRON_LOG_LEVEL`
- `XCRON_LOG_FORMAT`

It logs action start/finish/failure and subprocess start/finish/failure.

## Target Configuration

Add a config file, proposed path:

```text
resources/logging/default.yaml
```

Expected shape:

```yaml
version: 1
logger: xcron
destination: stderr
format: auto
level: INFO
timestamp: iso
events:
  actions: true
  subprocesses: true
  scheduler_wrappers: true
fields:
  include:
    - event
    - level
    - timestamp
    - action
    - process_event
    - command
    - duration_ms
    - returncode
  redact:
    - env
    - token
    - secret
```

Environment variables should override the file for local operations:

- `XCRON_LOG_LEVEL`
- `XCRON_LOG_FORMAT`

## Approach

1. Introduce a small typed logging config model and loader.
2. Update `configure_logging()` to read the default config before applying env overrides.
3. Keep `structlog.PrintLoggerFactory(file=sys.stderr)` or equivalent stderr routing.
4. Add tests proving logs go to stderr and command output stays parseable.
5. Document the config file and override variables.

## Task Breakdown

1. Add `resources/logging/default.yaml` and typed loading.
2. Wire `libs/services/observability.py` to the config.
3. Add tests for default config, env overrides, and stdout/stderr separation.
4. Update user/dev docs with logging operation notes.

## Risks

- Wrapper logs and application logs can be confused. Keep wrapper stdout/stderr paths documented separately.
- Subprocess command logging can expose sensitive arguments. Apply redaction before logging env-like values.

## Open Questions

- Should cron backend logs always use JSON regardless of terminal status?
- Should launchd wrapper logs include the selected log format in their `job_started` lines?
