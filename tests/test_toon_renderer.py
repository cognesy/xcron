from __future__ import annotations

from libs.services.toon_renderer import normalize_for_toon, render_toon


def test_render_toon_encodes_root_object_with_bool_and_null() -> None:
    payload = {
        "kind": "validate",
        "valid": True,
        "manifest_hash": None,
    }

    assert render_toon(payload) == "\n".join(
        [
            "kind: validate",
            "valid: true",
            "manifest_hash: null",
        ]
    )


def test_render_toon_encodes_array_of_objects_as_tabular_output() -> None:
    payload = {
        "statuses": [
            {"kind": "ok", "id": "demo.sync", "reason": "aligned"},
            {"kind": "disabled", "id": "demo.cleanup", "reason": "disabled in desired state"},
        ]
    }

    assert render_toon(payload) == "\n".join(
        [
            "statuses[2,]{kind,id,reason}:",
            "  ok,demo.sync,aligned",
            "  disabled,demo.cleanup,disabled in desired state",
        ]
    )


def test_render_toon_preserves_empty_collections_and_tuple_normalization() -> None:
    payload = {
        "help": (),
        "details": [],
        "jobs": (
            {"id": "alpha", "enabled": True},
            {"id": "beta", "enabled": False},
        ),
    }

    assert normalize_for_toon(payload) == {
        "help": [],
        "details": [],
        "jobs": [
            {"id": "alpha", "enabled": True},
            {"id": "beta", "enabled": False},
        ],
    }
    assert render_toon(payload) == "\n".join(
        [
            "help[0]:",
            "details[0]:",
            "jobs[2,]{id,enabled}:",
            "  alpha,true",
            "  beta,false",
        ]
    )


def test_render_toon_handles_truncation_metadata_fields() -> None:
    payload = {
        "snippet": {
            "preview": "first 1000 chars...",
            "truncated": True,
            "total_chars": 1842,
            "help": "Run `xcron inspect sync_docs --full` to see complete content",
        }
    }

    assert render_toon(payload) == "\n".join(
        [
            "snippet:",
            "  preview: first 1000 chars...",
            "  truncated: true",
            "  total_chars: 1842",
            "  help: Run `xcron inspect sync_docs --full` to see complete content",
        ]
    )
