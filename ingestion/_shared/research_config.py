"""Centralized configuration for the author/book research pipeline.

Provides corpus scope (exclude_dirs, exclude_sources for MongoDB),
error thresholds, and defaults so extraction and analysis use consistent settings.
"""

from __future__ import annotations

# Defaults: exclude augmented and logs from corpus scope; fail if >10% documents error.
RESEARCH_DEFAULTS: dict = {
    "exclude_dirs": ["augmented", "logs", "__pycache__"],
    "exclude_sources": ["augmented"],  # When reading from MongoDB, skip these source values
    "error_threshold_pct": 10.0,
    "metadata_patterns": ["*.json", "*.jsonl"],
}


def get_research_config(config: dict | None) -> dict:
    """Return research pipeline config merged with defaults.

    config["research"] can override exclude_dirs, exclude_sources, error_threshold_pct.
    """
    base = dict(RESEARCH_DEFAULTS)
    research = (config or {}).get("research") or {}
    if isinstance(research, dict):
        if "exclude_dirs" in research:
            base["exclude_dirs"] = list(research["exclude_dirs"])
        if "exclude_sources" in research:
            base["exclude_sources"] = list(research["exclude_sources"])
        if "error_threshold_pct" in research:
            base["error_threshold_pct"] = float(research["error_threshold_pct"])
        if "metadata_patterns" in research:
            base["metadata_patterns"] = list(research["metadata_patterns"])
    return base
