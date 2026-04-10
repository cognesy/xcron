from __future__ import annotations

from libs.services.axi_presenter import build_error_payload, parse_fields_csv, select_fields, truncate_text


def test_parse_fields_csv_preserves_order_and_drops_empty_values() -> None:
    assert parse_fields_csv(" kind , id ,, reason ") == ("kind", "id", "reason")
    assert parse_fields_csv(None) == ()


def test_select_fields_uses_requested_subset_or_allowed_default() -> None:
    payload = {
        "kind": "status",
        "count": "2 of 2",
        "statuses": [],
        "help": ["Run `xcron inspect <id>`"],
    }

    assert select_fields(payload, allowed_fields=("kind", "count", "statuses"), requested_fields=("count", "kind")) == {
        "count": "2 of 2",
        "kind": "status",
    }
    assert select_fields(payload, allowed_fields=("kind", "count", "statuses")) == {
        "kind": "status",
        "count": "2 of 2",
        "statuses": [],
    }


def test_truncate_text_returns_metadata_for_large_values() -> None:
    result = truncate_text("x" * 1005, limit=1000, full_hint="Run `xcron inspect sync --full`")

    assert result == {
        "preview": "x" * 1000,
        "truncated": True,
        "total_chars": 1005,
        "help": "Run `xcron inspect sync --full`",
    }
    assert truncate_text("short", limit=1000) == "short"


def test_build_error_payload_emits_common_axi_shape() -> None:
    assert build_error_payload(
        "the following arguments are required: job_id",
        code="usage_error",
        details=({"field": "job_id", "issue": "required"},),
        help_items=("Run `xcron jobs add --help` to see usage",),
    ) == {
        "kind": "error",
        "code": "usage_error",
        "message": "the following arguments are required: job_id",
        "details": [{"field": "job_id", "issue": "required"}],
        "help": ["Run `xcron jobs add --help` to see usage"],
    }
