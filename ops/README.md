# Repository operations

`ops/` is xcron's catalogue of repository self-service operations. Each
capability is a small, independently described package that owns its metadata,
documentation, executable recipes, and any narrow support assets.

The catalogue does not replace project commands. Capability recipes delegate to
the canonical scripts, tests, and tools that already define xcron behaviour.
That keeps a convenient operator interface from becoming a second source of
truth.

## Use

```sh
just                         # discover root and operations commands
just ops quality             # discover one capability safely
just ops quality core        # deterministic import and test lane
just ops cli capture path/to/golden
just validate                # validate the operations catalogue
just check                   # deterministic repository checks
just test                    # full deterministic test lane
```

Every capability contains:

- `capability.yaml` — machine-readable contract, ownership, dependencies, and recipes;
- `README.md` — human-facing scope and safe usage;
- `justfile` — executable local entry points, with a no-argument command menu.

`ops/control` owns the catalogue contract and validator. It verifies that each
asset under `ops/` has exactly one owner, provider mappings are valid,
dependencies are acyclic, documented commands exist locally, and declared
skills are present.

## Capability catalogue

| Capability | Owns | Primary command |
| --- | --- | --- |
| `control` | catalogue schema and validation | `just ops control validate` |
| `quality` | deterministic import and test checks | `just ops quality core` |
| `distribution` | clean installed-wheel verification | `just ops distribution wheel` |
| `cli` | help and output-contract checks | `just ops cli contract` |
| `assurance` | xqa diagnostic entry points | `just ops assurance doctor` |
| `skills` | packaged skill discovery and smoke checks | `just ops skills check` |
| `workflow` | repository readiness and CI composition | `just ops workflow doctor` |

Host scheduler integration remains explicit under `tests/integration/`; it is
not folded into the default deterministic operations lanes.
