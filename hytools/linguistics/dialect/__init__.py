"""Dialect: rule-based WA/EA/classical classification and quantitative dialect metrics."""

import importlib as _importlib

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "DialectClassification": ("branch_dialect_classifier", "DialectClassification"),
    "DistanceWeights": ("dialect_distance", "DistanceWeights"),
    "DistanceReport": ("dialect_distance", "DistanceReport"),
    "compute_component_distance": ("dialect_distance", "compute_component_distance"),
    "get_review_priority": ("review_audit", "get_review_priority"),
    "get_stage_review_settings": ("review_audit", "get_stage_review_settings"),
    "load_review_audit_config": ("review_audit", "load_review_audit_config"),
    "build_starter_variant_pairs": ("variant_pairs_helper", "build_starter_variant_pairs"),
    "save_variant_pairs_json": ("variant_pairs_helper", "save_variant_pairs_json"),
    "to_western": ("dialect_converter", "to_western"),
    "to_eastern": ("dialect_converter", "to_eastern"),
    "to_classical": ("dialect_converter", "to_classical"),
    "to_reform": ("dialect_converter", "to_reform"),
    "DialectPairRecord": ("dialect_pair_metrics", "DialectPairRecord"),
    "DialectMetricsSummary": ("dialect_pair_metrics", "DialectMetricsSummary"),
    "compute_dialect_pair_metrics": ("dialect_pair_metrics", "compute_dialect_pair_metrics"),
    "summarize_records": ("dialect_pair_metrics", "summarize_records"),
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
