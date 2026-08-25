# Deterministic quality

This capability delegates to the workspace architecture/metadata and pytest
lanes. It does not define another test command or another quality policy.

```sh
just ops quality          # safe recipe menu
just ops quality architecture  # package and boundary contracts only
just ops quality test     # pytest suite
just ops quality core     # canonical scripts/verify-core.sh
```

`core` is the usual local completion check. The root `just test` aggregate
selects it after validating the operations catalogue.
