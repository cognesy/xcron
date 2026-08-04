"""Layered settings for one xcron invocation.

This package answers a single question — *what are the effective settings for
this run?* — and answers it once, at the composition root. Everything below the
runtime receives typed values; nothing below the runtime reads a settings
environment variable or re-derives a default.

The layering mechanism is delegated to `xcfg`. The model, the packaged
defaults, and the environment-variable contract stay here, because they are
xcron's promises to its users rather than the library's.

Workspace identity (``XCRON_HOME``, ``XCRON_PROJECT``) is deliberately *not* a
setting and is not read here: it selects which configuration files are read, so
it cannot itself come from one. It belongs to
:mod:`xcron.capabilities.workspace`.
"""
