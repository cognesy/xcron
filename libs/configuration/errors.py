"""The one failure this module can produce."""

from __future__ import annotations


class ConfigurationError(Exception):
    """Raised when settings cannot be composed or do not validate.

    `xcfg.ConfigError` never escapes this package. A caller catches xcron's
    error type, so the library underneath can be replaced without touching a
    single ``except`` clause.
    """


__all__ = ["ConfigurationError"]
