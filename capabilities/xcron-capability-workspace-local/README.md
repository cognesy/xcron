# Workspace local capability

This provider owns xcron project identity, marker compatibility, home/state
layout, runtime-path containment, and non-destructive initialization. It has
no dependency on a scheduler, manifest parser, terminal, or sibling provider.

The entry point advertises `workspace:local` and registers the `workspace`
port. Its starter manifest is a package-contained resource, so a lean
installation has every asset initialization needs.

```sh
just ops packages test xcron-capability-workspace-local
just ops packages build xcron-capability-workspace-local
```
