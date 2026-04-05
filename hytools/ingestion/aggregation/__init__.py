"""Aggregation: MongoDB -> derived collections (word frequencies, facets, summaries, coverage, timeline)."""

import importlib as _importlib

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "CoverageAnalyzer": ("coverage_analysis", "CoverageAnalyzer"),
    "CoverageGap": ("coverage_analysis", "CoverageGap"),
    "TimelineGenerator": ("timeline_generation", "TimelineGenerator"),
    "TimelineEvent": ("timeline_generation", "TimelineEvent"),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        mod = _importlib.import_module(f".{module_name}", __name__)
        return getattr(mod, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return __all__
