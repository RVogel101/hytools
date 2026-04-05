"""Hytools root namespace package."""

import importlib as _importlib

_SUBPACKAGES = ["augmentation", "cleaning", "cloud", "core_contracts", "ingestion", "integrations", "linguistics", "ocr"]

__all__ = _SUBPACKAGES


def __getattr__(name: str):
    if name in _SUBPACKAGES:
        return _importlib.import_module(f".{name}", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return __all__
