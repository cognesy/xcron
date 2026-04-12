"""Tests for the tmux compact renderer."""

from __future__ import annotations

from libs.services.tmux_renderer import render_tmux


def test_render_scalar_fields() -> None:
    payload = {"backend": "cron", "count": "2 of 2"}
    result = render_tmux(payload)
    assert "backend: cron" in result
    assert "count: 2 of 2" in result


def test_render_row_list_with_alignment() -> None:
    payload = {
        "backend": "cron",
        "statuses": [
            {"kind": "ok", "id": "demo.ping_job", "reason": "aligned"},
            {"kind": "disabled", "id": "demo.paused", "reason": "disabled in desired state"},
        ],
    }
    result = render_tmux(payload)
    assert "backend: cron" in result
    assert "statuses[2]:" in result
    lines = result.splitlines()
    status_lines = [line for line in lines if line.startswith("  ")]
    assert len(status_lines) == 2
    assert "ok" in status_lines[0]
    assert "demo.ping_job" in status_lines[0]
    assert "disabled" in status_lines[1]


def test_render_empty_list() -> None:
    payload = {"statuses": []}
    result = render_tmux(payload)
    assert "statuses: -" in result


def test_render_nested_dict() -> None:
    payload = {"jobs": {"total": 3}}
    result = render_tmux(payload)
    assert "jobs: total=3" in result


def test_render_none_values() -> None:
    payload = {"backend": None}
    result = render_tmux(payload)
    assert "backend: -" in result


def test_render_boolean_values() -> None:
    payload = {"dry_run": True, "cleared": False}
    result = render_tmux(payload)
    assert "dry_run: yes" in result
    assert "cleared: no" in result


def test_render_non_dict_passthrough() -> None:
    assert render_tmux("hello") == "hello"
    assert render_tmux(42) == "42"
