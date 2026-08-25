#!/usr/bin/env sh
# The deterministic core lane: package architecture, then behavior.
#
# Providers are independently built namespace-package distributions, so an
# import-graph tool cannot observe their installed boundaries. The workspace
# architecture lane reads the source/metadata ownership directly before the
# complete behavioral suite runs.
set -eu

uv run pytest tests/architecture tests/test_packaging.py
uv run pytest "$@"
