# Agent hooks local capability

This provider owns the repo-local Codex and Claude hook files plus
session-history recording. It preserves unrelated hook payload data and uses a
typed request for an explicit xcron executable when discovery is unsuitable.

```sh
just ops packages test xcron-capability-agent-hooks-local
just ops packages build xcron-capability-agent-hooks-local
```
