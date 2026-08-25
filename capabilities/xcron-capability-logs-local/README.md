# Logs local capability

This provider lists and truncates wrapper logs within the derived xcron-owned
log directory only. It preserves the dry-run default, never accepts arbitrary
paths, and deliberately has no metrics dependency.

```sh
just ops packages test xcron-capability-logs-local
just ops packages build xcron-capability-logs-local
```
