# xcron Logging

`xcron` uses `structlog` for application-level operational events. The default
logging contract is checked in at:

```text
resources/logging/default.yaml
```

The default destination is stderr. This keeps stdout reserved for command
payloads in TOON or JSON, including structured error payloads. Application logs
include action lifecycle events and backend subprocess lifecycle events.

Runtime overrides:

```sh
XCRON_LOG_LEVEL=DEBUG xcron validate
XCRON_LOG_FORMAT=json xcron status --output json
```

Supported log formats are:

- `auto` - JSON when stderr is non-interactive, console rendering for terminals
- `json` - newline-delimited JSON events on stderr
- `console` - human-oriented console rendering on stderr

The logging config also defines redaction patterns for subprocess command
arguments. Arguments with configured sensitive keys such as `token`, `secret`,
or `env` are redacted before being attached to structured subprocess events.

Wrapper logs are separate. Managed scheduler jobs still write their command
stdout and wrapper lifecycle lines to deterministic per-job files under the
xcron state root, and those paths are surfaced by `xcron inspect`.
