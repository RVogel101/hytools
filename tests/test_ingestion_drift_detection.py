from __future__ import annotations

from hytools.ingestion.aggregation.drift_detection import _build_drift_alert_doc


def test_build_drift_alert_doc_captures_baseline_and_alert_state():
    alert = _build_drift_alert_doc(
        baseline_snapshot={"timestamp": "2026-04-04T00:00:00Z", "word_count": 5000},
        max_drift=0.12,
        mean_drift=0.04,
        top_drift=[("բառ", 0.12)],
        threshold=0.05,
        status="alert",
    )

    assert alert["alert"] is True
    assert alert["baseline_word_count"] == 5000
    assert alert["top_drifted_words"][0]["word"] == "բառ"