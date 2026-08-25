"""Installed best-effort local metrics provider and outcome-sink adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping

from xcron.contracts import (
    InvocationContext,
    MetricsPort,
    MetricsResetResult,
    MetricsResult,
    OutcomeSink,
    WorkspacePort,
)
from xcron.kernel import (
    Capability,
    CapabilityDescriptor,
    CapabilityProvides,
    CapabilityRegistration,
    CapabilityRequirement,
)


class LocalMetricsStore:
    """A deliberately small store that degrades to an empty in-memory value."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def show(self) -> dict[str, Any]:
        return {**self._read(), "path": str(self.path)}

    def reset(self) -> dict[str, Any]:
        previous = self._read()
        payload = _empty_payload()
        try:
            self._write(payload)
        except Exception:
            pass
        return {**payload, "path": str(self.path), "previous_counters": previous.get("counters", {})}

    def increment(self, counter: str, amount: int = 1) -> None:
        try:
            payload = self._read()
            counters = payload["counters"]
            counters[counter] = int(counters.get(counter, 0)) + amount
            payload["updated_at"] = _timestamp()
            self._write(payload)
        except Exception:
            return None

    def _read(self) -> dict[str, Any]:
        try:
            if not self.path.is_file():
                return _empty_payload()
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return _empty_payload()
        if not isinstance(payload, dict):
            return _empty_payload()
        counters = payload.get("counters")
        return {
            "version": int(payload.get("version", 1)),
            "created_at": str(payload.get("created_at", _timestamp())),
            "updated_at": str(payload.get("updated_at", payload.get("created_at", _timestamp()))),
            "counters": dict(counters) if isinstance(counters, Mapping) else {},
        }

    def _write(self, payload: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.path)


class MetricsOutcomeSink:
    """Context-bound outcome sink; it cannot turn a store outage into failure."""

    def __init__(self, store: LocalMetricsStore) -> None:
        self._store = store

    def record(self, counter: str, amount: int = 1) -> None:
        self._store.increment(counter, amount)


class LocalMetricsProvider:
    """Expose metrics reads plus the aggregate host's optional outcome sink."""

    def __init__(self, workspace: WorkspacePort) -> None:
        self._workspace = workspace

    def show(self, context: InvocationContext) -> MetricsResult:
        del context
        return _metrics_result(self._store().show())

    def reset(self, context: InvocationContext) -> MetricsResetResult:
        del context
        payload = self._store().reset()
        return MetricsResetResult(
            **_metrics_values(payload),
            previous_counters=_counters(payload.get("previous_counters")),
        )

    def outcome_sink(self, context: InvocationContext) -> OutcomeSink:
        del context
        return MetricsOutcomeSink(self._store())

    def _store(self) -> LocalMetricsStore:
        # `home()` is the workspace capability's existing XCRON_HOME boundary;
        # a project invocation never changes the machine-wide metrics location.
        return LocalMetricsStore(self._workspace.home().metrics_path)


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _empty_payload() -> dict[str, Any]:
    now = _timestamp()
    return {"version": 1, "created_at": now, "updated_at": now, "counters": {}}


def _metrics_result(payload: Mapping[str, Any]) -> MetricsResult:
    return MetricsResult(**_metrics_values(payload))


def _metrics_values(payload: Mapping[str, Any]) -> dict[str, object]:
    return {
        "path": str(payload["path"]),
        "version": int(payload["version"]),
        "created_at": str(payload["created_at"]),
        "updated_at": str(payload["updated_at"]),
        "counters": _counters(payload.get("counters")),
    }


def _counters(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    try:
        return {str(key): int(count) for key, count in value.items()}
    except (TypeError, ValueError):
        return {}


DESCRIPTOR = CapabilityDescriptor(
    capability="metrics",
    implementation="local",
    version="0.1.3",
    kernel_api=">=1,<2",
    requires=(CapabilityRequirement("workspace"),),
    provides=CapabilityProvides(ports=("metrics",), cli_paths=("metrics",)),
)


def _build(host) -> CapabilityRegistration:
    return CapabilityRegistration(
        ports={"metrics": LocalMetricsProvider(host.require("workspace", WorkspacePort))},
        cli_paths={"metrics": None},
    )


CAPABILITY = Capability(DESCRIPTOR, _build)

assert isinstance(LocalMetricsProvider.__new__(LocalMetricsProvider), MetricsPort)
