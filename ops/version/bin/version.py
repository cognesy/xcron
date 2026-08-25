"""Own, validate, update, and package xcron's lockstep release version."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from email import message_from_bytes
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib
from typing import Callable, Iterable, Mapping
import zipfile

import yaml


ROOT = Path(__file__).resolve().parents[3]
RECORD = Path("ops/version/current.yaml")
LOCK = Path("uv.lock")
VERIFY_WHEEL_SCRIPT = Path("scripts/verify-wheel.sh")
RELEASE_WORKFLOW = Path(".github/workflows/release.yml")
STABLE_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
VERSION_ASSIGNMENT = re.compile(
    r"^(?P<prefix>[ \t]*product_version:[ \t]*)(?:\"[^\"]*\"|'[^']*'|[^ \t#\r\n]+)(?P<suffix>[ \t]*(?:#.*)?)(?P<ending>\r?\n|$)",
    re.MULTILINE,
)
INTERNAL_PIN = re.compile(
    r"(?P<quote>[\"'])(?P<name>[a-z0-9][a-z0-9._-]*)(?P<extras>\[[^\]]+\])?==(?P<version>[^\"']+)(?P=quote)"
)


class VersionError(RuntimeError):
    """Raised for an unsafe version operation."""


@dataclass(frozen=True)
class Diagnostic:
    path: Path
    message: str

    def render(self, root: Path) -> str:
        return f"{self.path.relative_to(root)}: {self.message}"


@dataclass(frozen=True)
class WorkspaceProject:
    path: Path
    name: str
    metadata: Mapping[str, object]


@dataclass(frozen=True)
class ProviderDescriptor:
    source: Path
    version_start: int
    version_end: int
    version: str


def _read_toml(path: Path) -> Mapping[str, object]:
    with path.open("rb") as source:
        value = tomllib.load(source)
    if not isinstance(value, Mapping):
        raise VersionError(f"expected TOML mapping in {path}")
    return value


def _read_record(root: Path) -> Mapping[str, object]:
    path = root / RECORD
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise VersionError(f"could not read {RECORD}: {error}") from error
    if not isinstance(loaded, Mapping):
        raise VersionError(f"{RECORD} must contain a mapping")
    return loaded


def release_version(root: Path = ROOT) -> str:
    version = _read_record(root).get("product_version")
    if not isinstance(version, str) or not STABLE_VERSION.fullmatch(version):
        raise VersionError(f"{RECORD}: product_version must be stable SemVer")
    return version


def _workspace_member_paths(root: Path) -> list[Path]:
    root_metadata = _read_toml(root / "pyproject.toml")
    tool = root_metadata.get("tool")
    uv = tool.get("uv") if isinstance(tool, Mapping) else None
    workspace = uv.get("workspace") if isinstance(uv, Mapping) else None
    patterns = workspace.get("members") if isinstance(workspace, Mapping) else None
    if not isinstance(patterns, list) or not all(isinstance(item, str) for item in patterns):
        raise VersionError("pyproject.toml: [tool.uv.workspace].members must be a string list")

    members = [root]
    for pattern in patterns:
        matched = sorted(path for path in root.glob(pattern) if path.is_dir())
        if not matched:
            raise VersionError(f"pyproject.toml: workspace member pattern {pattern!r} matches nothing")
        members.extend(matched)
    return members


def workspace_projects(root: Path = ROOT) -> list[WorkspaceProject]:
    projects: list[WorkspaceProject] = []
    names: set[str] = set()
    for directory in _workspace_member_paths(root):
        pyproject = directory / "pyproject.toml"
        if not pyproject.is_file():
            raise VersionError(f"workspace member {directory.relative_to(root)} lacks pyproject.toml")
        metadata = _read_toml(pyproject)
        project = metadata.get("project")
        name = project.get("name") if isinstance(project, Mapping) else None
        if not isinstance(name, str) or not name:
            raise VersionError(f"{pyproject.relative_to(root)}: [project].name must be a string")
        if name in names:
            raise VersionError(f"duplicate workspace distribution {name!r}")
        names.add(name)
        projects.append(WorkspaceProject(pyproject, name, metadata))
    return projects


def _table_value(metadata: Mapping[str, object], *keys: str) -> object | None:
    current: object = metadata
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _published_dependencies(metadata: Mapping[str, object]) -> Iterable[str]:
    dependencies = _table_value(metadata, "project", "dependencies")
    if isinstance(dependencies, list):
        yield from (item for item in dependencies if isinstance(item, str))
    optional = _table_value(metadata, "project", "optional-dependencies")
    if isinstance(optional, Mapping):
        for values in optional.values():
            if isinstance(values, list):
                yield from (item for item in values if isinstance(item, str))


def _internal_pins(metadata: Mapping[str, object], names: set[str]) -> list[tuple[str, str]]:
    pins: list[tuple[str, str]] = []
    for requirement in _published_dependencies(metadata):
        match = re.fullmatch(
            r"(?P<name>[a-z0-9][a-z0-9._-]*)(?:\[[^\]]+\])?==(?P<version>[^; ]+)(?:\s*;.*)?",
            requirement,
        )
        if match and match.group("name") in names:
            pins.append((match.group("name"), match.group("version")))
    return pins


def _provider_descriptors(project: WorkspaceProject, root: Path) -> list[ProviderDescriptor]:
    entries = _table_value(project.metadata, "project", "entry-points", "xcron.capabilities")
    if entries is None:
        return []
    if not isinstance(entries, Mapping):
        raise VersionError(f"{project.path.relative_to(root)}: xcron.capabilities entry points must be a mapping")

    descriptors: list[ProviderDescriptor] = []
    for entry in entries.values():
        if not isinstance(entry, str) or ":" not in entry:
            raise VersionError(f"{project.path.relative_to(root)}: invalid capability entry point {entry!r}")
        module = entry.partition(":")[0]
        source = project.path.parent / "src" / Path(*module.split(".")).with_suffix(".py")
        if not source.is_file():
            raise VersionError(f"{project.path.relative_to(root)}: entry point source {source.relative_to(root)} is missing")
        content = source.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(source))
        offsets = [0]
        for line in content.splitlines(keepends=True):
            offsets.append(offsets[-1] + len(line))
        matches: list[ProviderDescriptor] = []
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call):
                continue
            function = call.func
            is_descriptor = isinstance(function, ast.Name) and function.id == "CapabilityDescriptor"
            is_descriptor = is_descriptor or (
                isinstance(function, ast.Attribute) and function.attr == "CapabilityDescriptor"
            )
            if not is_descriptor:
                continue
            for keyword in call.keywords:
                if keyword.arg != "version" or not isinstance(keyword.value, ast.Constant):
                    continue
                value = keyword.value
                if not isinstance(value.value, str):
                    raise VersionError(f"{source.relative_to(root)}: descriptor version must be a string literal")
                if value.lineno is None or value.end_lineno is None or value.end_col_offset is None:
                    raise VersionError(f"{source.relative_to(root)}: descriptor version has no source range")
                start = offsets[value.lineno - 1] + value.col_offset
                end = offsets[value.end_lineno - 1] + value.end_col_offset
                matches.append(ProviderDescriptor(source, start, end, value.value))
        if len(matches) != 1:
            raise VersionError(
                f"{source.relative_to(root)}: expected one CapabilityDescriptor.version literal, found {len(matches)}"
            )
        descriptors.extend(matches)
    return descriptors


def _lock_versions(root: Path) -> Mapping[str, str]:
    path = root / LOCK
    try:
        metadata = _read_toml(path)
    except (OSError, tomllib.TOMLDecodeError, VersionError) as error:
        raise VersionError(f"could not read {LOCK}: {error}") from error
    packages = metadata.get("package")
    if not isinstance(packages, list):
        raise VersionError(f"{LOCK}: expected package array")
    versions: dict[str, str] = {}
    for package in packages:
        if not isinstance(package, Mapping):
            continue
        name, version = package.get("name"), package.get("version")
        if isinstance(name, str) and isinstance(version, str):
            versions[name] = version
    return versions


def _validate_record(record: Mapping[str, object]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    supported = {"schema_version", "product", "product_version", "description"}
    for key in record:
        if key not in supported:
            diagnostics.append(Diagnostic(RECORD, f"unsupported field {key!r}"))
    if record.get("schema_version") != 1:
        diagnostics.append(Diagnostic(RECORD, "schema_version must be 1"))
    if record.get("product") != "xcron":
        diagnostics.append(Diagnostic(RECORD, "product must be 'xcron'"))
    version = record.get("product_version")
    if not isinstance(version, str) or not STABLE_VERSION.fullmatch(version):
        diagnostics.append(Diagnostic(RECORD, "product_version must be literal stable SemVer"))
    if not isinstance(record.get("description"), str) or not str(record["description"]).strip():
        diagnostics.append(Diagnostic(RECORD, "description must be a non-empty string"))
    return diagnostics


def validate(root: Path = ROOT) -> list[Diagnostic]:
    """Return all local source and lockfile version-projection drift."""
    diagnostics: list[Diagnostic] = []
    try:
        record = _read_record(root)
    except VersionError as error:
        return [Diagnostic(RECORD, str(error))]
    diagnostics.extend(_validate_record(record))
    version = record.get("product_version")
    if not isinstance(version, str) or not STABLE_VERSION.fullmatch(version):
        return diagnostics

    try:
        projects = workspace_projects(root)
    except VersionError as error:
        return [*diagnostics, Diagnostic(Path("pyproject.toml"), str(error))]
    names = {project.name for project in projects}
    for project in projects:
        declared = _table_value(project.metadata, "project", "version")
        relative = project.path.relative_to(root)
        if declared != version:
            diagnostics.append(Diagnostic(relative, f"[project].version {declared!r} must equal {version!r}"))
        for name, pinned in _internal_pins(project.metadata, names):
            if pinned != version:
                diagnostics.append(
                    Diagnostic(relative, f"published internal pin {name}=={pinned} must equal {version}")
                )
        try:
            descriptors = _provider_descriptors(project, root)
        except VersionError as error:
            diagnostics.append(Diagnostic(relative, str(error)))
            continue
        for descriptor in descriptors:
            if descriptor.version != version:
                diagnostics.append(
                    Diagnostic(
                        descriptor.source.relative_to(root),
                        f"CapabilityDescriptor.version {descriptor.version!r} must equal {version!r}",
                    )
                )

    try:
        locked = _lock_versions(root)
    except VersionError as error:
        diagnostics.append(Diagnostic(LOCK, str(error)))
    else:
        for name in sorted(names):
            locked_version = locked.get(name)
            if locked_version != version:
                diagnostics.append(Diagnostic(LOCK, f"{name} is {locked_version!r}, expected {version!r}"))

    script = root / VERIFY_WHEEL_SCRIPT
    expected_lookup = "RELEASE_VERSION=$(uv run python ops/version/bin/version.py value)"
    if not script.is_file():
        diagnostics.append(Diagnostic(VERIFY_WHEEL_SCRIPT, "is missing"))
    elif expected_lookup not in script.read_text(encoding="utf-8"):
        diagnostics.append(Diagnostic(VERIFY_WHEEL_SCRIPT, "must read RELEASE_VERSION from ops/version authority"))
    workflow = root / RELEASE_WORKFLOW
    required_release_steps = (
        'tags:\n      - "v*"',
        'refs/tags/$TAG:refs/tags/$TAG',
        "taiki-e/install-action@v2",
        "just version verify-release",
        "just ops workflow ci",
        "just version package",
        "gh release create",
        "gh release upload",
    )
    if not workflow.is_file():
        diagnostics.append(Diagnostic(RELEASE_WORKFLOW, "is missing"))
    else:
        workflow_source = workflow.read_text(encoding="utf-8")
        for step in required_release_steps:
            if step not in workflow_source:
                diagnostics.append(Diagnostic(RELEASE_WORKFLOW, f"must retain release step {step!r}"))
    return diagnostics


def _replace_record_version(source: str, version: str) -> str:
    matches = list(VERSION_ASSIGNMENT.finditer(source))
    if len(matches) != 1:
        raise VersionError(f"expected exactly one product_version field, found {len(matches)}")
    match = matches[0]
    return f"{source[:match.start()]}{match['prefix']}{version}{match['suffix']}{match['ending']}{source[match.end():]}"


def _replace_project_version(source: str, version: str) -> str:
    active_table: str | None = None
    replacements = 0
    lines: list[str] = []
    for line in source.splitlines(keepends=True):
        table = re.match(r"^[ \t]*\[([^\]]+)\][ \t]*(?:#.*)?(?:\r?\n)?$", line)
        if table:
            active_table = table.group(1)
        if active_table == "project":
            match = re.match(r"^(?P<prefix>[ \t]*version[ \t]*=[ \t]*)[\"'][^\"']*[\"'](?P<suffix>[ \t]*(?:#.*)?)(?P<ending>\r?\n|$)", line)
            if match:
                line = f"{match['prefix']}\"{version}\"{match['suffix']}{match['ending']}"
                replacements += 1
        lines.append(line)
    if replacements != 1:
        raise VersionError(f"expected exactly one [project].version assignment, found {replacements}")
    return "".join(lines)


def _replace_internal_pins(source: str, names: set[str], version: str) -> str:
    def replace(match: re.Match[str]) -> str:
        if match["name"] not in names:
            return match.group(0)
        return f"{match['quote']}{match['name']}{match['extras'] or ''}=={version}{match['quote']}"

    return INTERNAL_PIN.sub(replace, source)


def _replace_descriptor_version(source: str, descriptor: ProviderDescriptor, version: str) -> str:
    original = source[descriptor.version_start : descriptor.version_end]
    if original not in {f"\"{descriptor.version}\"", f"'{descriptor.version}'"}:
        raise VersionError(f"{descriptor.source}: descriptor source range no longer contains expected literal")
    return f"{source[:descriptor.version_start]}{original[0]}{version}{original[0]}{source[descriptor.version_end:]}"


def planned_updates(root: Path, version: str) -> Mapping[Path, str]:
    """Prepare every non-lockfile projection without changing the workspace."""
    if not STABLE_VERSION.fullmatch(version):
        raise VersionError(f"version must be stable SemVer, got {version!r}")
    current = release_version(root)
    if _compare(version, current) <= 0:
        raise VersionError(f"version {version} must be greater than current {current}")
    diagnostics = validate(root)
    if diagnostics:
        rendered = "\n".join(f"  - {item.render(root)}" for item in diagnostics)
        raise VersionError(f"cannot change a drifting version:\n{rendered}")

    projects = workspace_projects(root)
    names = {project.name for project in projects}
    changes: dict[Path, str] = {}
    record_path = root / RECORD
    changes[record_path] = _replace_record_version(record_path.read_text(encoding="utf-8"), version)
    for project in projects:
        content = project.path.read_text(encoding="utf-8")
        content = _replace_project_version(content, version)
        changes[project.path] = _replace_internal_pins(content, names, version)
        for descriptor in _provider_descriptors(project, root):
            descriptor_source = changes.get(descriptor.source, descriptor.source.read_text(encoding="utf-8"))
            changes[descriptor.source] = _replace_descriptor_version(descriptor_source, descriptor, version)
    return changes


def _replace_file(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)


def _refresh_lock(root: Path) -> None:
    completed = subprocess.run(["uv", "lock"], cwd=root, text=True, capture_output=True, check=False)
    if completed.returncode:
        output = (completed.stdout + completed.stderr).strip()
        raise VersionError(f"uv lock failed:\n{output}")


def set_version(
    root: Path,
    version: str,
    *,
    lock_runner: Callable[[Path], None] = _refresh_lock,
) -> None:
    """Atomically update sources, refresh uv.lock, or restore every changed file."""
    changes = planned_updates(root, version)
    lock_path = root / LOCK
    original = {path: path.read_text(encoding="utf-8") for path in [*changes, lock_path]}
    try:
        for path, content in changes.items():
            _replace_file(path, content)
        lock_runner(root)
        diagnostics = validate(root)
        if diagnostics:
            rendered = "\n".join(f"  - {item.render(root)}" for item in diagnostics)
            raise VersionError(f"version update did not converge:\n{rendered}")
    except Exception:
        for path, content in original.items():
            _replace_file(path, content)
        raise


def _compare(left: str, right: str) -> int:
    left_parts = tuple(int(part) for part in left.split("."))
    right_parts = tuple(int(part) for part in right.split("."))
    return (left_parts > right_parts) - (left_parts < right_parts)


def next_version(root: Path, part: str) -> str:
    if part not in {"patch", "minor", "major"}:
        raise VersionError(f"next requires patch, minor, or major, got {part!r}")
    diagnostics = validate(root)
    if diagnostics:
        rendered = "\n".join(f"  - {item.render(root)}" for item in diagnostics)
        raise VersionError(f"cannot calculate next version while projections drift:\n{rendered}")
    major, minor, patch = (int(item) for item in release_version(root).split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments], text=True, capture_output=True, check=False
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise VersionError(f"git {' '.join(arguments)} failed: {detail}")
    return completed.stdout.strip()


def _remote_tags(root: Path) -> Mapping[str, str]:
    output = _git(root, "ls-remote", "--tags", "origin", "v*")
    tags: dict[str, str] = {}
    for line in output.splitlines():
        object_id, _, reference = line.partition("\t")
        if not reference.startswith("refs/tags/") or reference.endswith("^{}"):
            continue
        tag = reference.removeprefix("refs/tags/")
        if STABLE_VERSION.fullmatch(tag.removeprefix("v")):
            tags[tag] = object_id
    return tags


def verify_release(root: Path = ROOT) -> Mapping[str, object]:
    diagnostics = validate(root)
    if diagnostics:
        rendered = "\n".join(f"  - {item.render(root)}" for item in diagnostics)
        raise VersionError(f"cannot verify drifting release:\n{rendered}")
    version = release_version(root)
    tag = f"v{version}"
    if _git(root, "cat-file", "-t", f"refs/tags/{tag}") != "tag":
        raise VersionError(f"release tag {tag} must exist locally and be annotated")
    tag_commit = _git(root, "rev-parse", f"{tag}^{{commit}}")
    head = _git(root, "rev-parse", "HEAD")
    if tag_commit != head:
        raise VersionError(f"release tag {tag} points to {tag_commit}, not HEAD {head}")
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise VersionError(f"release source is not clean:\n{status}")
    local_tag_object = _git(root, "rev-parse", f"refs/tags/{tag}")
    remote = _remote_tags(root)
    remote_object = remote.get(tag)
    if remote_object != local_tag_object:
        raise VersionError(f"release tag {tag} is not pushed to origin with its local annotated tag object")
    latest = max((value.removeprefix("v") for value in remote), key=lambda item: tuple(map(int, item.split("."))))
    if _compare(version, latest) < 0:
        raise VersionError(f"release version {version} precedes highest remote stable tag v{latest}")
    return {
        "schemaVersion": 1,
        "productVersion": version,
        "tag": tag,
        "commit": head,
        "tagKind": "annotated",
        "sourceClean": True,
        "remoteTag": tag,
        "highestRemoteStableTag": f"v{latest}",
    }


def sync(root: Path = ROOT) -> None:
    _git(root, "fetch", "--tags", "--prune", "origin")


def _wheel_metadata(wheel: Path) -> tuple[str, str]:
    with zipfile.ZipFile(wheel) as archive:
        metadata_paths = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_paths) != 1:
            raise VersionError(f"{wheel.name}: expected one .dist-info/METADATA file")
        metadata = message_from_bytes(archive.read(metadata_paths[0]))
    name, version = metadata.get("Name"), metadata.get("Version")
    if not name or not version:
        raise VersionError(f"{wheel.name}: METADATA lacks Name or Version")
    return name, version


def _safe_output_directory(root: Path, requested: str | None, version: str) -> Path:
    if requested is None:
        return root / "dist" / f"xcron-{version}"
    destination = Path(requested).expanduser().resolve()
    try:
        destination.relative_to(root.resolve())
    except ValueError:
        return destination
    raise VersionError("package output must be outside the repository; use the default dist/ location or an external path")


def package_release(root: Path = ROOT, requested_output: str | None = None) -> Mapping[str, object]:
    diagnostics = validate(root)
    if diagnostics:
        rendered = "\n".join(f"  - {item.render(root)}" for item in diagnostics)
        raise VersionError(f"cannot package drifting release:\n{rendered}")
    version = release_version(root)
    destination = _safe_output_directory(root, requested_output, version)
    destination.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["uv", "build", "--all-packages", "--wheel", "--out-dir", str(destination), "--clear"],
        cwd=root,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise VersionError("uv build failed")
    expected = {project.name for project in workspace_projects(root)}
    wheels: list[dict[str, str]] = []
    found: set[str] = set()
    for wheel in sorted(destination.glob("*.whl")):
        name, wheel_version = _wheel_metadata(wheel)
        if wheel_version != version:
            raise VersionError(f"{wheel.name}: metadata version {wheel_version!r} must equal {version!r}")
        if name in found:
            raise VersionError(f"{wheel.name}: duplicate wheel for {name}")
        found.add(name)
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        wheels.append({"distribution": name, "filename": wheel.name, "sha256": digest})
    if found != expected:
        raise VersionError(f"wheel bundle mismatch: expected {sorted(expected)}, found {sorted(found)}")
    manifest: Mapping[str, object] = {
        "schemaVersion": 1,
        "product": "xcron",
        "productVersion": version,
        "wheels": wheels,
    }
    manifest_path = destination / "release-manifest.json"
    _replace_file(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    checksums = "".join(f"{item['sha256']}  {item['filename']}\n" for item in wheels)
    _replace_file(destination / "SHA256SUMS.txt", checksums)
    return {**manifest, "outputDirectory": str(destination)}


def _show(root: Path) -> Mapping[str, object]:
    diagnostics = validate(root)
    version = release_version(root)
    local_tags: list[str] = []
    try:
        output = _git(root, "tag", "--list", "v*")
    except VersionError as error:
        local_tag_status: Mapping[str, object] = {"available": False, "error": str(error)}
    else:
        local_tags = sorted(
            (tag for tag in output.splitlines() if STABLE_VERSION.fullmatch(tag.removeprefix("v"))),
            key=lambda item: tuple(map(int, item.removeprefix("v").split("."))),
        )
        local_tag_status = {
            "available": True,
            "latest": local_tags[-1] if local_tags else None,
            "observation": "local only; use verify-release to query origin",
        }
    return {
        "schemaVersion": 1,
        "product": "xcron",
        "productVersion": version,
        "authority": str(RECORD),
        "workspacePackages": [project.name for project in workspace_projects(root)],
        "localTags": local_tag_status,
        "valid": not diagnostics,
        "problems": [item.render(root) for item in diagnostics],
    }


def _report_diagnostics(root: Path) -> int:
    diagnostics = validate(root)
    if diagnostics:
        print("xcron version drift:", file=sys.stderr)
        for diagnostic in diagnostics:
            print(f"  - {diagnostic.render(root)}", file=sys.stderr)
        return 1
    print(f"xcron release version {release_version(root)}: OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("show")
    subcommands.add_parser("value")
    subcommands.add_parser("check")
    next_parser = subcommands.add_parser("next")
    next_parser.add_argument("part")
    set_parser = subcommands.add_parser("set")
    set_parser.add_argument("version")
    subcommands.add_parser("sync")
    subcommands.add_parser("verify-release")
    package_parser = subcommands.add_parser("package")
    package_parser.add_argument("out_dir", nargs="?")
    parsed = parser.parse_args(argv)
    try:
        if parsed.command == "show":
            print(json.dumps(_show(ROOT), indent=2, sort_keys=True))
            return 0
        if parsed.command == "value":
            print(release_version(ROOT))
            return 0
        if parsed.command == "check":
            return _report_diagnostics(ROOT)
        if parsed.command == "next":
            print(next_version(ROOT, parsed.part))
            return 0
        if parsed.command == "set":
            previous = release_version(ROOT)
            set_version(ROOT, parsed.version)
            print(f"xcron release version: {previous} -> {parsed.version}")
            return 0
        if parsed.command == "sync":
            sync(ROOT)
            print("release tags from origin: synchronized")
            return 0
        if parsed.command == "verify-release":
            print(json.dumps(verify_release(ROOT), indent=2, sort_keys=True))
            return 0
        if parsed.command == "package":
            print(json.dumps(package_release(ROOT, parsed.out_dir), indent=2, sort_keys=True))
            return 0
    except VersionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    raise AssertionError(f"unexpected command {parsed.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
