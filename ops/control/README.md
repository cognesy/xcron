# Operations control

This capability owns the operations catalogue itself: its provider index,
metadata schemas, validator, local tests, and extension procedure.

```sh
just ops control             # show safe local command menu
just ops control list        # list all capabilities
just ops control validate    # validate the catalogue
just ops control aggregate check
just ops control test
```

Add a capability as a complete package, not a loose recipe: give it a manifest,
README, safe `justfile`, and any scripts, schemas, tests, or skills it owns.
Register its service in `ops/ops.yaml` only after the validator passes.
