# Distribution verification

This capability reaches the existing installed-wheel lane. It is intentionally
separate from deterministic source-tree tests because it builds a wheel and
creates isolated environments.

```sh
just ops distribution
just ops distribution wheel
```

Run it before release work or after changing packaging, package data, console
entry points, or optional dependency boundaries.
