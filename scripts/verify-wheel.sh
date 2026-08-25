#!/usr/bin/env sh
# Prove the publishable xcron package graph from built wheels, never checkout
# imports. The root distribution is an aggregate provider set during the staged
# migration; every capability wheel remains independently installable.
#
# Usage: ./scripts/verify-wheel.sh [all|packages|aggregate|lean|alternate|cli]
set -eu

LANE=${1:-all}
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
WHEELS="$WORK/wheels"

case "$LANE" in
    all|packages|aggregate|lean|alternate|cli) ;;
    *)
        echo "usage: $0 [all|packages|aggregate|lean|alternate|cli]" >&2
        exit 2
        ;;
esac

cd "$ROOT"
RELEASE_VERSION=$(uv run python ops/version/bin/version.py value)
echo "==> building every workspace wheel"
uv build --all-packages --wheel --out-dir "$WHEELS" --clear >"$WORK/build.log" 2>&1 || {
    cat "$WORK/build.log"
    exit 1
}

ROOT_WHEEL="$WHEELS/xcron-$RELEASE_VERSION-py3-none-any.whl"
KERNEL_WHEEL="$WHEELS/xcron_kernel-$RELEASE_VERSION-py3-none-any.whl"
CONTRACTS_WHEEL="$WHEELS/xcron_contracts-$RELEASE_VERSION-py3-none-any.whl"
SDK_WHEEL="$WHEELS/xcron_sdk-$RELEASE_VERSION-py3-none-any.whl"
ALTERNATE_WHEEL="$WHEELS/xcron_capability_metrics_test-$RELEASE_VERSION-py3-none-any.whl"
for wheel in "$ROOT_WHEEL" "$KERNEL_WHEEL" "$CONTRACTS_WHEEL" "$SDK_WHEEL" "$ALTERNATE_WHEEL"; do
    test -f "$wheel" || { echo "missing built wheel: $wheel" >&2; exit 1; }
done

# Run probes outside the checkout so Python's implicit current-directory import
# path cannot turn a source-tree success into a false installed-wheel success.
cd "$WORK"

verify_wheel_contents() {
    echo "==> wheel inventory and package ownership"
    uv run --no-project python - "$WHEELS" <<'PY'
from pathlib import Path
import sys
import zipfile

wheels = Path(sys.argv[1])
expected_assets = {
    "xcron_capability_manifest_yaml": "xcron/capabilities/manifest_yaml/resources/schemas/schedules.schema.yaml",
    "xcron_capability_observability_structlog": "xcron/capabilities/observability_structlog/resources/logging/default.yaml",
    "xcron_capability_settings_xcfg": "xcron/capabilities/settings_xcfg/resources/config/config.default.yaml",
    "xcron_capability_workspace_local": "xcron/capabilities/workspace_local/resources/starter-manifest.yaml",
    "xcron_cli": "xcron_cli/resources/help/root.md",
    "xcron_kernel": "xcron/kernel/resources/kernel-api.txt",
}
provider_modules = {
    "xcron_capability_agent_hooks_local": "agent_hooks_local",
    "xcron_capability_jobs_manifest": "jobs_manifest",
    "xcron_capability_logs_local": "logs_local",
    "xcron_capability_manifest_yaml": "manifest_yaml",
    "xcron_capability_metrics_local": "metrics_local",
    "xcron_capability_metrics_test": "metrics_test",
    "xcron_capability_observability_structlog": "observability_structlog",
    "xcron_capability_scheduler_native": "scheduler_native",
    "xcron_capability_settings_xcfg": "settings_xcfg",
    "xcron_capability_workspace_local": "workspace_local",
}

seen = set()
for wheel in sorted(wheels.glob("*.whl")):
    normalized = wheel.name.split("-", 1)[0]
    seen.add(normalized)
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    assert not any(name.startswith("ops/") for name in names), wheel.name
    assert not any(name.startswith("tests/") for name in names), wheel.name
    if normalized in expected_assets:
        assert expected_assets[normalized] in names, (wheel.name, expected_assets[normalized])
    if normalized in provider_modules:
        module = provider_modules[normalized]
        prefix = f"xcron/capabilities/{module}/"
        assert any(name.startswith(prefix) for name in names), (wheel.name, prefix)
        siblings = {
            name.split("/", 3)[2]
            for name in names
            if name.startswith("xcron/capabilities/") and len(name.split("/")) > 3
        }
        assert siblings <= {module}, (wheel.name, siblings)

assert set(expected_assets) <= seen
assert set(provider_modules) <= seen
print("    every wheel is free of ops/tests; providers own only their capability and declared assets")
PY
}

verify_individual_providers() {
    echo "==> independently installing provider wheels with declared closure"
    while read -r distribution module; do
        test -n "$distribution" || continue
        environment="$WORK/provider-$module"
        uv venv --quiet "$environment"
        if test "$distribution" = "xcron-capability-settings-xcfg"; then
            VIRTUAL_ENV="$environment" uv pip install --quiet --find-links "$WHEELS" \
                "$distribution==$RELEASE_VERSION" "xcfg @ git+https://github.com/cognesy/xcfg@v0.5.0"
        else
            VIRTUAL_ENV="$environment" uv pip install --quiet --find-links "$WHEELS" "$distribution==$RELEASE_VERSION"
        fi
        VIRTUAL_ENV="$environment" uv run --no-project python - "$distribution" "$module" <<'PY'
from importlib.metadata import distribution
import sys

name, module = sys.argv[1:]
installed = distribution(name)
files = {str(path) for path in installed.files or ()}
prefix = f"xcron/capabilities/{module}/"
assert any(path.startswith(prefix) for path in files), (name, prefix)
siblings = {
    path.split("/", 3)[2]
    for path in files
    if path.startswith("xcron/capabilities/") and len(path.split("/")) > 3
}
assert siblings <= {module}, (name, siblings)
assert installed.entry_points.select(group="xcron.capabilities"), name
PY
    done <<'EOF'
xcron-capability-agent-hooks-local agent_hooks_local
xcron-capability-jobs-manifest jobs_manifest
xcron-capability-logs-local logs_local
xcron-capability-manifest-yaml manifest_yaml
xcron-capability-metrics-local metrics_local
xcron-capability-metrics-test metrics_test
xcron-capability-observability-structlog observability_structlog
xcron-capability-scheduler-native scheduler_native
xcron-capability-settings-xcfg settings_xcfg
xcron-capability-workspace-local workspace_local
EOF
    echo "    every provider installs from its own wheel plus declared dependencies"
}

verify_aggregate() {
    echo "==> aggregate library install"
    environment="$WORK/aggregate"
    uv venv --quiet "$environment"
    VIRTUAL_ENV="$environment" uv pip install --quiet --find-links "$WHEELS" \
        "$ROOT_WHEEL" "xcfg @ git+https://github.com/cognesy/xcfg@v0.5.0"
    VIRTUAL_ENV="$environment" uv run --no-project python - <<'PY'
import importlib.resources as resources
import sys

from xcron.sdk import Xcron

with Xcron.open_unscoped() as client:
    ids = set(client.capabilities.ids())
assert ids == {
    "workspace:local",
    "settings:xcfg",
    "observability:structlog",
    "manifest:yaml",
    "scheduler:native",
    "jobs:manifest",
    "logs:local",
    "metrics:local",
    "agent-hooks:local",
}, ids
assert resources.files("xcron.capabilities.manifest_yaml.resources.schemas").joinpath(
    "schedules.schema.yaml"
).is_file()
for forbidden in ("typer", "rich", "toon", "xcron_cli"):
    assert forbidden not in sys.modules, forbidden
    try:
        __import__(forbidden)
    except ImportError:
        continue
    raise AssertionError(f"{forbidden} leaked into the aggregate library install")
print("    default SDK/provider set is present; no terminal channel dependency leaked")
PY
}

verify_lean() {
    echo "==> lean kernel/contracts/SDK install and typed registry failures"
    environment="$WORK/lean"
    uv venv --quiet "$environment"
    VIRTUAL_ENV="$environment" uv pip install --quiet --find-links "$WHEELS" \
        "$KERNEL_WHEEL" "$CONTRACTS_WHEEL" "$SDK_WHEEL"
    VIRTUAL_ENV="$environment" uv run --no-project python - <<'PY'
from xcron.kernel import (
    Capability,
    CapabilityCollisionError,
    CapabilityCycleError,
    CapabilityDescriptor,
    CapabilityIncompatibleError,
    CapabilityMalformedError,
    CapabilityRegistration,
    CapabilityRegistry,
    CapabilityRequirement,
    CapabilityUnavailableError,
)
from xcron.sdk import Xcron


def capability(name, implementation="local", *, requires=(), kernel_api=">=1,<2"):
    return Capability(
        CapabilityDescriptor(
            capability=name,
            implementation=implementation,
            version="1.0.0",
            kernel_api=kernel_api,
            requires=requires,
        ),
        lambda host: CapabilityRegistration(),
    )


def expects(error_type, operation):
    try:
        operation()
    except error_type:
        return
    raise AssertionError(f"expected {error_type.__name__}")


empty = CapabilityRegistry(())
with Xcron.open_unscoped(capability_registry=empty) as client:
    assert client.capabilities.ids() == ()
    expects(CapabilityUnavailableError, lambda: client.jobs)
expects(CapabilityUnavailableError, lambda: empty.select("absent"))
expects(CapabilityCollisionError, lambda: CapabilityRegistry((capability("same"), capability("same"))))
expects(CapabilityMalformedError, lambda: CapabilityRegistry((capability("bad_name"),)))
expects(CapabilityIncompatibleError, lambda: CapabilityRegistry((capability("wrong", kernel_api=">=2"),)))
expects(
    CapabilityCycleError,
    lambda: CapabilityRegistry(
        (
            capability("left", requires=(CapabilityRequirement("right"),)),
            capability("right", requires=(CapabilityRequirement("left"),)),
        )
    ).snapshot(),
)
for forbidden in ("typer", "rich", "toon", "xcron_cli", "xcron.capabilities"):
    try:
        __import__(forbidden)
    except ImportError:
        continue
    raise AssertionError(f"{forbidden} leaked into the lean SDK install")
print("    lean SDK is usable and unavailable/malformed/incompatible/cyclic providers fail typed")
PY
}

verify_alternate() {
    echo "==> explicit alternate provider selection"
    environment="$WORK/alternate"
    uv venv --quiet "$environment"
    VIRTUAL_ENV="$environment" uv pip install --quiet --find-links "$WHEELS" \
        "$ROOT_WHEEL" "$ALTERNATE_WHEEL" "xcfg @ git+https://github.com/cognesy/xcfg@v0.5.0"
    VIRTUAL_ENV="$environment" uv run --no-project python - <<'PY'
from xcron.contracts import MetricsPort
from xcron.kernel import CapabilityAmbiguousError, CapabilitySelection
from xcron.sdk import Xcron

try:
    Xcron.open_unscoped()
except CapabilityAmbiguousError:
    pass
else:
    raise AssertionError("two installed metrics providers must require explicit selection")

with Xcron.open_unscoped(selection=CapabilitySelection(metrics="test")) as client:
    metrics = client._host.require("metrics", MetricsPort)
    assert metrics.show(client._context).path == "test://xcron/metrics"
    assert metrics.reset(client._context).previous_counters == {"alternate_provider": 1}
print("    alternate provider is selected explicitly and replaces the default metrics port")
PY
}

verify_cli() {
    echo "==> aggregate CLI extra install"
    environment="$WORK/cli"
    uv venv --quiet "$environment"
    VIRTUAL_ENV="$environment" uv pip install --quiet --find-links "$WHEELS" \
        "$ROOT_WHEEL[cli]" "xcfg @ git+https://github.com/cognesy/xcfg@v0.5.0"
    "$environment/bin/xcron" --version >/dev/null
    "$environment/bin/xcron" --help >/dev/null
    "$environment/bin/xcron" jobs --help >/dev/null
    VIRTUAL_ENV="$environment" uv run --no-project python - <<'PY'
import importlib.resources as resources

import xcron_cli
from xcron_cli.typer_app import run

assert run
assert resources.files("xcron_cli.resources.help").joinpath("root.md").is_file()
print("    console script and authored CLI assets are supplied by xcron-cli")
PY
}

case "$LANE" in
    all)
        verify_wheel_contents
        verify_individual_providers
        verify_aggregate
        verify_lean
        verify_alternate
        verify_cli
        ;;
    packages)
        verify_wheel_contents
        verify_individual_providers
        ;;
    aggregate) verify_aggregate ;;
    lean) verify_lean ;;
    alternate) verify_alternate ;;
    cli) verify_cli ;;
esac

echo "OK"
