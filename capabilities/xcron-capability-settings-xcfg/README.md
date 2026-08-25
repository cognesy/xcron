# Settings xcfg capability

This provider composes strict xcron settings from its package-contained default,
an explicit workspace config path, and the caller-supplied environment snapshot.
It imports the third-party layering mechanism directly but neither the legacy
root configuration module nor any sibling provider.

```sh
just ops packages test xcron-capability-settings-xcfg
just ops packages build xcron-capability-settings-xcfg
```
