"""Pre-configured output surface for xcron CLI commands."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from typing import Any, Literal, NoReturn, cast

import typer

from apps.cli.common import selected_output_format
from libs.services import (
    CommandContract,
    ErrorDetail,
    ErrorResponse,
    PayloadConvertible,
    get_command_contract,
    parse_fields_csv,
    render_tmux,
    render_toon,
    select_fields,
    validate_requested_fields,
)

OutputFormat = Literal["json", "toon", "tmux"]


class Output:
    """Pre-configured output surface for one command invocation."""

    def __init__(
        self,
        ctx: typer.Context,
        contract_name: str,
        local_output: OutputFormat | None = None,
    ) -> None:
        self._fmt = cast(OutputFormat, selected_output_format(local_output or _shared_option(ctx, "output_format", None)))
        self._full = bool(_shared_option(ctx, "full", False))
        self._contract = get_command_contract(contract_name)

        fields_csv = _shared_option(ctx, "fields", None)
        parsed_fields = parse_fields_csv(fields_csv) if fields_csv else ()
        self._requested_fields = validate_requested_fields(self._contract, parsed_fields) if parsed_fields else ()

    @property
    def fmt(self) -> OutputFormat:
        return self._fmt

    @property
    def full(self) -> bool:
        return self._full

    @property
    def contract(self) -> CommandContract:
        return self._contract

    def print(self, response: PayloadConvertible) -> None:
        """Render one response and write it to stdout."""

        typer.echo(self.render(response))

    def render(self, response: PayloadConvertible) -> str:
        """Render one response to a string without performing I/O."""

        return self._render_payload(response.to_payload(), apply_selection=True)

    def error(
        self,
        message: str,
        *,
        code: str = "runtime_error",
        details: list[dict[str, str]] | None = None,
        hints: list[str] | None = None,
        exit_code: int = 1,
    ) -> NoReturn:
        """Render one structured error response and exit."""

        response = ErrorResponse(
            kind="error",
            code=code,
            message=message,
            details=tuple(ErrorDetail(**item) for item in (details or ())),
            help=tuple(hints or ()),
        )
        typer.echo(self._render_payload(response.to_payload(), apply_selection=False))
        raise typer.Exit(code=exit_code)

    def _render_payload(self, payload: dict[str, Any], *, apply_selection: bool) -> str:
        active_payload = self._select(payload) if apply_selection else payload
        normalized = normalize_for_output(active_payload)
        if self._fmt == "json":
            return json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=True)
        if self._fmt == "tmux":
            return render_tmux(normalized)
        return render_toon(normalized)

    def _select(self, payload: dict[str, Any]) -> dict[str, Any]:
        contract = self._contract
        requested_fields = self._requested_fields

        requested_top_level = [field for field in requested_fields if field in contract.default_fields]

        if contract.list_key and any(field in contract.list_row_fields for field in requested_fields):
            if contract.list_key not in requested_top_level:
                requested_top_level.append(contract.list_key)

        for parent_key in contract.nested_fields:
            prefix = f"{parent_key}."
            if any(field.startswith(prefix) for field in requested_fields) and parent_key not in requested_top_level:
                requested_top_level.append(parent_key)

        for collection_key, row_fields in contract.collection_fields.items():
            if any(field in row_fields for field in requested_fields) and collection_key not in requested_top_level:
                requested_top_level.append(collection_key)

        selected = select_fields(
            payload,
            allowed_fields=contract.default_fields,
            requested_fields=tuple(requested_top_level),
        )

        if contract.list_key and contract.list_key in selected:
            row_requested = tuple(field for field in requested_fields if field in contract.list_row_fields)
            selected[contract.list_key] = [
                select_fields(row, allowed_fields=contract.list_row_fields, requested_fields=row_requested)
                for row in payload.get(contract.list_key, ())
            ]

        for parent_key, allowed_fields in contract.nested_fields.items():
            if parent_key not in selected:
                continue
            nested_requested = tuple(
                field.removeprefix(f"{parent_key}.")
                for field in requested_fields
                if field.startswith(f"{parent_key}.") and field.removeprefix(f"{parent_key}.") in allowed_fields
            )
            selected[parent_key] = select_fields(
                payload.get(parent_key, {}),
                allowed_fields=allowed_fields,
                requested_fields=nested_requested,
            )

        for collection_key, row_fields in contract.collection_fields.items():
            if collection_key not in selected:
                continue
            row_requested = tuple(field for field in requested_fields if field in row_fields)
            selected[collection_key] = [
                select_fields(row, allowed_fields=row_fields, requested_fields=row_requested)
                for row in payload.get(collection_key, ())
            ]

        return selected


def _shared_option(ctx: typer.Context, key: str, fallback: Any) -> Any:
    if key in ctx.params and ctx.params[key] is not None:
        return ctx.params[key]

    cursor = ctx.parent
    while cursor is not None:
        if key in cursor.params and cursor.params[key] is not None:
            return cursor.params[key]
        cursor = cursor.parent
    return fallback


def normalize_for_output(value: Any) -> Any:
    """Normalize output payloads so TOON and JSON share one stable shape."""

    if isinstance(value, os.PathLike):
        return os.fspath(value)
    if isinstance(value, Mapping):
        return {str(key): normalize_for_output(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [normalize_for_output(item) for item in value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [normalize_for_output(item) for item in value]
    return value
