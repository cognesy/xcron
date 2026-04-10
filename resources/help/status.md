# `xcron status`

Inspect actual deployed backend state for the selected project and compare it to desired state.

This is the operator-facing command for spotting `ok`, `missing`, `drift`, `disabled`, `extra`, and backend errors.

Use `--output json` for pipelines and `--fields backend,statuses` when you want a narrower machine-readable payload.
