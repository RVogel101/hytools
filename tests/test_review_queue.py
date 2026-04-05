from __future__ import annotations

from unittest.mock import MagicMock, patch

from hytools.ingestion._shared.review_queue import (
    PRIORITY_BORDERLINE_DIALECT,
    PRIORITY_SOURCE_POLICY,
    ReviewItem,
    get_review_collection,
    maybe_enqueue_language_review,
)


def test_review_item_supports_cross_stage_metadata():
    item = ReviewItem(
        reason="source_policy_exception",
        priority=PRIORITY_SOURCE_POLICY,
        queue_source="loc",
        stage="loc",
        item_id="item-1",
        title="Library Title",
        source_url="https://example.com/item-1",
        extra={"catalog_source": "loc"},
    )

    payload = item.to_dict()

    assert payload["queue_source"] == "loc"
    assert payload["stage"] == "loc"
    assert payload["item_id"] == "item-1"
    assert payload["pdf_name"] == "Library Title"
    assert payload["run_id"]
    assert payload["extra"] == {"catalog_source": "loc"}


@patch("hytools.ingestion._shared.review_queue.classify_text_classification")
def test_maybe_enqueue_language_review_handles_low_confidence_classification(mock_classify):
    mock_classify.return_value = {
        "label": "inconclusive",
        "confidence": 0.2,
        "western_score": 2.0,
        "eastern_score": 1.8,
        "classical_score": 0.0,
    }
    collection = MagicMock()

    reason = maybe_enqueue_language_review(
        collection,
        stage="loc",
        item_id="item-1",
        text="ա",
        title="Title",
        source_url="https://example.com/item-1",
    )

    assert reason == "low_confidence_dialect_classification"
    payload = collection.insert_one.call_args[0][0]
    assert payload["priority"] == PRIORITY_BORDERLINE_DIALECT
    assert payload["stage"] == "loc"


@patch("hytools.ingestion._shared.review_queue.classify_text_classification")
def test_maybe_enqueue_language_review_handles_rejected_policy_exception(mock_classify):
    mock_classify.return_value = {
        "label": "likely_eastern",
        "confidence": 0.8,
        "western_score": 0.0,
        "eastern_score": 6.0,
        "classical_score": 0.0,
    }
    collection = MagicMock()

    reason = maybe_enqueue_language_review(
        collection,
        stage="loc",
        item_id="item-2",
        text="ա",
        rejected=True,
    )

    assert reason == "source_policy_exception"
    payload = collection.insert_one.call_args[0][0]
    assert payload["priority"] == PRIORITY_SOURCE_POLICY
    assert payload["reason"] == "source_policy_exception"


def test_get_review_collection_prefers_generic_property():
    marker = MagicMock()
    client = MagicMock()
    client.review_queue = marker

    assert get_review_collection(client) is marker
