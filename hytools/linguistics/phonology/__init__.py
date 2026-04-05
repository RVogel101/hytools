"""Western Armenian phonology: letter-to-IPA, pronunciation, and letter data."""

import importlib as _importlib

__all__ = ["phonetics", "letter_data"]


def __getattr__(name: str):
    if name in __all__:
        return _importlib.import_module(f".{name}", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return __all__
