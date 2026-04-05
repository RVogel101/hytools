"""Drift detection for word frequency distributions (WRR data quality).

Compares current word frequencies to the most recent baseline snapshot
stored in the ``word_frequency_baselines`` collection. On first run (no
baseline exists), stores the current distribution as baseline and reports
zero drift. Subsequent runs compare against the stored baseline, store
the drift report, then rotate the current distribution into a new baseline.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _compute_relative_frequencies(freqs: Dict[str, float]) -> Dict[str, float]:
    total = sum(freqs.values())
    if total <= 0:
        return {}
    return {word: count / total for word, count in freqs.items()}


def compare_word_frequencies(base: Dict[str, float], current: Dict[str, float], top_n: int = 100) -> Dict[str, float]:
    """Compute simple symmetric KL-like divergence for top words in both distributions."""
    base_freq = _compute_relative_frequencies(base)
    current_freq = _compute_relative_frequencies(current)
    words = set(list(base_freq.keys())[:top_n] + list(current_freq.keys())[:top_n])
    drift_scores: Dict[str, float] = {}
    for word in words:
        b = base_freq.get(word, 1e-9)
        c = current_freq.get(word, 1e-9)
        drift_scores[word] = abs(b - c)
    logger.info("Drift detection: top word drift calculation done for %d words", len(drift_scores))
    return drift_scores


def _load_current_frequencies(client) -> Dict[str, float]:
    """Load current word frequencies from the word_frequencies collection."""
    words: Dict[str, float] = {}
    for doc in client.db.word_frequencies.find({}, {"word": 1, "total_count": 1}):
        words[doc["word"]] = float(doc.get("total_count", 0.0))
    return words


def _load_baseline_snapshot(client) -> dict[str, Any] | None:
    """Load the most recent baseline snapshot. Returns None if no baseline exists."""
    baseline_col = client.db["word_frequency_baselines"]
    return baseline_col.find_one(sort=[("timestamp", -1)])


def _save_baseline(client, frequencies: Dict[str, float]) -> None:
    """Store a new baseline snapshot (top 5000 words to keep size manageable)."""
    baseline_col = client.db["word_frequency_baselines"]
    top_words = dict(sorted(frequencies.items(), key=lambda x: -x[1])[:5000])
    baseline_col.insert_one({
        "timestamp": datetime.now(timezone.utc),
        "word_count": len(top_words),
        "frequencies": top_words,
    })
    logger.info("Stored new baseline with %d entries", len(top_words))


def _build_drift_alert_doc(
    *,
    baseline_snapshot: dict[str, Any] | None,
    max_drift: float,
    mean_drift: float,
    top_drift: list[tuple[str, float]],
    threshold: float,
    status: str,
) -> dict[str, Any]:
    generated = datetime.now(timezone.utc)
    return {
        "stage": "drift_detection",
        "generated": generated,
        "status": status,
        "threshold": threshold,
        "max_drift": max_drift,
        "mean_drift": mean_drift,
        "alert": max_drift > threshold,
        "baseline_timestamp": (baseline_snapshot or {}).get("timestamp"),
        "baseline_word_count": int((baseline_snapshot or {}).get("word_count", 0) or 0),
        "top_drifted_words": [{"word": w, "drift": d} for w, d in top_drift],
    }


def run(config: dict) -> None:
    from hytools.ingestion._shared.helpers import open_mongodb_client

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for drift detection")

        current = _load_current_frequencies(client)
        if not current:
            logger.warning("No word frequencies found; skipping drift detection")
            return

        baseline_snapshot = _load_baseline_snapshot(client)
        baseline = None if baseline_snapshot is None else baseline_snapshot.get("frequencies", {})
        if baseline_snapshot is None:
            logger.info("No baseline found — storing current distribution as first baseline")
            _save_baseline(client, current)
            client.metadata.replace_one(
                {"stage": "drift_detection"},
                {
                    "stage": "drift_detection",
                    "timestamp": datetime.now(timezone.utc),
                    "max_drift": 0.0,
                    "mean_drift": 0.0,
                    "samples": 0,
                    "note": "first_run_baseline_created",
                },
                upsert=True,
            )
            if hasattr(client, "save_drift_alert"):
                client.save_drift_alert(
                    _build_drift_alert_doc(
                        baseline_snapshot=None,
                        max_drift=0.0,
                        mean_drift=0.0,
                        top_drift=[],
                        threshold=float(config.get("drift_threshold", 0.05)),
                        status="baseline_created",
                    )
                )
            print("Drift detection: first baseline created (0 drift)")
            return

        drift = compare_word_frequencies(baseline, current)
        max_drift = max(drift.values(), default=0.0)
        mean_drift = sum(drift.values()) / max(len(drift), 1)

        # Top drifted words for diagnostics
        top_drift = sorted(drift.items(), key=lambda x: -x[1])[:20]

        client.metadata.replace_one(
            {"stage": "drift_detection"},
            {
                "stage": "drift_detection",
                "timestamp": datetime.now(timezone.utc),
                "max_drift": max_drift,
                "mean_drift": mean_drift,
                "samples": len(drift),
                "top_drifted_words": [{"word": w, "drift": d} for w, d in top_drift],
            },
            upsert=True,
        )

        if hasattr(client, "save_drift_alert"):
            client.save_drift_alert(
                _build_drift_alert_doc(
                    baseline_snapshot=baseline_snapshot,
                    max_drift=max_drift,
                    mean_drift=mean_drift,
                    top_drift=top_drift,
                    threshold=float(config.get("drift_threshold", 0.05)),
                    status="alert" if max_drift > float(config.get("drift_threshold", 0.05)) else "ok",
                )
            )

        # Rotate baseline: save current as new baseline
        _save_baseline(client, current)

        threshold = float(config.get("drift_threshold", 0.05))
        if max_drift > threshold:
            logger.warning(
                "DRIFT ALERT: max_drift=%.4f > threshold=%.4f — check data quality",
                max_drift, threshold,
            )

        print(f"Drift detection completed: {len(drift)} terms analyzed, max_drift={max_drift:.4f}, mean={mean_drift:.4f}")
