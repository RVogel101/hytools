"""Helpers for exposing the existing top-level packages through the hytool namespace."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType


def alias_package(alias_name: str, target_name: str) -> ModuleType:
    """Expose *target_name* through the already-created *alias_name* module."""
    target = importlib.import_module(target_name)
    alias_module = sys.modules[alias_name]

    alias_module.__doc__ = getattr(target, "__doc__", None)
    alias_module.__file__ = getattr(target, "__file__", None)
    alias_module.__package__ = alias_name

    if hasattr(target, "__path__"):
        alias_module.__path__ = target.__path__
    if hasattr(target, "__all__"):
        alias_module.__all__ = target.__all__

    for key, value in target.__dict__.items():
        if key in {"__name__", "__loader__", "__spec__", "__package__", "__path__", "__file__"}:
            continue
        alias_module.__dict__.setdefault(key, value)

    return target