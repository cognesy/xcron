# xcron SDK

`xcron-sdk` is the terminal-free, typed Python client for xcron. It discovers
installed providers through the capability kernel and speaks only the stable
contracts package; it imports no scheduler, YAML, hooks, logging, or rendering
implementation.

`Xcron.open()` resolves workspace and settings once. Its compatibility groups
remain lazy: `schedules`, `jobs`, `operations`, `hooks`, and `home` request
their corresponding public port only when reached. An embedder can select a
competing implementation with `CapabilitySelection` without changing SDK code.

```sh
just ops packages test xcron-sdk
just ops packages build xcron-sdk
```
