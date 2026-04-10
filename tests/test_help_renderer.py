from __future__ import annotations

from libs.services.help_renderer import load_help_body, render_help_text


def test_load_help_body_reads_packaged_root_and_leaf_pages() -> None:
    assert "Authoritative runtime help for xcron lives under `resources/help/`." in load_help_body("root")
    assert "Create a new manifest job." in load_help_body("jobs/add")


def test_render_help_text_prefixes_authored_body_before_reference() -> None:
    rendered = render_help_text("jobs/index", "usage: xcron jobs [-h]\n\noptions:\n  -h, --help\n")

    assert "xcron jobs" in rendered
    assert "These commands edit YAML only;" in rendered
    assert "Usage" in rendered
    assert "usage: xcron jobs [-h]" in rendered
    assert "Reference" in rendered
    assert "options:" in rendered
