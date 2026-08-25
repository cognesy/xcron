from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
from types import ModuleType

import yaml


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "ops" / "control" / "bin" / "catalogue.py"
PACKAGES_SCRIPT = ROOT / "ops" / "packages" / "bin" / "packages.py"


def _catalogue() -> ModuleType:
    spec = importlib.util.spec_from_file_location("xcron_ops_catalogue", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _packages() -> ModuleType:
    spec = importlib.util.spec_from_file_location("xcron_ops_packages", PACKAGES_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _copied_ops(tmp_path: Path) -> Path:
    copied = tmp_path / "ops"
    shutil.copytree(ROOT / "ops", copied)
    return copied


def _load_yaml(path: Path) -> dict[str, object]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _write_yaml(path: Path, value: dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def test_live_catalogue_is_valid_and_has_expected_capabilities() -> None:
    catalogue = _catalogue()

    assert catalogue.validate(ROOT / "ops") == []
    assert [capability.identifier for capability in catalogue.discover(ROOT / "ops")] == [
        "assurance",
        "cli",
        "control",
        "distribution",
        "packages",
        "quality",
        "skills",
        "version",
        "workflow",
    ]


def test_aggregate_lanes_are_declared_by_capabilities() -> None:
    catalogue = _catalogue()

    assert set(catalogue._steps(ROOT / "ops", "check")) == {
        ("cli", "contract"),
        ("control", "validate"),
        ("quality", "architecture"),
        ("skills", "check"),
        ("version", "check"),
    }
    assert catalogue._steps(ROOT / "ops", "test") == [("quality", "core")]


def test_capability_defaults_and_root_router_are_safe() -> None:
    catalogue = _catalogue()
    for capability in catalogue.discover(ROOT / "ops"):
        completed = subprocess.run(
            ["just", "--justfile", str(capability.root / "justfile"), "--dry-run", "default"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr

    for route, expected in (([], "quality"), (["list"], "quality"), (["quality"], "core")):
        routed = subprocess.run(
            ["just", "ops", *route],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert routed.returncode == 0, routed.stderr
        assert expected in routed.stdout

    subdirectory = ROOT / "docs"
    routed = subprocess.run(
        ["just", "--justfile", str(ROOT / "justfile"), "ops", "list"],
        cwd=subdirectory,
        capture_output=True,
        text=True,
        check=False,
    )
    assert routed.returncode == 0, routed.stderr
    assert "packages" in routed.stdout

    unknown = subprocess.run(
        ["just", "ops", "not-a-capability"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert unknown.returncode == 2
    assert "unknown operations capability" in unknown.stderr


def test_validator_reports_catalogue_contract_drift(tmp_path: Path) -> None:
    catalogue = _catalogue()

    unowned = _copied_ops(tmp_path)
    (unowned / "unowned.txt").write_text("orphan\n", encoding="utf-8")
    assert any("expected exactly one owner" in item.message for item in catalogue.validate(unowned))

    wrong_provider = _copied_ops(tmp_path / "provider")
    index = _load_yaml(wrong_provider / "ops.yaml")
    active = index["active"]
    assert isinstance(active, dict)
    active["package-workspace"] = "quality"
    _write_yaml(wrong_provider / "ops.yaml", index)
    assert any("does not provide" in item.message for item in catalogue.validate(wrong_provider))

    cycle = _copied_ops(tmp_path / "cycle")
    quality = _load_yaml(cycle / "quality" / "capability.yaml")
    requires = quality["requires"]
    assert isinstance(requires, dict)
    requires["capabilities"] = ["assurance"]
    _write_yaml(cycle / "quality" / "capability.yaml", quality)
    assert any(item.rule == "dependencies" and "cycle:" in item.message for item in catalogue.validate(cycle))

    missing_default = _copied_ops(tmp_path / "default")
    (missing_default / "quality" / "justfile").write_text("imports:\n    @true\n", encoding="utf-8")
    diagnostics = catalogue.validate(missing_default)
    assert any("safe default" in item.message for item in diagnostics)
    assert any("declared command" in item.message for item in diagnostics)

    missing_skill = _copied_ops(tmp_path / "skill")
    (missing_skill / "control" / "skills" / "xcron-repository-operations" / "SKILL.md").unlink()
    assert any("missing declared skill" in item.message for item in catalogue.validate(missing_skill))

    peer_boundary = _copied_ops(tmp_path / "peer")
    (peer_boundary / "quality" / "bin").mkdir()
    private_path = "/".join(("ops", "skills", "bin", "list_skills.py"))
    (peer_boundary / "quality" / "bin" / "probe.py").write_text(
        f"SOURCE = {private_path!r}\n",
        encoding="utf-8",
    )
    assert any(item.rule == "peer-boundary" for item in catalogue.validate(peer_boundary))

    product_boundary = _copied_ops(tmp_path / "product")
    product_source = tmp_path / "product" / "src" / "xcron"
    product_source.mkdir(parents=True)
    (product_source / "forbidden.py").write_text("import ops\n", encoding="utf-8")
    assert any(item.rule == "product-boundary" for item in catalogue.validate(product_boundary))


def test_package_workspace_contract_requires_local_routes(tmp_path: Path) -> None:
    packages = _packages()
    package = tmp_path / "packages" / "sample"
    package.mkdir(parents=True)
    (package / "pyproject.toml").write_text(
        "[project]\nname = 'xcron-sample'\nversion = '0.0.0'\n",
        encoding="utf-8",
    )
    (package / "capability.toml").write_text(
        "[package]\nkind = 'example'\n\n[operations]\njustfile = 'justfile'\n"
        "required_recipes = ['default', 'list', 'doctor', 'check', 'test', 'build']\n",
        encoding="utf-8",
    )
    (package / "justfile").write_text(
        "default:\n    @just --list\n\nlist:\n    @true\n\ncheck:\n    @true\n\ntest:\n    @true\n\nbuild:\n    @true\n",
        encoding="utf-8",
    )

    distributions, diagnostics = packages.discover(tmp_path)

    assert distributions == []
    assert [item.message for item in diagnostics] == ["missing local recipes: doctor"]


def test_skill_discovery_omits_the_legacy_placeholder() -> None:
    completed = subprocess.run(
        ["just", "ops", "skills", "list"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "resources/skills/admin-xcron/SKILL.md",
        "resources/skills/use-xcron/SKILL.md",
    ]
