"""Render and write managed wrapper scripts for xcron jobs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex

from libs.domain.models import NormalizedJob, OverlapPolicy
from libs.services.logging_paths import RuntimePaths, ensure_runtime_dirs, resolve_runtime_paths
from libs.services.observability import get_logger

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class RenderedWrapper:
    """Wrapper rendering result for one job."""

    job: NormalizedJob
    desired_hash: str
    runtime_paths: RuntimePaths
    content: str


def render_wrapper(job: NormalizedJob, desired_hash: str, state_root: Path | None = None) -> RenderedWrapper:
    """Render the managed shell wrapper for one normalized job."""
    runtime_paths = resolve_runtime_paths(job, state_root=state_root)
    lines = [
        "#!/bin/sh",
        "# xcron managed wrapper",
        f"# qualified_id: {job.qualified_id}",
        f"# desired_hash: {desired_hash}",
        "set -eu",
        "",
        f"mkdir -p {shell_quote(str(runtime_paths.logs_dir))}",
        f"mkdir -p {shell_quote(str(runtime_paths.locks_dir))}",
        f"exec >>{shell_quote(str(runtime_paths.stdout_log_path))} 2>>{shell_quote(str(runtime_paths.stderr_log_path))}",
        f"EVENT_LOG_PATH={shell_quote(str(runtime_paths.event_log_path))}",
        f"STDOUT_LOG_PATH={shell_quote(str(runtime_paths.stdout_log_path))}",
        f"STDERR_LOG_PATH={shell_quote(str(runtime_paths.stderr_log_path))}",
        f"QUALIFIED_ID={shell_quote(job.qualified_id)}",
        f"DESIRED_HASH={shell_quote(desired_hash)}",
        f"JOB_COMMAND={shell_quote(job.execution.command)}",
        f"JOB_WORKING_DIR={shell_quote(job.execution.working_dir)}",
        "RUN_ID=$(date -u +\"%Y%m%dT%H%M%SZ\")-$$",
        "RUN_STARTED=0",
        "FINISH_REPORTED=0",
        "STDOUT_TMP=",
        "STDERR_TMP=",
        "xcron_metric() {",
        "  metric_counter=$1",
        "  if command -v python3 >/dev/null 2>&1; then",
        "    XCRON_METRIC_COUNTER=\"$metric_counter\" python3 - <<'PY' 2>/dev/null || true",
        "import datetime, json, os, pathlib",
        "counter = os.environ['XCRON_METRIC_COUNTER']",
        "configured = os.environ.get('XCRON_HOME')",
        "root = pathlib.Path(configured).expanduser() if configured else pathlib.Path.home() / '.xcron'",
        "path = root / 'metrics' / 'metrics.json'",
        "now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()",
        "try:",
        "    payload = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}",
        "except Exception:",
        "    payload = {}",
        "payload.setdefault('version', 1)",
        "payload.setdefault('created_at', now)",
        "payload['updated_at'] = now",
        "counters = payload.setdefault('counters', {})",
        "counters[counter] = int(counters.get(counter, 0)) + 1",
        "path.parent.mkdir(parents=True, exist_ok=True)",
        "path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\\n', encoding='utf-8')",
        "PY",
        "  fi",
        "}",
        "xcron_event() {",
        "  event_name=$1",
        "  if command -v python3 >/dev/null 2>&1; then",
        "    XCRON_EVENT=\"$event_name\" \\",
        "    XCRON_EVENT_LOG_PATH=\"$EVENT_LOG_PATH\" \\",
        "    XCRON_RUN_ID=\"$RUN_ID\" \\",
        "    XCRON_QUALIFIED_ID=\"$QUALIFIED_ID\" \\",
        "    XCRON_DESIRED_HASH=\"$DESIRED_HASH\" \\",
        "    XCRON_PID=\"$$\" \\",
        "    XCRON_COMMAND=\"$JOB_COMMAND\" \\",
        "    XCRON_CWD=\"$JOB_WORKING_DIR\" \\",
        "    XCRON_STDOUT_LOG_PATH=\"$STDOUT_LOG_PATH\" \\",
        "    XCRON_STDERR_LOG_PATH=\"$STDERR_LOG_PATH\" \\",
        "    python3 - <<'PY' 2>/dev/null || true",
        "import datetime, json, os, pathlib",
        "def optional_int(name):",
        "    value = os.environ.get(name)",
        "    return None if value in (None, '') else int(value)",
        "payload = {",
        "    'timestamp': datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),",
        "    'event': os.environ['XCRON_EVENT'],",
        "    'run_id': os.environ['XCRON_RUN_ID'],",
        "    'qualified_id': os.environ['XCRON_QUALIFIED_ID'],",
        "    'desired_hash': os.environ['XCRON_DESIRED_HASH'],",
        "    'pid': optional_int('XCRON_PID'),",
        "    'command': os.environ['XCRON_COMMAND'],",
        "    'cwd': os.environ['XCRON_CWD'],",
        "    'stdout_log_path': os.environ['XCRON_STDOUT_LOG_PATH'],",
        "    'stderr_log_path': os.environ['XCRON_STDERR_LOG_PATH'],",
        "    'event_log_path': os.environ['XCRON_EVENT_LOG_PATH'],",
        "    'stream': os.environ.get('XCRON_STREAM'),",
        "    'sequence': optional_int('XCRON_SEQUENCE'),",
        "    'line': os.environ.get('XCRON_LINE'),",
        "    'exit_code': optional_int('XCRON_EXIT_CODE'),",
        "    'duration_seconds': optional_int('XCRON_DURATION_SECONDS'),",
        "}",
        "payload = {key: value for key, value in payload.items() if value is not None}",
        "path = pathlib.Path(os.environ['XCRON_EVENT_LOG_PATH'])",
        "path.parent.mkdir(parents=True, exist_ok=True)",
        "with path.open('a', encoding='utf-8') as handle:",
        "    handle.write(json.dumps(payload, sort_keys=True, separators=(',', ':')) + '\\n')",
        "PY",
        "  fi",
        "}",
        "xcron_replay_stream() {",
        "  stream=$1",
        "  path=$2",
        "  sequence=0",
        "  while IFS= read -r line || [ -n \"$line\" ]; do",
        "    if [ \"$stream\" = stdout ]; then",
        "      printf \"%s\\n\" \"$line\"",
        "    else",
        "      printf \"%s\\n\" \"$line\" >&2",
        "    fi",
        "    XCRON_STREAM=\"$stream\" XCRON_SEQUENCE=\"$sequence\" XCRON_LINE=\"$line\" xcron_event child_output",
        "    sequence=$((sequence + 1))",
        "  done < \"$path\"",
        "}",
        f"cd {shell_quote(job.execution.working_dir)}",
    ]

    if job.execution.timezone:
        lines.append(f"export TZ={shell_quote(job.execution.timezone)}")

    for key, value in job.execution.env:
        lines.append(f"export {key}={shell_quote(value)}")

    lines.extend(
        [
            "",
            "finish_run() {",
            '  status=$1',
            '  if [ "${FINISH_REPORTED:-0}" -eq 1 ]; then',
            "    return",
            "  fi",
            "  FINISH_REPORTED=1",
            '  if [ "${RUN_STARTED:-0}" -eq 1 ]; then',
            '    FINISHED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")',
            '    FINISHED_EPOCH=$(date +%s)',
            '    DURATION_SECONDS=$((FINISHED_EPOCH - STARTED_EPOCH))',
            "    xcron_metric ticks.finished",
            '    XCRON_EXIT_CODE="$status" XCRON_DURATION_SECONDS="$DURATION_SECONDS" xcron_event job_finished',
            f'    printf "%s event=job_finished run_id=%s qualified_id={job.qualified_id} desired_hash={desired_hash} exit_code=%s duration_seconds=%s\\n" "$FINISHED_AT" "$RUN_ID" "$status" "$DURATION_SECONDS" >&2',
            "  fi",
            "}",
            "on_exit() {",
            '  status=$?',
            '  finish_run "$status"',
            '  if [ -n "${LOCK_DIR:-}" ]; then',
            '    rmdir "$LOCK_DIR" 2>/dev/null || true',
            "  fi",
            '  rm -f "${STDOUT_TMP:-}" "${STDERR_TMP:-}"',
            "}",
            'on_int() { exit 130; }',
            'on_term() { exit 143; }',
            "trap on_exit EXIT",
            "trap on_int INT",
            "trap on_term TERM",
        ]
    )

    if job.execution.overlap is OverlapPolicy.FORBID:
        lines.extend(
            [
                "",
                f"LOCK_DIR={shell_quote(str(runtime_paths.lock_path))}",
                'if ! mkdir "$LOCK_DIR" 2>/dev/null; then',
                f'  printf "%s\\n" "xcron: skipped overlapping run for {job.qualified_id}" >&2',
                "  exit 0",
                "fi",
            ]
        )

    lines.extend(
        [
            "",
            'STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")',
            'STARTED_EPOCH=$(date +%s)',
            "RUN_STARTED=1",
            "xcron_metric ticks.started",
            "xcron_event job_started",
            f'printf "%s event=job_started run_id=%s qualified_id={job.qualified_id} desired_hash={desired_hash} pid=%s command=%s cwd=%s\\n" "$STARTED_AT" "$RUN_ID" "$$" {shell_quote(job.execution.command)} {shell_quote(job.execution.working_dir)} >&2',
            "STDOUT_TMP=$(mktemp \"${TMPDIR:-/tmp}/xcron.${RUN_ID}.stdout.XXXXXX\")",
            "STDERR_TMP=$(mktemp \"${TMPDIR:-/tmp}/xcron.${RUN_ID}.stderr.XXXXXX\")",
            "set +e",
            f"{shell_quote(job.execution.shell)} -lc {shell_quote(job.execution.command)} >\"$STDOUT_TMP\" 2>\"$STDERR_TMP\"",
            "status=$?",
            "set -e",
            "xcron_replay_stream stdout \"$STDOUT_TMP\"",
            "xcron_replay_stream stderr \"$STDERR_TMP\"",
            'finish_run "$status"',
            'exit "$status"',
            "",
        ]
    )
    return RenderedWrapper(
        job=job,
        desired_hash=desired_hash,
        runtime_paths=runtime_paths,
        content="\n".join(lines),
    )


def write_wrapper(rendered: RenderedWrapper) -> Path:
    """Write a rendered wrapper script to disk and mark it executable."""
    ensure_runtime_dirs(rendered.runtime_paths)
    rendered.runtime_paths.wrapper_path.write_text(rendered.content, encoding="utf-8")
    rendered.runtime_paths.wrapper_path.chmod(0o755)
    LOGGER.info(
        "wrapper_written",
        qualified_id=rendered.job.qualified_id,
        wrapper_path=str(rendered.runtime_paths.wrapper_path),
        stdout_log_path=str(rendered.runtime_paths.stdout_log_path),
        stderr_log_path=str(rendered.runtime_paths.stderr_log_path),
        lock_path=str(rendered.runtime_paths.lock_path),
    )
    return rendered.runtime_paths.wrapper_path


def shell_quote(value: str) -> str:
    """Quote a value for safe POSIX shell embedding."""
    return shlex.quote(value)
