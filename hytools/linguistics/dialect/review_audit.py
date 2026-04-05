"""Centralized review/audit heuristics for dialect classification workflows.

This lives under ``hytools.linguistics.dialect`` so review thresholds and
stage-level audit semantics stay close to the branch classifier rather than
being duplicated across ingestion modules.
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import logging
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - fallback path is deterministic
    yaml = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_DEFAULT_REVIEW_AUDIT_CONFIG: dict[str, Any] = {
    "default": {
        "enabled": True,
        "confidence_threshold": 0.35,
        "score_margin_threshold": 2.0,
    },
    "stages": {
        "metadata_tagger": {
            "queue_source": "ingestion",
        },
        "web_crawler": {
            "queue_source": "crawler",
            "min_armenian_ratio": 0.05,
        },
        "news": {
            "queue_source": "news",
        },
    },
    "priority_mapping": {
        "low_confidence_dialect_classification": 1,
        "source_policy_exception": 2,
        "borderline_crawl_page": 2,
    },
}


def _config_path() -> Path:
    return Path(__file__).with_name("review_heuristics.yaml")


def _deep_merge(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


@lru_cache(maxsize=1)
def _load_review_audit_config_cached() -> dict[str, Any]:
    config = deepcopy(_DEFAULT_REVIEW_AUDIT_CONFIG)
    path = _config_path()
    if yaml is None or not path.exists():
        return config

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("Could not load review heuristics from %s: %s", path, exc)
        return config

    if isinstance(raw, dict):
        _deep_merge(config, raw)
    return config


def load_review_audit_config() -> dict[str, Any]:
    """Return a mutable copy of the centralized review/audit config."""
    return deepcopy(_load_review_audit_config_cached())


def get_stage_review_settings(
    stage: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return merged review settings for a stage.

    Merge order:
    1. Built-in defaults
    2. ``review_heuristics.yaml`` in ``linguistics/dialect``
    3. Stage-specific settings
    4. Caller-provided overrides
    """
    config = load_review_audit_config()
    settings = dict(config.get("default") or {})

    if stage:
        stage_settings = (config.get("stages") or {}).get(stage) or {}
        if isinstance(stage_settings, dict):
            settings.update(stage_settings)

    if isinstance(overrides, dict):
        settings.update({key: value for key, value in overrides.items() if value is not None})

    return settings


def get_review_priority(reason: str, fallback: int) -> int:
    """Return centralized priority for a review reason."""
    mapping = load_review_audit_config().get("priority_mapping") or {}
    try:
        return int(mapping.get(reason, fallback))
    except (TypeError, ValueError):
        return fallback


__all__ = [
    "get_review_priority",
    "get_stage_review_settings",
    "load_review_audit_config",
]