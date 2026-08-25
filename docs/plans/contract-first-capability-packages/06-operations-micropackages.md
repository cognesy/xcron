# Repository operations micropackages

<!-- markdownlint-disable MD013 -->

## Boundary

`ops/` is xcron's repository self-service control plane. It is deliberately
not the product capability host: it does not take part in SDK/CLI discovery,
and product code may not import it. It describes how maintainers inspect,
test, build, package, release, and verify the package workspace.

The existing xcron catalogue already has the intended outer shape. This
refactor must retain and strengthen it as the number of independently
installable runtime providers grows. The Cordis Python and Intercom precedents
are used for its ownership and delegation model, not as a runtime dependency.

## Capability anatomy

Every repository-operation capability has one owned directory:

```text
ops/<id>/
├── capability.yaml       # versioned manifest: provider, ownership, commands
├── README.md             # scope, prerequisites, safe invocation, decisions
├── justfile              # safe default plus only this capability's recipes
├── bin/                  # optional executable implementation
├── schema/               # optional local data/schema assets
├── tests/                # optional focused operation tests
└── skills/<name>/        # optional durable agent procedure
    └── SKILL.md
```

`capability.yaml` declares `id`, `provides`, `status`, `requires.tools`,
`requires.capabilities`, `owns`, `reads`, `generates`, `commands`, and
`skills`. The directory name and `id` match. `owns` includes the capability's
own directory, so no operation asset is left orphaned. `README.md` and a safe
`default` Just recipe are mandatory even for a capability whose implementation
is only delegation.

`ops/ops.yaml` is the explicit provider selection table. It has exactly one
active provider per operational interface. It is an audited record of choice;
the operation dispatcher never reads it to choose a command dynamically.

## Required xcron operational capabilities

The current `control`, `quality`, `distribution`, `cli`, `assurance`, `skills`,
and `workflow` capabilities remain their existing decisions. Add a
`packages` (or more narrowly named replacement) capability when workspace
package build/conformance/install proof becomes an independent maintenance
decision. Do not make `control` a catch-all.

The package operation capability owns its descriptor/schema/check scripts and
delegates to each package-local Justfile. It exposes at least:

| Command | Contract |
| --- | --- |
| `list` | Print every package/provider, its distribution name, capability implementation, and local operation menu. |
| `check <distribution>` | Run the named package's declared fast checks from its own Justfile. |
| `test <distribution>` | Run the named package's declared test/conformance lane. |
| `build <distribution>` | Build only that distribution in an isolated target. |
| `doctor` | Report missing local tools, missing package metadata, or a package that lacks its required operational entries. |

An individual runtime distribution retains a `justfile` at its root for local
development. Its default is discovery-only. That Justfile is the canonical
implementation of the distribution's local lanes; global `ops/` routes are
thin delegators and must never reimplement their commands.

## Catalogue checks

Extend the existing validator and its focused tests to reject:

1. invalid schema/version, a directory/ID mismatch, a missing README,
   Justfile, safe default, declared command, or declared skill;
2. unowned or multiply-owned files beneath `ops/`, overlapping generated and
   authored claims, unknown/cyclic capability requirements, or invalid active
   provider selection;
3. a package operation that refers to a nonexistent local package Justfile or
   recipe, or exposes a command without an owned manifest declaration;
4. duplicated aggregate membership stored outside manifests. Aggregate `check`
   and `test` lanes are assembled from each capability's declared command;
5. product-source imports from `ops/`, package shipment of `ops/`, and
   operations scripts reaching into a peer capability's private `bin/` or
   `tests/` subtree instead of its declared local Just entry point; and
6. an unsafe router: `just ops`, `just ops <capability>`, and `just ops list`
   must show discovery data, not run a mutation or resolve an invalid path.

The validator may read product manifests and local package Justfiles to check
delegation, but it does not claim or write product source. Product package
tests remain owned by the package itself.

## Just topology

```text
root justfile
  -> ops/justfile                      # only discover/delegate/aggregate
      -> ops/<operation>/justfile      # owns operation command semantics
          -> packages/<name>/justfile  # owns distribution-local build/test
          -> capabilities/<name>/justfile
```

Root aliases such as `just check`, `just test`, and `just validate` remain
shortcuts to manifest-derived aggregate routes. The root router is not the
canonical home of a lane. All routes set or derive the repository root rather
than assuming the caller's current directory, and positional arguments pass
through unchanged so `--output json` remains usable.

## Completion evidence

- `just`, `just ops`, `just ops list`, and `just ops <capability>` are safe,
  discoverable menus; no discovery route attempts to run an undeclared
  capability directory.
- `just validate`, `just check`, and `just test` delegate through `ops/` and
  the validator proves their composition comes from manifests.
- Every new package/provider has a local Justfile and its metadata is visible
  through the package operations capability without duplicating the recipe.
- `just ops control validate`, its operation-focused tests, package operation
  tests, and full workspace gates pass from both the repository root and a
  subdirectory.
