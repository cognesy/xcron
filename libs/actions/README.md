# Actions

Actions are the primary use-case boundary in xcron.

These modules are now import shims only. Each re-exports one capability's
public surface from `libs/capabilities/` so pre-refactor import paths keep
working; they are scheduled for removal and must not grow logic.
