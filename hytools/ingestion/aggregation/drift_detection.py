"""Drift detection for word frequency distributions (WRR data quality)."""
from __future__ import annotations

import logging
from typing import Dict

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


def run(config: dict) -> None:
    from hytools.ingestion._shared.helpers import open_mongodb_client

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for drift detection")

        word_freqs = client.db.word_frequencies
        metadata = client.get_latest_metadata("frequency_aggregator") or {}
        stage = metadata.get("stage")

        # Example logic: compare current word_frequencies to a previous snapshot in metadata.
        # Here we perform a minimal placeholder; production should store distributions in a separate collection.
        words = {}
        for doc in word_freqs.find({}, {"word": 1, "total_count": 1}):
            words[doc["word"]] = float(doc.get("total_count", 0.0))

        # TODO: load baseline from config, previous snapshot, or external source.
        baseline = words
        drift = compare_word_frequencies(baseline, words)

        # Store simple summary
        client.metadata.replace_one(
            {"stage": "drift_detection"},
            {
                "stage": "drift_detection",
                "timestamp": metadata.get("timestamp", None),
                "max_drift": max(drift.values(), default=0),
                "mean_drift": sum(drift.values()) / max(len(drift), 1),
                "samples": len(drift),
            },
            upsert=True,
        )

        print(f"Drift detection completed: {len(drift)} terms analyzed")
