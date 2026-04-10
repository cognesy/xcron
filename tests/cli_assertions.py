from __future__ import annotations


def assert_usage_error(output: str, *, message_fragment: str | None = None) -> None:
    assert "kind: error" in output
    assert "code: usage_error" in output
    if message_fragment is not None:
        assert message_fragment in output


def assert_mutation_output(output: str, *, kind: str, outcome: str, target: str | None = None) -> None:
    assert f"kind: {kind}" in output
    assert f"outcome: {outcome}" in output
    if target is not None:
        assert f"target: {target}" in output


def assert_list_output(output: str, *, count: str, header: str) -> None:
    assert f"count: {count}" in output
    assert header in output
