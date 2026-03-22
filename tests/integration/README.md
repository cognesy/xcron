# Integration Harnesses

These checks are explicit-only. They do not run as part of the default
`uv run pytest` suite.

## macOS launchd

Run the real host `launchd` integration test with structured logs enabled:

```sh
XCRON_RUN_LAUNCHD_IT=1 XCRON_LOG_FORMAT=json XCRON_LOG_LEVEL=INFO uv run pytest tests/integration/launchd_real_it.py -s
```

## Linux cron via Docker/Colima

Build the slim cron image and run the isolated end-to-end harness:

```sh
./tests/integration/run_cron_it.sh
```

The cron harness:

- uses Docker/Colima rather than the host scheduler
- installs the project with `uv`
- runs real `crontab` and `cron` inside the container
- verifies `apply`, `status`, `inspect`, scheduled execution, and `prune`
