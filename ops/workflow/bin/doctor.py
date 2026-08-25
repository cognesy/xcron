"""Run the non-mutating readiness checks for repository operations."""

from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]
CHECKS = (
    ("operations catalogue", ["just", "validate"]),
    ("xcron CLI", ["uv", "run", "xcron", "--version"]),
)


def main() -> int:
    for name, command in CHECKS:
        print(f"checking {name}", flush=True)
        completed = subprocess.run(command, cwd=ROOT, check=False)
        if completed.returncode:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
