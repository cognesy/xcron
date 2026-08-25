# Workspace package operations

This capability is the repository-level directory for package self-service.
It discovers independently installable distributions under `packages/` and
`capabilities/`, checks their metadata and required local Just routes, then
delegates to the package-local implementation.

It deliberately does not build or test a package itself. A distribution owns
its code, tests, assets, descriptor, and `justfile`; this capability only
makes those local lanes discoverable from the repository root.

```sh
just ops packages list
just ops packages doctor
just ops packages check xcron-kernel
just ops packages test xcron-capability-manifest-yaml
just ops packages build xcron
```

Until the capability-package migration creates the workspace directories,
`list` and `doctor` report that there are no package distributions. That is an
informational state, not a missing-product failure. Once a package directory
exists, it must carry a `pyproject.toml` and a local Justfile with `default`,
`list`, `doctor`, `check`, `test`, and `build` recipes.
