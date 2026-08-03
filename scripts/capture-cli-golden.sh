#!/usr/bin/env sh
# Capture the AXI CLI surface (stdout only) so it can be byte-compared across
# refactor phases. Stderr is dropped deliberately: structlog lines carry
# timestamps and durations that are not part of the contract.
#
#   usage: scripts/capture-cli-golden.sh <output-dir>
#
# Compare two captures with:
#   diff -ru <baseline-dir> <new-dir>
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <output-dir>" >&2
  exit 2
fi

G="$1"
mkdir -p "$G"

# Fixed width keeps Rich help wrapping deterministic across terminals.
export COLUMNS=80

PROJECT=resources/examples/basic
JOB=sync_docs

for command in "" jobs logs hooks metrics validate plan status apply prune inspect init; do
  name=$(echo "${command:-root}" | tr ' ' '_')
  uv run xcron $command --help > "$G/help_$name.txt" 2>/dev/null || true
done

for command in "jobs list" "jobs show" "jobs add" "jobs update" "jobs remove" \
               "jobs enable" "jobs disable" "logs list" "logs clear" \
               "hooks install" "hooks status" "hooks repair" \
               "metrics show" "metrics reset"; do
  name=$(echo "$command" | tr ' ' '_')
  uv run xcron $command --help > "$G/help_$name.txt" 2>/dev/null || true
done

uv run xcron --version > "$G/version.txt" 2>/dev/null || true

# Read-only commands only. status, apply, and prune touch the real host
# scheduler and stay out of the deterministic capture.
for format in toon json; do
  uv run xcron validate --project "$PROJECT" -o "$format" \
    > "$G/validate.$format.txt" 2>/dev/null || true
  uv run xcron plan --project "$PROJECT" -o "$format" \
    > "$G/plan.$format.txt" 2>/dev/null || true
  uv run xcron jobs list --project "$PROJECT" -o "$format" \
    > "$G/jobs_list.$format.txt" 2>/dev/null || true
  uv run xcron jobs show "$JOB" --project "$PROJECT" -o "$format" \
    > "$G/jobs_show.$format.txt" 2>/dev/null || true
done

exit_code() { "$@" >/dev/null 2>&1 && echo 0 || echo $?; }
{
  echo "validate=$(exit_code uv run xcron validate --project "$PROJECT")"
  echo "missing_project=$(exit_code uv run xcron validate --project /nonexistent)"
  echo "bad_fields=$(exit_code uv run xcron jobs list --project "$PROJECT" --fields nope)"
  echo "version=$(exit_code uv run xcron --version)"
} > "$G/exit_codes.txt"

echo "captured $(find "$G" -type f | wc -l | tr -d ' ') files into $G" >&2
