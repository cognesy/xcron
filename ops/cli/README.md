# CLI contract

This capability makes the agent-facing CLI surface easy to verify without
moving command logic outside `xcron.channels.cli`.

```sh
just ops cli
just ops cli help
just ops cli contract
just ops cli capture /tmp/xcron-cli-golden
```

`capture` delegates to `scripts/capture-cli-golden.sh`. That script only uses
help and other read-only command surfaces; it never applies, prunes, or checks
host scheduler state.
