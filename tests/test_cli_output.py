from __future__ import annotations

import json
from pathlib import Path

import click
import pytest
import typer

from apps.cli.output import Output
from libs.services.cli_responses import (
    HomeJobsSummary,
    HomeResponse,
    InspectResponse,
    StatusResponse,
    StatusRow,
    SummaryRow,
    ValidationSummaryResponse,
)


def _make_ctx(**params: object) -> click.Context:
    root = click.Context(click.Command("xcron"))
    root.params = dict(params)
    child = click.Context(click.Command("command"), parent=root)
    child.params = {}
    return child


def test_output_uses_parent_context_options_and_local_output_override() -> None:
    out = Output(_make_ctx(output_format="toon", fields="backend", full=True), "status", local_output="json")

    assert out.fmt == "json"
    assert out.full is True
    assert out.contract.name == "status"


def test_output_render_json_uses_contract_default_fields_for_flat_payloads() -> None:
    response = ValidationSummaryResponse(
        project="/tmp/demo",
        manifest="/tmp/demo/resources/schedules/default.yaml",
        valid=True,
        jobs=2,
        manifest_hash="abc123",
        errors=0,
        warnings=1,
        warning_messages=("warn: deprecated field",),
    )

    payload = json.loads(Output(_make_ctx(output_format="json"), "validate").render(response))

    assert payload == {
        "errors": 0,
        "jobs": 2,
        "manifest": "/tmp/demo/resources/schedules/default.yaml",
        "manifest_hash": "abc123",
        "project": "/tmp/demo",
        "valid": True,
        "warnings": 1,
    }


def test_output_render_json_filters_list_row_fields_from_requested_fields() -> None:
    response = StatusResponse(
        backend="cron",
        count="2 of 2",
        statuses=(
            StatusRow(kind="ok", id="demo.sync", reason="aligned"),
            StatusRow(kind="disabled", id="demo.cleanup", reason="disabled"),
        ),
        help=("Run `xcron inspect <job-id>`",),
    )

    payload = json.loads(Output(_make_ctx(output_format="json", fields="id"), "status").render(response))

    assert payload == {
        "statuses": [
            {"id": "demo.sync"},
            {"id": "demo.cleanup"},
        ]
    }


def test_output_render_json_filters_nested_fields_and_normalizes_values() -> None:
    response = InspectResponse(
        backend="cron",
        job="demo.sync",
        status="aligned",
        desired={
            "working_dir": Path("/tmp/demo"),
            "env": (("FOO", "bar"),),
            "schedule": "cron=*/15 * * * *",
        },
        deployed={"label": "demo.sync"},
        snippets={"wrapper": Path("/tmp/demo/wrapper.sh")},
        help=("Run `xcron status`",),
    )

    payload = json.loads(
        Output(
            _make_ctx(output_format="json", fields="desired.working_dir,desired.env"),
            "inspect",
        ).render(response)
    )

    assert payload == {
        "desired": {
            "env": [["FOO", "bar"]],
            "working_dir": "/tmp/demo",
        }
    }


def test_output_render_toon_filters_collection_rows_from_requested_fields() -> None:
    response = HomeResponse(
        bin="xcron",
        description="Manage schedules",
        project="/tmp/demo",
        schedule="default",
        backend="cron",
        manifest="/tmp/demo/resources/schedules/default.yaml",
        jobs=HomeJobsSummary(total=1),
        plan_summary=(SummaryRow(kind="create", count=1),),
        help=("Run `xcron validate`",),
    )

    rendered = Output(_make_ctx(fields="count"), "home").render(response)

    assert rendered == "\n".join(
        [
            "plan_summary[1,]{count}:",
            "  1",
        ]
    )


def test_output_error_renders_structured_payload_and_raises_exit(capsys: pytest.CaptureFixture[str]) -> None:
    out = Output(_make_ctx(output_format="json"), "status")

    with pytest.raises(typer.Exit) as excinfo:
        out.error(
            "job action failed",
            code="usage_error",
            details=[{"field": "job_id", "issue": "missing"}],
            hints=["Run `xcron jobs list` to inspect available jobs"],
            exit_code=2,
        )

    payload = json.loads(capsys.readouterr().out)

    assert excinfo.value.exit_code == 2
    assert payload == {
        "code": "usage_error",
        "details": [{"field": "job_id", "issue": "missing"}],
        "help": ["Run `xcron jobs list` to inspect available jobs"],
        "kind": "error",
        "message": "job action failed",
    }
