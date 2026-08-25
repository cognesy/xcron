# Assurance diagnostics

This capability provides named entry points to the existing xqa pilot. They are
diagnostics and configuration checks, not implicit gates for normal development.

```sh
just ops assurance
just ops assurance doctor
just ops assurance status
just ops assurance validate
```

Use the quality and distribution capabilities for xcron's canonical completion
lanes. Run host scheduler integration tests explicitly from
`tests/integration/` when they are needed.
