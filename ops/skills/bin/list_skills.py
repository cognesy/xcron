"""List packaged xcron skills and optionally assert their required shape."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SKILLS = ROOT / "resources" / "skills"


def discover() -> list[Path]:
    return sorted(
        path
        for path in SKILLS.glob("*/SKILL.md")
        if path.is_file() and path.parent.name != "skill"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when no packaged skills exist")
    arguments = parser.parse_args(argv)
    skills = discover()
    for skill in skills:
        print(skill.relative_to(ROOT))
    if arguments.check and not skills:
        print("no packaged skills found", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
