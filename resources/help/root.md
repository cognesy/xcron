# xcron

Manage one project schedule under `resources/schedules/` against native OS schedulers.

Authoritative runtime help for xcron lives under `resources/help/`.

Use the top-level command when you need to discover the current CLI surface:

- `xcron validate` checks one selected manifest without touching the scheduler.
- `xcron plan` previews scheduler changes from desired state and local xcron state.
- `xcron status` compares desired state to actual deployed backend state.
- `xcron jobs ...` edits YAML only; `xcron apply` is the step that reconciles backend state.
