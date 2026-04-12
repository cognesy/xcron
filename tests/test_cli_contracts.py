from __future__ import annotations

from libs.services.cli_contracts import get_command_contract


def test_cli_contract_registry_exposes_representative_command_metadata() -> None:
    home = get_command_contract("home")
    inspect = get_command_contract("inspect")
    jobs_list = get_command_contract("jobs.list")
    metrics = get_command_contract("metrics.show")

    assert "plan_summary" in home.allowed_fields

    assert inspect.truncation_limit == 1000
    assert "desired" in inspect.allowed_fields
    assert "deployed" in inspect.allowed_fields
    assert inspect.nested_fields["desired"]

    assert jobs_list.list_key == "jobs"
    assert jobs_list.list_row_fields == ("job_id", "enabled", "schedule", "command")
    assert "counters" in metrics.allowed_fields
