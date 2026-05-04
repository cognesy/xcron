# xcron Agent Operating Brief

This file is optimized for agents working in this repo. Read it before editing.

## Project Purpose

`xcron` is a CLI-first schedule definition and reconciliation tool for
project-local recurring shell commands. A project keeps one YAML schedule
manifest under `resources/schedules/`, and `xcron` reconciles that desired state
to the native OS scheduler.

`xcron` is implemented in Python now as a prototype. The external contract is
designed to remain stable across the planned later Go rewrite (see
`docs/dev/go-rewrite-contract.md`).

CLI entrypoint:

```bash
uv run xcron
```

## Product Boundaries / Non-Goals

`xcron` is:

- a schedule definition and reconciliation tool;
- a thin control plane over native schedulers (`launchd`, `cron`, future
  `systemd`);
- a CLI-first developer and operator tool.

`xcron` is not:

- a job queue, workflow engine, distributed scheduler, or orchestration system;
- a long-running scheduler daemon or process supervisor;
- a runner of jobs inside its own process.

Other boundaries:

- desired state always comes from one project's own manifest under
  `resources/schedules/`. There is no central machine-wide manifest;
- only artifacts that carry an `xcron` ownership marker are touched. Unmanaged
  plists and crontab entries stay outside scope;
- queue semantics, retries, backoff, workflow chaining, distributed
  coordination, and cloud schedulers are explicitly out of v1.

## Repo Layout

```text
apps/cli/                 Typer shell, Output class, AXI output boundary
libs/actions/             one use case per command/workflow
libs/services/            reusable services
libs/services/backends/   launchd_service, cron_service
libs/domain/              Pydantic domain models, normalization, diffing
libs/infra/               infra placeholder helpers
resources/schemas/        schedules.schema.yaml (manifest schema)
resources/help/           packaged Markdown command help
resources/logging/        default structlog logging config
resources/templates/      AXI command/test templates
resources/examples/       example projects (basic, disabled-job)
resources/skills/         repo-local agent skills (use-xcron, admin-xcron)
docs/user/                user guide
docs/dev/                 architecture, output, logging, plans, retrospectives
scripts/verify-core.sh    deterministic core verification entrypoint
tests/                    pytest suite (unit + parser + CLI + observability)
tests/integration/        explicit-only host launchd and Docker cron harnesses
SPEC.md                   product specification (also used as package readme)
```

## Layering Contract

Dependency direction:

```text
apps/cli
  -> libs/actions
  -> libs/services (incl. libs/services/backends)
  -> libs/domain
```

Rules:

- `apps/cli` parses Typer flags, resolves the project path / shared options,
  calls exactly one action, renders typed responses through the `Output` class
  in `apps/cli/output.py`, and sets exit codes.
- `apps/cli` must not contain manifest IO, scheduler IO, subprocess logic, hash
  comparisons, or domain rules.
- `libs/actions` owns user-visible use cases: `validate_project`, `plan_project`,
  `status_project`, `apply_project`, `prune_project`, `inspect_job`,
  `manage_jobs`, `manage_logs`, `metrics`, `init_home`. Actions coordinate
  services and return structured `*Result` types.
- `libs/services` provides reusable capabilities: config/manifest loading,
  schema and semantic validation, manifest editing, hashing, wrapper rendering,
  state persistence, AXI presentation/contracts/mappers, structured logging,
  hook installers, scheduler backends.
- `libs/services/backends` hides launchd plist generation/loading and cron
  managed-block handling behind narrow service interfaces.
- `libs/domain` contains Pydantic models, normalization, plan/status diffing,
  and qualified-id helpers. Domain code must not import from `apps`.
- Services do not call actions or shell code.
- Keep arrays/dicts at the YAML/output boundary; use typed Pydantic models
  internally.

The architecture mirrors the rules in `SPEC.md` and `docs/dev/architecture.md`,
which the later Go rewrite is expected to preserve.

## AXI CLI Contract

`xcron` is agent-facing. Preserve this behavior:

- Default stdout format is TOON.
- JSON is the automation format (`--output json` / `-o json`).
- `tmux` is supported for selected commands such as `xcron logs` and
  `xcron inspect` views that benefit from tmux pane formatting.
- Convert to TOON/JSON/tmux only at the output boundary. Internal logic returns
  Pydantic response models from `libs/services/cli_responses.py`.
- `--fields` is validated up front against the per-command `CommandContract`
  in `libs/services/cli_contracts.py`. Invalid fields become structured usage
  errors, not silent no-ops.
- `--full` expands truncated snippet payloads in detail-heavy commands,
  primarily `inspect`.
- Bare `xcron` returns a content-first home view via `plan_project`. It must
  not mutate scheduler state.
- Structured errors are written to stdout in the selected format. Logs,
  progress, and subprocess diagnostics go to stderr through `structlog`.
- Never prompt interactively. Missing or invalid input is a structured
  `usage_error`.
- Exit codes:
  - `0`: success or idempotent no-op (mutations report `outcome: noop`);
  - `1`: runtime / action / backend failure;
  - `2`: usage / validation failure at the CLI boundary.

When changing CLI behavior, inspect and update:

- `apps/cli/typer_app.py` (Typer commands and bootstrap usage-error path)
- `apps/cli/output.py` (`Output` class, normalization, field selection)
- `apps/cli/common.py` (shared option/env helpers)
- `libs/services/cli_contracts.py`, `cli_responses.py`, `cli_mappers.py`
- `resources/help/*.md` (authored runtime help)
- `tests/test_cli_*` and `tests/test_typer_cli.py`

See `docs/dev/output.md` for the full output design.

## Core Operating Model

`xcron` models three layers:

1. **Desired state** — `<project-root>/resources/schedules/<schedule>.yaml`.
2. **Rendered native state** — generated launchd plist or managed crontab
   block, plus per-project wrapper scripts and runtime state.
3. **Actual machine state** — what `launchd`/`cron` currently report.

`plan` compares desired state against `xcron`'s **derived local state**
(`project-state.json` from the last `apply`). It is fast and does not touch the
scheduler.

`status` compares desired state against **actual deployed state** (real plist
files, real crontab entries). Use `status` for ground truth.

`apply` always uses actual backend state as its baseline. After manual edits to
plists, crontab, or wrappers, `plan` and `status` will disagree — trust
`status`.

Default project root is `~/.xcron` (overridable via `--project` or
`XCRON_HOME`). Default backend is platform-derived: `launchd` on macOS, `cron`
on Linux. Override with `--backend launchd|cron`.

Standard workflow:

```bash
uv run xcron init          # initialize ~/.xcron/ with a starter manifest
uv run xcron validate
uv run xcron plan
uv run xcron apply
uv run xcron status
uv run xcron inspect <job-id> [--full] [-o json]
```

Manifest mutation through the CLI edits YAML only. `apply` is the step that
reconciles scheduler state:

```bash
uv run xcron jobs list
uv run xcron jobs add <id> --command <cmd> --cron "*/15 * * * *"
uv run xcron jobs add <id> --command <cmd> --every 1h
uv run xcron jobs update <id> --cron "0 * * * *" --clear-env
uv run xcron jobs enable|disable|remove <id>
```

Other surfaces:

- `xcron prune` — remove all managed artifacts for the project.
- `xcron logs list|clear` — inspect / truncate wrapper log files.
- `xcron metrics show|reset` — persisted runtime metrics.
- `xcron hooks install|status|repair` — repo-local Codex and Claude hooks
  written to `.codex/config.toml`, `.codex/hooks.json`, `.claude/settings.json`.
- `xcron hooks session-start|session-end` — hidden CLI surfaces invoked by
  installed agent hooks.

## Runtime Layout And Env Overrides

Managed derived state is machine-local and partitioned by `project.id`:

```text
# macOS
~/Library/Application Support/xcron/projects/<project-id>/
# Linux
~/.local/state/xcron/projects/<project-id>/
  project-state.json   # xcron's records from last apply
  wrappers/            # generated shell wrapper scripts
  logs/                # *.out.log, *.err.log, *.events.jsonl
  locks/               # overlap-forbid lock dirs (transient)
```

Backend artifacts:

- launchd: `~/Library/LaunchAgents/com.xcron.<project-id>.<job-id>.plist`
- cron: a managed block in the user crontab, delimited by
  `# BEGIN XCRON project=<id>` … `# END XCRON project=<id>`.

Useful environment overrides (covered by tests; safe for isolated runs):

| Variable | Purpose |
|----------|---------|
| `XCRON_HOME` | default project root used when `--project` is not passed |
| `XCRON_STATE_ROOT` | derived state root (wrappers, logs, locks, project-state.json) |
| `XCRON_LAUNCH_AGENTS_DIR` | plist output directory (launchd) |
| `XCRON_LAUNCHCTL_DOMAIN` | launchd domain (e.g. `gui/501`) |
| `XCRON_CRONTAB_PATH` | file path used instead of the real user crontab |
| `XCRON_MANAGE_LAUNCHCTL` | `0` skips all `launchctl` calls |
| `XCRON_MANAGE_CRONTAB` | `0` skips all crontab writes |
| `XCRON_LOG_LEVEL` | structlog level (`DEBUG`/`INFO`/...) |
| `XCRON_LOG_FORMAT` | `console` or `json` for stderr logs |
| `XCRON_RUN_LAUNCHD_IT` | gate for the explicit launchd integration test |

The pytest `conftest.py` sets `XCRON_HOME` to a per-test tmp dir, so unit tests
never write to the real `~/.xcron`.

## Commands And Quality Gates

Use `uv` for every Python workflow.

```bash
uv sync
uv run xcron --help
uv run xcron --output json
uv run xcron status -o json --fields backend,statuses
```

Default deterministic core lane:

```bash
./scripts/verify-core.sh        # currently runs `uv run pytest`
```

Equivalent direct invocation:

```bash
uv run pytest
```

Optional `xqa` pilot (delegates to the same core lane):

```bash
xqa doctor
xqa doctor --profile default
xqa profile run default --output json
xqa snap store --output json
xqa progress --against latest --output text
```

`.xqa/config.yaml` defines the `default` and `tests` profiles, both wrapping
`./scripts/verify-core.sh` and writing JUnit XML to `.xqa/state/`.

Run the relevant subset while developing. Run the full pytest suite before
closing a task that changed code, CLI behavior, manifest schema, packaged
resources, or skills. There is no `ruff`/`mypy`/`pyright` gate configured in
this repo today.

Cheap CLI smokes that are safe to run for documentation-only changes:

```bash
uv run xcron --help
uv run xcron jobs --help
git diff --check
```

## Explicit Integration Checks

Real scheduler integration runs are explicit-only and stay outside the
deterministic core lane.

macOS host launchd:

```bash
XCRON_RUN_LAUNCHD_IT=1 XCRON_LOG_FORMAT=json XCRON_LOG_LEVEL=INFO \
  uv run pytest tests/integration/launchd_real_it.py -s
```

Linux cron in Docker/Colima:

```bash
./tests/integration/run_cron_it.sh
```

The cron harness uses Docker rather than the host scheduler, installs the
project with `uv`, and exercises `apply`, `status`, `inspect`, scheduled
execution, and `prune`. See `tests/integration/README.md`.

## Testing Expectations

- Add or update tests for behavior changes.
- Keep tests focused on the changed layer (action, service, mapper, contract,
  renderer, backend).
- CLI/output changes need updates in `tests/test_cli_*.py`,
  `tests/test_typer_cli.py`, and the matching `cli_contracts`/`cli_mappers`
  tests.
- New response shapes require a `cli_responses.py` model and a matching
  `cli_contracts.py` entry; both belong to the same change.
- Backend changes need `tests/test_launchd_backend.py` /
  `tests/test_cron_backend.py` updates.
- Wrapper / runtime-log changes need
  `tests/test_wrapper_renderer.py` and `tests/test_cli_logs.py`.
- For documentation-only changes that touch `resources/help/` or skills, run
  the help and skill smoke tests (`tests/test_help_renderer.py`,
  `tests/test_typer_cli.py`) and `git diff --check` at minimum.
- Do not unconditionally invoke `launchctl` or write the user crontab from new
  tests. Use the `XCRON_MANAGE_*` and `XCRON_*_PATH` env overrides.

## Agent Skills / Resources

Repo-local agent skills are product assets under `resources/skills/`:

- `use-xcron` — day-to-day xcron use (defining and editing jobs, applying,
  verifying deployed state).
- `admin-xcron` — admin / troubleshooting (drift recovery, backend inspection,
  ownership boundaries, test overrides).

A bare `resources/skill/SKILL.md` placeholder also exists at the resources
root; treat it as a legacy stub, not a current skill.

When editing skills, run a help/CLI smoke and `git diff --check`. There is no
repo-local skill validator script wired in today; do not invent one.

Authored runtime help is packaged under `resources/help/`. The default logging
config is packaged under `resources/logging/default.yaml`. Both are loaded via
`importlib.resources` from installed wheels — keep filenames and the
`pyproject.toml` `package-data` glob in sync.

## Documentation Map

- `README.md` — high-level project summary and quick start.
- `SPEC.md` — full product specification (also the package long-description).
- `docs/user/README.md` — user guide (commands, manifest format, output model,
  status semantics, env overrides, integration checks).
- `docs/dev/architecture.md` — architecture and layering rules.
- `docs/dev/output.md` — AXI output design (`Output`, contracts, field
  selection, truncation).
- `docs/dev/logging.md` — observability and structured logging.
- `docs/dev/go-rewrite-contract.md` — external contract that must remain stable
  for the future Go implementation.
- `docs/dev/plans/` — durable implementation plans.
- `docs/dev/notes/` and `docs/dev/retrospectives/` — design notes and
  retrospectives.
- `tests/integration/README.md` — explicit launchd/cron harness instructions.

## Issue Tracking With bd

Use bd (beads) for all task tracking. Do not use markdown TODO lists or
TodoWrite as the source of truth.

Common commands:

```bash
bd ready --json
bd show <id> --json
bd update <id> --claim --json
bd close <id> --reason "Done" --json
bd status --json
bd epic status --json
```

Task workflow:

1. `bd ready --json` to find unblocked work.
2. `bd update <id> --claim --json` to claim atomically.
3. `bd show <id> --json` to read requirements.
4. Implement.
5. Verify.
6. `bd close <id> --reason "<specific reason>" --json`.
7. File follow-up issues with `--deps discovered-from:<id>` when needed.

Embedded bd lock warning: do not run multiple `bd` write/read commands in
parallel. The embedded backend often permits only one active access. If a lock
error appears, rerun the bd command serially.

## Git / Session Completion

This repo has a configured Git remote (`origin` →
`https://github.com/cognesy/xcron.git`), so `git push` is the normal end of a
session.

At session end:

1. File bd issues for follow-up work if needed.
2. Run the relevant quality gates (`./scripts/verify-core.sh` for code
   changes; help/CLI smoke for docs/skills; no-op for AGENTS.md-only changes
   beyond `git diff --check`).
3. Close or update bd issues.
4. Remove generated caches when they are not intentional artifacts:

   ```bash
   find apps libs resources tests -type d -name __pycache__ -prune -exec rm -rf {} +
   rm -rf .pytest_cache .ruff_cache .mypy_cache
   ```

5. Commit completed changes when requested or when the repo workflow requires
   it.
6. Attempt `git pull --rebase` then `git push`.
7. If `git push` fails (auth, no remote, conflict), report the exact blocker
   and resolve it. Do not claim push succeeded.

Do not commit `.venv`, `__pycache__`, pytest/ruff/mypy caches, `.xqa/state/`,
secrets, or local-only runtime files. `.gitignore` already excludes these.

## Shell Safety

Use non-interactive forms for commands that may prompt. Some local shells alias
`cp`, `mv`, and `rm` to `-i`, which causes agents to hang waiting on stdin.

```bash
cp -f source dest
mv -f source dest
rm -f file
rm -rf directory
cp -rf source dest
ssh -o BatchMode=yes ...
scp -o BatchMode=yes ...
```

Other commands that may prompt:

- `apt-get` — pass `-y`.
- `brew` — set `HOMEBREW_NO_AUTO_UPDATE=1`.

Prefer `rg` and `rg --files` over `find`/`grep` for searches in this repo.
