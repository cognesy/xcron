#!/usr/bin/env sh
# The deterministic core lane: the dependency graph, then the test suite.
#
# Import Linter runs first because a broken contract explains the test failures
# that follow it, and reading that explanation is cheaper than deriving it from
# a stack trace.
set -eu

uv run lint-imports
uv run pytest "$@"
