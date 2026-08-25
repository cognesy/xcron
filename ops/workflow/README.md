# Delivery workflow

This capability composes the other repository operations into a small local
delivery interface. It does not hide destructive Git actions or host scheduler
integration behind a convenience command.

```sh
just ops workflow
just ops workflow doctor
just ops workflow status
just ops workflow sync
just ops workflow ci
```

`doctor` is non-mutating. `sync` intentionally updates the local dependency
environment. `ci` first proves release-version projections, then runs
catalogue validation, deterministic checks, and the installed-wheel lane; run
it before a release or handoff that needs that level of evidence.
