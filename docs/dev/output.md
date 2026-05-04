# xcron Output Architecture

## Status

- Date: 2026-04-10
- Status: Implemented

## Purpose

Describe the output layer that now backs `xcron`'s Typer CLI. The current
implementation is centered on [`apps/cli/output.py`](/Users/ddebowczyk/projects/xcron/apps/cli/output.py):
one `Output` object per command invocation, contract-driven field selection,
structured errors, and pure string rendering for tests.

This document is intentionally xcron-specific. It does not describe the
broader xfind design space (`jsonl`, `text`, Rich `print_text()` paths, or
`ctx.obj`-driven option propagation) because xcron does not implement those.

## Supported Formats

xcron currently supports exactly two stdout formats:

- `toon` - default, agent-facing, compact
- `json` - machine-friendly, suitable for `jq`, scripts, and fixtures

There is no `jsonl` mode and no separate `text` mode in xcron's command output
path. Runtime help is rendered separately through
[`libs/services/help_renderer.py`](/Users/ddebowczyk/projects/xcron/libs/services/help_renderer.py).

## Command DX

The command author model is:

```python
out = Output(ctx, "status", output_format)
result = status_project(...)
out.print(map_status_response(result, contract=out.contract))
```

For errors:

```python
out.error(
    "project status inspection failed",
    details=validation_details(...),
    hints=list(out.contract.default_hints),
)
```

That replaces the older `_emit_output(...)`, `render_response(...)`,
`render_list_response(...)`, `_emit_error(...)`, and
`_resolve_output_format(...)` chain.

## The Output Object

`Output` is a pre-configured output surface for one command invocation.

```python
class Output:
    def __init__(
        self,
        ctx: typer.Context,
        contract_name: str,
        local_output: Literal["json", "toon"] | None = None,
    ) -> None: ...

    def print(self, response: PayloadConvertible) -> None: ...
    def render(self, response: PayloadConvertible) -> str: ...

    def error(
        self,
        message: str,
        *,
        code: str = "runtime_error",
        details: list[dict[str, str]] | None = None,
        hints: list[str] | None = None,
        exit_code: int = 1,
    ) -> NoReturn: ...

    @property
    def fmt(self) -> Literal["json", "toon"]: ...

    @property
    def full(self) -> bool: ...

    @property
    def contract(self) -> CommandContract: ...
```

Key behavior:

- reads `--output`, `--fields`, and `--full` from the current Typer context and
  its parent chain
- local `output_format` overrides the parent/global value
- validates `--fields` against the named `CommandContract` during construction
- renders normal responses through `render()` and writes through `print()`
- renders structured errors through `error()` and raises `typer.Exit`

## Context Resolution

xcron stores global options in Typer's normal parent parameter chain, not
`ctx.obj`. Both [`apps/cli/output.py`](/Users/ddebowczyk/projects/xcron/apps/cli/output.py)
and [`apps/cli/typer_app.py`](/Users/ddebowczyk/projects/xcron/apps/cli/typer_app.py)
walk `ctx.parent` to resolve inherited options.

Implications:

- `xcron -o json status` works
- `xcron status -o json` works
- `xcron -o json status -o toon` resolves to the per-command override
- `xcron --fields backend,statuses status` propagates the field selection into
  the leaf command

## Rendering Pipeline

Normal responses use this pipeline:

| Format | Pipeline |
|--------|----------|
| `toon` | `response.to_payload()` -> contract field selection -> `render_toon()` |
| `json` | `response.to_payload()` -> contract field selection -> `json.dumps(...)` |

Errors use the same format dispatch, but skip the command contract's normal
field selection so the full `ErrorResponse` is emitted.

Rendering stays pure:

```python
text = out.render(response)
```

`print()` is only:

```python
typer.echo(out.render(response))
```

That is why the output layer is easy to unit test.

## Response Model Inventory

All command output now flows through typed Pydantic response models in
[`libs/services/cli_responses.py`](/Users/ddebowczyk/projects/xcron/libs/services/cli_responses.py).

Current top-level response types:

- `ErrorResponse`
- `HomeResponse`
- `ValidationSummaryResponse`
- `PlanResponse`
- `StatusResponse`
- `InspectResponse`
- `JobsListResponse`
- `JobsShowResponse`
- `MutationResponse`
- `HookInstallResponse`
- `HookStatusResponse`
- `HookSessionEndResponse`

Representative row/nested types:

- `SummaryRow`
- `PlanChangeRow`
- `StatusRow`
- `JobListRow`
- `HomeJobsSummary`
- `CodexHookStatusResponse`
- `ClaudeHookStatusResponse`

`PayloadConvertible.to_payload()` is the only renderer-facing contract.

## Command Contracts

Contracts live in
[`libs/services/cli_contracts.py`](/Users/ddebowczyk/projects/xcron/libs/services/cli_contracts.py).
They define:

- `default_fields`
- `allowed_fields`
- `list_key`
- `list_row_fields`
- `nested_fields`
- `collection_fields`
- optional truncation/default-hint metadata

Representative shapes:

- `status` uses `list_key="statuses"` with row fields `kind`, `id`, `reason`
- `inspect` uses nested `desired` / `deployed` objects
- `home` mixes nested `jobs` with collection-style `plan_summary` and
  `plan_changes`
- `hooks.status` uses nested `codex` and `claude` objects

`Output._select()` intentionally supports mixed shapes inside one payload. That
matters for `home`, where nested and collection fields coexist.

## Field Selection

`--fields` is validated up front and then applied during rendering.

Examples:

```sh
xcron status --fields backend,statuses
xcron status --fields id
xcron inspect sync_docs --fields backend,job,desired.command,deployed.artifact_path
xcron hooks status --fields executable,codex.session_start_matches
```

Selection rules:

- flat responses filter top-level keys only
- list responses can request either top-level keys or row fields
- nested responses use dot notation like `desired.command`
- collection responses can request row fields directly and the parent collection
  is included automatically

Invalid field requests produce a structured usage error on stdout.

## Truncation And `--full`

`xcron inspect` is truncation-aware. The mapper builds snippet payloads with
preview metadata unless `--full` is active.

Default behavior:

- large backend-native snippet fields are truncated
- the payload includes preview metadata plus a hint to rerun with `--full`

With `--full`:

- the full raw snippet content is emitted

The flag is exposed on `inspect` and on the root callback so it can propagate
from the top-level invocation.

## Structured Errors

Errors are stdout-first and typed:

```text
kind: error
code: usage_error
message: unsupported output format: 'yaml'; expected one of json, toon
```

Exit codes:

- `1` - runtime or action failure
- `2` - usage or validation failure at the CLI boundary

There is also a small bootstrap error path in
[`apps/cli/typer_app.py`](/Users/ddebowczyk/projects/xcron/apps/cli/typer_app.py)
for failures that occur before an `Output` object can be constructed, such as
an invalid `--output` value.

## Help Rendering Boundary

Help rendering is no longer part of the output renderer module. The only Rich
Markdown rendering path now lives in
[`libs/services/help_renderer.py`](/Users/ddebowczyk/projects/xcron/libs/services/help_renderer.py).

That separation is deliberate:

- command output: TOON / JSON through `Output`
- authored runtime help: Markdown + parser reference through `help_renderer`

## Module Layout

```text
apps/cli/
  output.py       - Output class + normalize_for_output
  typer_app.py    - Typer commands and bootstrap usage-error path
  common.py       - shared CLI option helpers

libs/services/
  cli_responses.py   - typed CLI response models
  cli_contracts.py   - field-selection contracts
  cli_mappers.py     - action result -> response model translation
  axi_presenter.py   - field filtering and truncation helpers
  help_renderer.py   - authored Markdown help rendering
  toon_renderer.py   - TOON adapter
```

Removed in the refactor:

- `libs/services/output_renderer.py`
- `_emit_output`
- `_emit_error`
- `_resolve_output_format`
- the old `render_*_response()` helper chain

## Testing Strategy

The current output layer is verified at three levels:

- render-unit tests in
  [`tests/test_cli_output.py`](/Users/ddebowczyk/projects/xcron/tests/test_cli_output.py)
- command/contract coverage in CLI tests such as
  [`tests/test_typer_cli.py`](/Users/ddebowczyk/projects/xcron/tests/test_typer_cli.py)
  and [`tests/test_cli_parser.py`](/Users/ddebowczyk/projects/xcron/tests/test_cli_parser.py)
- full regression coverage through `uv run python -m pytest tests/ -x`

Important cases covered by tests:

- TOON vs JSON rendering
- flat/list/nested/collection field selection
- parent-context option inheritance
- structured error emission
- hooks output contracts

## Practical Rules For Future Changes

- Add or change response shape in `cli_responses.py`
- Update the matching contract in `cli_contracts.py`
- Keep action-to-response translation in `cli_mappers.py`
- Keep stdout writes inside `Output.print()` / `Output.error()`
- Extend `help_renderer.py` only for authored help, not normal command output
