"""Core domain contracts for migration-safe integration."""

import importlib as _importlib

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "normalize_text_for_hash": ("hashing", "normalize_text_for_hash"),
    "sha256_normalized": ("hashing", "sha256_normalized"),
    "DocumentRecord": ("types", "DocumentRecord"),
    "LexiconEntry": ("types", "LexiconEntry"),
    "PhoneticResult": ("types", "PhoneticResult"),
}

# `DialectTag` is legacy; new workflows should use `internal_language_code` /
# `internal_language_branch` exclusively. Keep type in source for backward
# compatibility within the module, but do not export by default.
__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        mod = _importlib.import_module(f".{module_name}", __name__)
        return getattr(mod, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return __all__
