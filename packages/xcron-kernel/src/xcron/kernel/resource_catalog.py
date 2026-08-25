"""Safe access to resources packaged by one capability distribution."""

from __future__ import annotations

from importlib import resources
from pathlib import PurePosixPath

from xcron.kernel.errors import CapabilityMalformedError


class CapabilityResources:
    """Read resources without allowing callers to escape the owner package."""

    def __init__(self, package: str) -> None:
        self._package = package

    def read_text(self, relative_path: str, *, encoding: str = "utf-8") -> str:
        return self._resource(relative_path).read_text(encoding=encoding)

    def read_bytes(self, relative_path: str) -> bytes:
        return self._resource(relative_path).read_bytes()

    def _resource(self, relative_path: str):
        path = PurePosixPath(relative_path)
        if not relative_path or path.is_absolute() or ".." in path.parts:
            raise CapabilityMalformedError(
                f"Resource path {relative_path!r} escapes capability package {self._package!r}.",
                "Use a non-empty package-relative resource path.",
            )
        resource = resources.files(self._package).joinpath(*path.parts)
        if not resource.is_file():
            raise CapabilityMalformedError(
                f"Resource {relative_path!r} is not packaged by {self._package!r}.",
                "Declare and include the resource in its owning capability distribution.",
            )
        return resource
