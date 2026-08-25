---
name: xcron-repository-operations
description: Extend or run xcron's metadata-driven repository operations catalogue.
---

# xcron repository operations

Use this skill when changing the local `ops/` catalogue or choosing a
repository self-service operation.

1. Start with `just` or `just ops <capability>`; a no-argument capability call
   must only list its recipes.
2. Keep the canonical script, test, or tool as the implementation. Local
   recipes are delegating interfaces, not copied workflows.
3. A new capability must own `capability.yaml`, `README.md`, `justfile`, and
   every support asset beneath its own `ops/<id>/` directory.
4. Add one `active` provider mapping in `ops/ops.yaml` for every provided
   service, then run `just validate` and the relevant lane.
