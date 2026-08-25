# Release versioning

`ops/version/current.yaml` is the single authority for xcron's stable release
version. Version 1 deliberately releases the root aggregate, every workspace
library, and every built-in provider in lockstep. A provider descriptor is
therefore part of the release projection, not an independent compatibility
number.

The capability validates all of these projections:

- each workspace `[project].version`;
- published exact pins between workspace distributions;
- each built-in provider's `CapabilityDescriptor.version`;
- the editable workspace entries in `uv.lock`;
- the wheel-verification script's lookup of the authority record.

It avoids the two common release-ledger hazards: `set` does not make a safety
claim from stale local tags, and `verify-release` queries `origin` directly
before it accepts a pushed annotated tag.

## Inspect and change

```sh
just version show
just version check
just version next patch
just version set 0.1.1
just version check
```

`set` is transactional: it stages all source projections, runs `uv lock`, then
re-validates the result. If locking or validation fails, it restores the prior
files. It does not commit, tag, push, or publish.

`sync` is an optional local convenience for inspecting tags. It is not a
release-safety precondition because a local tag cache can be stale.

## Create a GitHub Release

Run the full local proof first, commit the version change, then create and push
an annotated tag that exactly names the version:

```sh
just ops workflow ci
git add ops/version/current.yaml pyproject.toml packages capabilities uv.lock
git commit -m "Release v0.1.1"
git push origin main
git tag -a v0.1.1 -m "xcron v0.1.1"
git push origin v0.1.1
just version verify-release
```

The pushed `v*` tag starts `.github/workflows/release.yml`. The workflow checks
the tag, source, metadata, lockfile, and clean-install wheel matrix; creates a
GitHub Release; and attaches all wheels, `SHA256SUMS.txt`, and
`release-manifest.json`. It intentionally does not publish to PyPI.

## Package locally

```sh
just version package
just version package /tmp/xcron-release
```

The default bundle location is `dist/xcron-<version>/`. A supplied destination
must be outside the repository; this prevents a convenience command from
clearing source-controlled paths. The bundle contains one wheel for every
workspace distribution plus a manifest whose hashes were verified against the
wheel metadata.
