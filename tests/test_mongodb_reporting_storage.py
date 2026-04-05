from __future__ import annotations

from mongomock import MongoClient

from hytools.integrations.database.mongodb_client import MongoDBCorpusClient


def _make_client():
    client = MongoDBCorpusClient()
    client._db = MongoClient()["reporting_storage_test"]
    return client


def test_save_coverage_gaps_stores_summary_and_itemized_rows():
    client = _make_client()
    report = {
        "summary": {"total_gaps": 250},
        "inventory_coverage": {"total_books": 10},
        "gaps": [
            {"type": "work", "priority": "high", "description": f"gap-{idx}", "recommended_action": "acquire"}
            for idx in range(250)
        ],
    }

    client.save_coverage_gaps(report)

    summary = client.coverage_gaps.find_one({})
    assert summary["total_gap_rows"] == 250
    assert len(summary["gap_preview"]) == 100
    assert client.coverage_gap_items.count_documents({}) == 250


def test_save_acquisition_priorities_stores_counts_and_itemized_rows():
    client = _make_client()
    priorities = {
        "all": [{"priority": "high", "type": "work", "description": f"row-{idx}", "action": "acquire"} for idx in range(150)],
        "high": [{"priority": "high", "type": "work", "description": f"row-{idx}", "action": "acquire"} for idx in range(20)],
        "medium": [],
        "low": [],
        "inventory_coverage": {"total_books": 10},
    }

    client.save_acquisition_priorities(priorities)

    summary = client.acquisition_priorities.find_one({})
    assert summary["all_count"] == 150
    assert summary["high_count"] == 20
    assert len(summary["all_preview"]) == 100
    assert client.acquisition_priority_items.count_documents({"priority_filter": "all"}) == 150
    assert client.acquisition_priority_items.count_documents({"priority_filter": "high"}) == 20