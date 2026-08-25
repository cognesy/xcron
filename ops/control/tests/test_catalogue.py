from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
from types import ModuleType


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "ops" / "control" / "bin" / "catalogue.py"


def _catalogue() -> ModuleType:
    spec = importlib.util.spec_from_file_location("xcron_ops_catalogue", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_live_catalogue_is_valid_and_has_expected_capabilities() -> None:
    catalogue = _catalogue()

    assert catalogue.validate(ROOT / "ops") == []
    assert [capability.identifier for capability in catalogue.discover(ROOT / "ops")] == [
        "assurance",
        "cli",
        "control",
        "distribution",
        "quality",
        "skills",
        "workflow",
    ]


def test_aggregate_lanes_are_declared_by_capabilities() -> None:
    catalogue = _catalogue()

    assert set(catalogue._steps(ROOT / "ops", "check")) == {
        ("cli", "contract"),
        ("control", "validate"),
        ("quality", "imports"),
        ("skills", "check"),
    }
    assert catalogue._steps(ROOT / "ops", "test") == [("quality", "core")]


def test_capability_defaults_and_root_router_are_parseable() -> None:
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

    for capability in catalogue.discover(ROOT / "ops"):
        routed = subprocess.run(
            ["just", "--dry-run", "ops", capability.identifier],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert routed.returncode == 0, routed.stderr
        assert f"ops/{capability.identifier}/justfile" in f"{routed.stdout}{routed.stderr}"


def test_skill_discovery_omits_the_legacy_placeholder() -> None:
    completed = subprocess.run(
        ["uv", "run", "python", "ops/skills/bin/list_skills.py", "--check"],
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
