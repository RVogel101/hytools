from __future__ import annotations

from unittest.mock import MagicMock

from hytools.ingestion.review import list_review_items, mark_reviewed


def test_list_review_items_filters_and_sorts():
    collection = MagicMock()
    client = MagicMock()
    client.review_queue = collection
    collection.find.return_value.sort.return_value.limit.return_value = [
        {
            "run_id": "review-1",
            "priority": 1,
            "stage": "news",
            "reason": "low_confidence_dialect_classification",
            "reviewed": False,
        }
    ]

    items = list_review_items(client, stage="news", include_reviewed=False, limit=5)

    assert items[0]["run_id"] == "review-1"
    collection.find.assert_called_once_with({"stage": "news", "reviewed": {"$ne": True}})


def test_mark_reviewed_updates_matching_item():
    collection = MagicMock()
    collection.update_one.return_value.modified_count = 1
    client = MagicMock()
    client.review_queue = collection

    updated = mark_reviewed(client, "review-1", notes="handled")

    assert updated == 1
    collection.update_one.assert_called_once()