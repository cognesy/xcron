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
        "RUN_STARTED=0",
        "FINISH_REPORTED=0",
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
            f'    printf "%s event=job_finished qualified_id={job.qualified_id} desired_hash={desired_hash} exit_code=%s duration_seconds=%s\\n" "$FINISHED_AT" "$status" "$DURATION_SECONDS" >&2',
            "  fi",
            "}",
            "on_exit() {",
            '  status=$?',
            '  finish_run "$status"',
            '  if [ -n "${LOCK_DIR:-}" ]; then',
            '    rmdir "$LOCK_DIR" 2>/dev/null || true',
            "  fi",
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
            f'printf "%s event=job_started qualified_id={job.qualified_id} desired_hash={desired_hash} pid=%s\\n" "$STARTED_AT" "$$" >&2',
            f"{shell_quote(job.execution.shell)} -lc {shell_quote(job.execution.command)}",
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
