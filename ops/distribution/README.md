# Distribution verification

This capability builds every independently addressable wheel, then runs the
clean-install matrix. It is intentionally separate from deterministic
source-tree tests because it resolves packages into isolated environments.

```sh
just ops distribution
just ops distribution wheel
just ops distribution packages   # individual provider closure and wheel contents
just ops distribution aggregate  # default SDK/provider install without the CLI
just ops distribution lean       # kernel + contracts + SDK only
just ops distribution alternate  # selected test provider replaces metrics
just ops distribution cli        # xcron[cli] console and help assets
```

The full `wheel` lane also demonstrates malformed, incompatible, unavailable,
and cyclic provider diagnostics inside a clean lean install. Run it before
release work or after changing packaging, package data, console entry points,
or optional dependency boundaries.
