# Manifest YAML capability

This provider owns the packaged YAML schema plus loading, semantic validation,
normalization, stable hashing, and atomic YAML mutation. A caller supplies a
resolved workspace in its invocation context; the provider does not resolve
paths through a sibling implementation or inspect process environment.

```sh
just ops packages test xcron-capability-manifest-yaml
just ops packages build xcron-capability-manifest-yaml
```
