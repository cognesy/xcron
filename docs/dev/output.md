# Output Architecture

## Status

- Date: 2026-04-10
- Status: Design

## Purpose

Define how xfind renders structured output to stdout across all output formats
(toon, json, jsonl, text). This document serves as the refactoring guide for
xfind and as a reference for aligning xcron and sibling tools.

## Design Goals

1. **Familiar DX**: command authors write `out.print(response)` — one object,
   one method, one argument. Mirrors Rich's `console.print()` pattern that
   every Python CLI developer already knows.
2. **Typed end-to-end**: response models are Pydantic classes with typed fields.
   No `dict[str, Any]` at any layer boundary.
3. **Pure rendering**: format dispatch returns strings. I/O happens at one point.
4. **Contract-driven**: output schema (default fields, allowed fields, row
   fields) is declared once per command and derived from the response model.
5. **AXI-compliant**: TOON default, field filtering, truncation, structured
   errors, content-first home, contextual hints.

## The Output Object

The central interface is `Output` — a pre-configured output surface that knows
the format, contract, and field selection. It wraps Rich's `Console` for the
text path and provides `print()` as the single method command authors use.

```python
class Output:
    """Pre-configured output surface for one command invocation.

    Constructor reads --output, --fields, --full from Typer context,
    validates fields against the named contract, and stores everything.
    No separate factory or resolve step.
    """

    def __init__(
        self,
        ctx: typer.Context,
        contract_name: str,
        local_output: OutputFormat | None = None,
    ) -> None: ...

    def print(self, response: PayloadConvertible) -> None:
        """Render and emit a response to stdout."""
        ...

    def render(self, response: PayloadConvertible) -> str:
        """Render a response to string without I/O. Useful for testing."""
        ...

    def error(
        self,
        message: str,
        *,
        code: str = "runtime_error",
        details: list[ErrorDetail] | None = None,
        hints: list[str] | None = None,
        exit_code: int = 1,
    ) -> NoReturn:
        """Render a structured error to stdout and exit."""
        ...

    @property
    def fmt(self) -> OutputFormat: ...

    @property
    def full(self) -> bool: ...
```

### Command DX

Before (current):

```python
def doctor(ctx: typer.Context, output: OutputFormat | None = ...) -> None:
    rc = _resolve_render(ctx, "doctor", output)
    result = doctor_action(registry=_registry())
    response = map_doctor_response(result)
    emit_response(
        fmt=rc.fmt,
        response=response,
        contract=rc.contract,
        requested_fields=rc.requested_fields,
        console=console,
    )
```

After:

```python
def doctor(ctx: typer.Context, output: OutputFormat | None = ...) -> None:
    out = Output(ctx, "doctor", output)
    result = doctor_action(registry=_registry())
    out.print(map_doctor_response(result))
```

Three lines. The command author sees: create output, call action, print
response. No plumbing.

### Error DX

Before:

```python
_emit_error(
    f"source {source!r} is not registered",
    fmt=rc.fmt,
    help_items=["Run `xfind source list` to see registered sources"],
)
```

After:

```python
out.error(
    f"source {source!r} is not registered",
    hints=["Run `xfind source list` to see registered sources"],
)
```

The Output object already knows the format. No need to pass it.

## Format Dispatch

`Output.print()` dispatches based on format:

| Format | Pipeline |
|--------|----------|
| `toon` | `response.to_payload()` → field filter → `render_toon()` → stdout |
| `json` | `response.to_payload()` → `json.dumps(indent=2)` → stdout |
| `jsonl` | `response.jsonl_items()` → one `json.dumps` per item → stdout |
| `text` | response → text renderer → `console.print()` |

All machine formats (toon, json, jsonl) go through `to_payload()` and write
plain strings to stdout. The text format uses Rich's Console for styled output.

### Rendering is pure

The format dispatch can be split into two steps for testability:

```python
def render(self, response: PayloadConvertible) -> str:
    """Render a response to string without I/O."""
    ...

def print(self, response: PayloadConvertible) -> None:
    """Render and emit to stdout."""
    text = self.render(response)
    typer.echo(text)
```

This allows tests to call `render()` and inspect the string without capturing
stdout.

## Response Models

Every command has a dedicated typed response model. No generic envelopes with
`dict[str, Any]` contents.

```
PayloadConvertible (base)
├── ErrorResponse
├── HomeResponse
├── SourceListResponse    (items: list[SourceRow])
├── SourceShowResponse
├── SourceAddResponse
├── IndexListResponse     (items: list[IndexRow])
├── IndexBuildResponse
├── IndexRefreshResponse
├── SearchResponse        (results: list[SearchResultRow])
├── HelpDocumentResponse
├── HelpListResponse      (items: list[HelpTopicRow])
├── DoctorResponse
├── ConfigShowResponse
├── ConfigValidateResponse
├── HookInstallResponse
└── HookStatusResponse
```

### PayloadConvertible base

```python
class PayloadConvertible(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    def jsonl_items(self) -> list[BaseModel] | None:
        return None
```

List response types override `jsonl_items()` to return their items list. The
dispatcher calls this instead of guessing by key name.

### Row models

List responses contain typed row models:

```python
class SourceRow(BaseModel):
    name: str
    root_path: str
    status: str = "new"
    ...

class SourceListResponse(PayloadConvertible):
    kind: str = "source.list"
    count: int = 0
    total: int = 0
    items: list[SourceRow] = Field(default_factory=list)
    help: list[str] = Field(default_factory=list)

    def jsonl_items(self) -> list[BaseModel] | None:
        return self.items
```

## Command Contracts

Contracts define the output schema for TOON field filtering. They are derived
from response models at import time via `contract_from_model()`:

```python
"doctor": contract_from_model(
    "doctor", "diagnostics", DoctorResponse,
    default_fields=("kind", "config_valid", "registered_sources",
                    "registered_indexes", "uv_venv_present"),
),
```

`allowed_fields` is automatically derived from `DoctorResponse.model_fields`.
Import-time validation ensures `default_fields` is a subset of `allowed_fields`.

### Field filtering

The `--fields` flag lets agents request specific fields:

```
xfind doctor --fields kind,config_valid
```

Field filtering applies to toon and json formats. The presenter selects fields
from the payload dict before rendering. For list responses, both top-level
fields and row-level fields are filtered.

### Truncation

The `--full` flag disables content truncation. When `full=False` (default),
large text fields are truncated to the contract's `truncation_limit` with a
metadata hint showing total size and the `--full` escape hatch.

## Output Flag

All commands accept `--output` / `-o` with values: `toon`, `json`, `jsonl`,
`text`. Default is `toon`.

The flag is both a global option (on the app callback) and a per-command option.
Per-command overrides global. Global propagates to subcommands via Typer's
`ctx.obj`.

```
xfind -o json doctor           # global
xfind doctor -o json           # per-command
xfind -o json doctor -o toon   # per-command wins
```

## Structured Errors

All errors emit a typed `ErrorResponse` to stdout with exit code 1 (runtime) or
2 (usage). Errors go through the same Output object as normal responses:

```python
out.error("source 'x' not registered", hints=["Run `xfind source list`"])
```

This renders the ErrorResponse in the current format (toon, json, etc.) and
calls `raise typer.Exit(code=1)`.

Error envelope:

```
kind: error
code: runtime_error
message: source 'x' is not registered
help[1]: Run `xfind source list` to see registered sources
```

## Content-First Home View

Bare `xfind` (no subcommand) shows live state via `HomeResponse`:

```
bin: ~/.local/bin/xfind
description: Local indexed search for sources and knowledge bases
sources[2]{name,status,indexes}:
  myproject,ready,3
  docs,building,1
help[2]:
  Run `xfind search <query> --source <name>` to search
  Run `xfind help` for topic guides
```

The text format renders a human-friendly version with Rich styling.

## Contextual Disclosure

Response models include `help: list[str]` fields with next-step hints. Mappers
populate these based on output state:

- Empty list → suggest creating
- Populated list → suggest viewing/searching
- After mutation → suggest next logical action
- Self-contained detail → omit hints

Hints use `<placeholder>` syntax for dynamic values and carry forward
disambiguating flags from the current invocation.

## Text Format Rendering

The text format is the human-readable path. Each response type can register a
text renderer. The default text renderer uses `console.print_json()`. Specific
types override with richer rendering:

- `HomeResponse` → styled source summary with section headers
- `HelpDocumentResponse` → Rich Markdown rendering
- `HelpListResponse` → Rich Markdown topic list
- `SearchResponse` → per-result blocks with path, score, snippet

Text renderers receive the typed response object (not a dict) and a Rich
Console.

## TOON Format

TOON is the default agent-facing format. It uses the `python-toon` library
behind a single adapter (`toon_renderer.py`). The adapter normalizes Python
containers and encodes to TOON text.

TOON output goes through contract-driven field filtering before encoding. This
ensures agents see only the fields they need by default, with `--fields`
available for explicit field requests.

## Module Layout

```
libs/xfind/services/
  axi_responses.py     — typed response models (PayloadConvertible + 16 models)
  axi_contracts.py     — command contracts derived from models
  axi_mappers.py       — action result → response model translation
  axi_presenter.py     — field filtering, truncation, error builder
  toon_renderer.py     — TOON adapter (wraps python-toon)

apps/cli/xfind_cli/
  output.py            — Output class (format dispatch + I/O)
  main.py              — Typer commands (resolve_output + out.print)
  hooks_commands.py    — hooks subcommand group
```

Key boundary: everything under `libs/` is pure (no I/O). The `Output` class in
`apps/cli/` is the only place that writes to stdout.

## Construction

`Output.__init__` is the resolver. No separate factory function:

```python
out = Output(ctx, "doctor")           # default format (toon)
out = Output(ctx, "doctor", output)   # local --output override
```

The constructor walks the Typer parent context to read `--output`, `--fields`,
`--full` from the global callback, merges with the local `--output` override,
validates `--fields` against the named contract, and stores everything. The
Output is ready to use immediately after construction.

## Mappers

Mappers translate action results into typed response models. One mapper per
command. Mappers are pure functions that do not call the presenter or renderer:

```python
def map_doctor_response(result: dict[str, Any]) -> DoctorResponse:
    return DoctorResponse(**{k: v for k, v in result.items()
                            if k in DoctorResponse.model_fields})
```

Mappers also populate contextual hints based on output state.

## Session Hooks

Session hooks (`xfind hooks session-start`, `xfind hooks session-end`) use the
same Output pipeline. The session-start hook always outputs TOON regardless of
user preference (it runs at session start before the user has specified a
format).

Hook installation is managed by `hook_installer.py` which creates/updates
Claude Code and Codex configuration files with absolute executable paths and
idempotent path repair.

## Testing Strategy

- **Response model tests**: verify `to_payload()` produces expected shapes
- **Contract tests**: verify contracts align with response models
- **Render tests**: call `Output.render()` (pure) and inspect the string
- **CLI tests**: invoke via CliRunner and verify stdout
- **TOON regression tests**: parse TOON with `toon.decode` and verify structure
- **JSON regression tests**: parse JSON and verify key presence

Prefer testing structural properties (key presence, type) over exact shapes
(full key enumeration). Exact shapes break on every field addition.
