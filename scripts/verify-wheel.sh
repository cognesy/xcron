#!/usr/bin/env sh
# Verify the built distribution, not the checkout.
#
# Everything this catches is invisible from a source tree: a package missing
# from `packages`, a resource that was never declared, a `py.typed` that does
# not ship, a channel dependency that leaked into the library half. The
# checkout has all of those files on disk regardless.
#
# Two environments, because the split is the point. The first installs the
# plain wheel and must not have a terminal renderer anywhere in it; the second
# installs `xcron[cli]` and must be able to run the console script.
#
# Not part of `verify-core.sh`: this builds, resolves, and downloads, including
# xcfg over git. Run it before a release or after touching `pyproject.toml`.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

cd "$ROOT"

echo "==> building"
rm -rf build dist
uv build --wheel >"$WORK/build.log" 2>&1 || { cat "$WORK/build.log"; exit 1; }
WHEEL=$(ls dist/*.whl)
echo "    $WHEEL"

echo "==> library-only install"
uv venv --quiet "$WORK/lib"
VIRTUAL_ENV="$WORK/lib" uv pip install --quiet "$WHEEL"
VIRTUAL_ENV="$WORK/lib" uv run --no-project python - "$WHEEL" <<'PY'
import importlib.resources as resources
import sys
from pathlib import Path

import xcron_libs
from xcron_libs.sdk.client import Xcron

# PEP 561: without this marker every embedder's type checker treats the
# installed package as untyped, no matter how annotated the source is.
for package in ("xcron_libs", "xcron_cli"):
    assert resources.files(package).joinpath("py.typed").is_file(), package

# Packaged data ships inside the module that reads it.
for package, name in (
    ("xcron_libs.capabilities.manifest.resources.schemas", "schedules.schema.yaml"),
    ("xcron_libs.configuration.resources.config", "config.default.yaml"),
    ("xcron_libs.shared.resources.logging", None),
):
    entries = list(resources.files(package).iterdir())
    assert entries, package
    if name is not None:
        assert any(entry.name == name for entry in entries), (package, name)

# The library half is embeddable: importing the SDK must not reach a renderer,
# and the renderers must not even be installed.
for forbidden in ("typer", "rich", "toon"):
    assert forbidden not in sys.modules, forbidden
    try:
        __import__(forbidden)
    except ImportError:
        continue
    raise AssertionError(f"{forbidden} is installed in a library-only environment")

# Packages that were deleted must not be resurrected by a stale build tree.
for gone in ("xcron_libs.actions", "xcron_libs.services", "xcron_libs.infra", "xcron_resources"):
    try:
        __import__(gone)
    except ImportError:
        continue
    raise AssertionError(f"{gone} still ships in the wheel")

print("    imports, resources, and markers OK; no channel dependency present")
PY

echo "==> cli install"
uv venv --quiet "$WORK/cli"
VIRTUAL_ENV="$WORK/cli" uv pip install --quiet "$WHEEL[cli]"
"$WORK/cli/bin/xcron" --version >/dev/null
"$WORK/cli/bin/xcron" --help >/dev/null
"$WORK/cli/bin/xcron" jobs --help >/dev/null
echo "    console script runs"

echo "OK"
