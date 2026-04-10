from __future__ import annotations

from types import SimpleNamespace

from libs.services.cli_contracts import get_command_contract
from libs.services.cli_mappers import (
    map_apply_response,
    map_error_response,
    map_home_response,
    map_jobs_mutation_response,
    map_status_response,
)


def test_map_error_response_builds_typed_error_envelope() -> None:
    response = map_error_response(
        "project validation failed",
        details=({"field": "/project", "issue": "required"},),
        help_items=("Run `xcron validate`",),
    )

    assert response.kind == "error"
    assert response.code == "runtime_error"
    assert response.details[0].field == "/project"
    assert response.help == ("Run `xcron validate`",)


def test_map_home_response_builds_typed_home_envelope() -> None:
    contract = get_command_contract("home")
    result = SimpleNamespace(
        backend="cron",
        changes=(SimpleNamespace(kind=SimpleNamespace(value="create"), qualified_id="demo.sync", reason="missing"),),
        validation=SimpleNamespace(
            project_root="/tmp/project",
            manifest_path="/tmp/project/resources/schedules/default.yaml",
            normalized_manifest=SimpleNamespace(jobs=("job",)),
        ),
    )

    response = map_home_response(
        result,
        executable="/Users/test/.local/bin/xcron",
        contract=contract,
        include_plan_changes=True,
    )

    assert response.bin == "/Users/test/.local/bin/xcron"
    assert response.jobs.total == 1
    assert response.plan_summary[0].kind == "create"
    assert response.plan_changes[0].id == "demo.sync"


def test_map_apply_response_reports_noop_when_only_noop_changes_exist() -> None:
    contract = get_command_contract("apply")
    result = SimpleNamespace(
        backend="cron",
        plan_result=SimpleNamespace(
            changes=(SimpleNamespace(kind=SimpleNamespace(value="noop")),),
            validation=SimpleNamespace(
                manifest_path="/tmp/project/resources/schedules/default.yaml",
                normalized_manifest=SimpleNamespace(project_id="demo-app"),
            ),
        ),
    )

    response = map_apply_response(result, contract=contract)

    assert response.kind == "apply"
    assert response.outcome == "noop"
    assert response.count == 0


def test_map_status_response_builds_typed_rows() -> None:
    contract = get_command_contract("status")
    result = SimpleNamespace(
        backend="cron",
        statuses=(
            SimpleNamespace(kind=SimpleNamespace(value="ok"), qualified_id="demo.sync", reason="aligned"),
            SimpleNamespace(kind=SimpleNamespace(value="disabled"), qualified_id="demo.pause", reason="disabled in desired state"),
        ),
    )

    response = map_status_response(result, contract=contract)

    assert response.count == "2 of 2"
    assert response.statuses[0].kind == "ok"
    assert response.statuses[1].id == "demo.pause"


def test_map_jobs_mutation_response_uses_change_signal() -> None:
    contract = get_command_contract("jobs.enable")
    result = SimpleNamespace(
        changed=False,
        manifest_path="/tmp/project/resources/schedules/default.yaml",
        job=SimpleNamespace(qualified_id="demo.sync"),
        removed_job_identifier=None,
    )

    response = map_jobs_mutation_response(
        result,
        contract=contract,
        changed_outcome="enabled",
    )

    assert response.kind == "jobs.enable"
    assert response.target == "demo.sync"
    assert response.outcome == "noop"
