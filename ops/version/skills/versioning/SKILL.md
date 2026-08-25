---
name: xcron-versioning
description: Safely inspect, change, verify, package, and release lockstep xcron versions.
---

# xcron release versioning

Use this capability whenever a request changes xcron's package version or
prepares a GitHub release. The only authority is
`ops/version/current.yaml`; do not hand-edit individual package versions.

Start with:

```sh
just version show
just version check
```

For a new stable release, preview the intended component, run `set`, then
validate and prove the complete source and installed-wheel lanes:

```sh
just version next patch
just version set <major.minor.patch>
just ops workflow ci
```

`set` updates every lockstep package version, exact internal publish-time pin,
provider descriptor, and `uv.lock` transactionally. It neither commits nor
publishes.

After committing, use an annotated `v<version>` tag at `HEAD`, push it, and run
`just version verify-release`. The GitHub Actions release workflow is
tag-triggered and attaches verified wheel artifacts to a GitHub Release. It
does not publish to PyPI.
