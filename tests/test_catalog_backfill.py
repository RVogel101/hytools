from __future__ import annotations

from contextlib import contextmanager

import hytools.ingestion.acquisition.hathitrust as hathitrust
from hytools.ingestion.discovery.book_inventory import BookAuthor, BookInventoryEntry, ContentType, CoverageStatus
import hytools.ingestion.discovery.catalog_backfill as catalog_backfill


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, limit):
        return self.rows[:limit]


class FakeCollection:
    def __init__(self, rows):
        self.rows = rows

    def find(self, *_args, **_kwargs):
        return FakeCursor(self.rows)


class FakeClient:
    def __init__(self, rows):
        self.acquisition_priority_items = FakeCollection(rows)
        self.logged_runs = []

    def log_pipeline_run(self, stage, status, details):
        self.logged_runs.append((stage, status, details))


class FakeInventoryManager:
    def __init__(self, books):
        self.books = books
        self.saved = False

    def cleanup_titles(self):
        return {
            "total_books": len(self.books),
            "normalized_titles": 0,
            "flagged_implausible_titles": 0,
            "cleared_implausible_flags": 0,
        }

    def find_by_title(self, title, fuzzy=False):
        lowered = title.lower()
        matches = [book for book in self.books if book.title.lower() == lowered]
        if matches or not fuzzy:
            return matches
        return [book for book in self.books if lowered in book.title.lower()]

    def save_inventory(self):
        self.saved = True
        return len(self.books)


def test_source_query_uses_title_for_nayiri():
    row_meta = {
        "title": "Վաղ տես",
        "authors": "Օ. Թունեան",
        "year": 1903,
        "query": "Վաղ տես Օ. Թունեան 1903",
    }

    query = catalog_backfill._source_query("nayiri", row_meta, {"source": "nayiri", "query": row_meta["query"]})

    assert query == "Վաղ տես"


def test_search_source_disables_hathitrust_seed_catalog(monkeypatch):
    observed = {}

    def fake_search_items(queries, max_per_query=0, include_seed_list=True):
        observed["queries"] = queries
        observed["max_per_query"] = max_per_query
        observed["include_seed_list"] = include_seed_list
        return {}

    monkeypatch.setattr(hathitrust, "search_items", fake_search_items)

    catalog_backfill._search_source(None, "hathitrust", "Վաղ տես", {"title": "Վաղ տես"}, max_per_query=7)

    assert observed == {
        "queries": ["Վաղ տես"],
        "max_per_query": 7,
        "include_seed_list": False,
    }


def test_run_targeted_backfill_updates_inventory_and_logs_run(monkeypatch):
    book = BookInventoryEntry(
        title="Վաղ տես",
        authors=[BookAuthor(name="Օ. Թունեան")],
        coverage_status=CoverageStatus.MISSING,
        content_type=ContentType.NOVEL,
    )
    manager = FakeInventoryManager([book])
    rows = [
        {
            "priority": "high",
            "type": "work",
            "description": "Missing work: 'Վաղ տես' by Օ. Թունեան (1903)",
            "acquisition_query": "Վաղ տես Օ. Թունեան 1903",
            "source_targets": [
                {"source": "loc", "query": "Վաղ տես Օ. Թունեան 1903"},
                {"source": "archive_org", "query": "Վաղ տես Օ. Թունեան 1903"},
            ],
            "metadata": {"title": "Վաղ տես", "authors": "Օ. Թունեան", "year": 1903},
            "impact_score": 0.9,
        }
    ]
    client = FakeClient(rows)
    saved_catalogs = []
    search_calls = []

    @contextmanager
    def fake_open_mongodb_client(_config):
        yield client

    def fake_inventory_manager(*_args, **_kwargs):
        return manager

    def fake_search_source(_client, source, query, row_meta, max_per_query):
        search_calls.append((source, query, row_meta.copy(), max_per_query))
        return {f"{source}:1": {"title": row_meta["title"]}}

    def fake_save_catalog(_client, source, catalog):
        saved_catalogs.append((source, catalog))
        return len(catalog)

    monkeypatch.setattr(catalog_backfill, "BookInventoryManager", fake_inventory_manager)
    monkeypatch.setattr(catalog_backfill, "open_mongodb_client", fake_open_mongodb_client)
    monkeypatch.setattr(catalog_backfill, "_search_source", fake_search_source)
    monkeypatch.setattr(catalog_backfill, "save_catalog_to_mongodb", fake_save_catalog)

    summary = catalog_backfill.run_targeted_backfill(
        {"database": {"mongodb_uri": "mongodb://example", "mongodb_database": "hytools_test"}},
        limit=5,
        max_per_query=3,
        sources=("loc", "archive_org"),
    )

    assert summary["rows_loaded"] == 1
    assert summary["rows_processed"] == 1
    assert summary["catalog_items_upserted"] == {"loc": 1, "archive_org": 1}
    assert summary["inventory_updates"] == {"loc": 1, "archive_org": 1}
    assert manager.saved is True
    assert book.loc_control_number == "loc:1"
    assert book.archive_org_id == "archive_org:1"
    assert [call[0] for call in search_calls] == ["loc", "archive_org"]
    assert saved_catalogs[0][0] == "loc"
    assert client.logged_runs[0][0] == "catalog_backfill"


def test_run_targeted_backfill_parses_description_when_metadata_missing(monkeypatch):
    manager = FakeInventoryManager([])
    rows = [
        {
            "priority": "high",
            "type": "work",
            "description": "Missing work: 'Վաղ տես' by Օ. Թունեան (1903)",
            "acquisition_query": "",
            "source_targets": [{"source": "loc", "query": ""}],
            "metadata": {},
            "impact_score": 0.9,
        }
    ]
    client = FakeClient(rows)
    observed = {}

    @contextmanager
    def fake_open_mongodb_client(_config):
        yield client

    def fake_inventory_manager(*_args, **_kwargs):
        return manager

    def fake_search_source(_client, source, query, row_meta, max_per_query):
        observed["source"] = source
        observed["query"] = query
        observed["row_meta"] = row_meta.copy()
        observed["max_per_query"] = max_per_query
        return {}

    monkeypatch.setattr(catalog_backfill, "BookInventoryManager", fake_inventory_manager)
    monkeypatch.setattr(catalog_backfill, "open_mongodb_client", fake_open_mongodb_client)
    monkeypatch.setattr(catalog_backfill, "_search_source", fake_search_source)

    summary = catalog_backfill.run_targeted_backfill(
        {"database": {"mongodb_uri": "mongodb://example", "mongodb_database": "hytools_test"}},
        limit=5,
        max_per_query=2,
        sources=("loc",),
    )

    assert summary["rows_processed"] == 1
    assert observed["source"] == "loc"
    assert observed["query"] == "Վաղ տես Օ. Թունեան 1903"
    assert observed["row_meta"] == {
        "title": "Վաղ տես",
        "authors": "Օ. Թունեան",
        "year": 1903,
        "query": "Վաղ տես Օ. Թունեան 1903",
    }