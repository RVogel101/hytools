import contextlib

import pytest
from mongomock import MongoClient

from hytools.ingestion.aggregation import frequency_aggregator, incremental_merge


class FakeClient:
    def __init__(self, db):
        self.db = db

    @property
    def documents(self):
        return self.db["documents"]

    @property
    def metadata(self):
        return self.db["metadata"]

    def get_latest_metadata(self, stage: str):
        return self.db["metadata"].find_one({"stage": stage}, sort=[("timestamp", -1)])

    def replace_one(self, filter_query, update_doc, upsert=False):
        self.db["metadata"].replace_one(filter_query, update_doc, upsert=upsert)

    def close(self):
        return None


@contextlib.contextmanager
def fake_open_mongodb_client(db):
    yield FakeClient(db)


def setup_mongo_data(db):
    first_id = db.documents.insert_one(
        {
            "source": "wikipedia_wa",
            "title": "առաջին",
            "text": "բառ բառ դար",
            "metadata": {
                "wa_score": 6.0,
                "enrichment_date": "2026-01-01T00:00:00+00:00",
                "internal_language_branch": "hye-w",
            },
        }
    ).inserted_id
    second_id = db.documents.insert_one(
        {
            "source": "newspaper",
            "title": "երկրորդ",
            "text": "բառ համ համ",
            "metadata": {
                "wa_score": 4.0,
                "enrichment_date": "2026-01-02T00:00:00+00:00",
                "internal_language_branch": "hye-w",
            },
        }
    ).inserted_id
    return first_id, second_id


def load_word_totals(db):
    return {
        doc["word"]: doc["total_count"]
        for doc in db.word_frequencies.find({}, {"word": 1, "total_count": 1})
    }


def test_hybrid_profile_affects_weights(monkeypatch):
    db = MongoClient()["western_armenian_corpus"]
    setup_mongo_data(db)

    monkeypatch.setattr(
        "hytools.ingestion._shared.helpers.open_mongodb_client",
        lambda cfg: fake_open_mongodb_client(db),
    )

    config = {
        "ingestion": {
            "frequency_aggregator": {
                "hybrid_profile": True,
                "wa_score_weight": 0.5,
            }
        }
    }

    frequency_aggregator.run(config)

    assert load_word_totals(db) == {"բառ": 3.55, "համ": 2.7}

    metadata = db.metadata.find_one({"stage": "frequency_aggregator"})
    assert metadata["hybrid_profile"] is True
    assert metadata["wa_score_weight"] == 0.5
    assert metadata["weights_used"] == {"newspaper": 1.35, "wikipedia_wa": 1.1}


def test_incremental_merge_updates_changed_documents_without_double_counting(monkeypatch):
    db = MongoClient()["western_armenian_corpus"]
    setup_mongo_data(db)

    monkeypatch.setattr(
        "hytools.ingestion._shared.helpers.open_mongodb_client",
        lambda cfg: fake_open_mongodb_client(db),
    )

    config = {
        "ingestion": {
            "frequency_aggregator": {}
        }
    }

    frequency_aggregator.run(config)
    initial = load_word_totals(db)
    assert initial == {"բառ": 3.5, "համ": 3.0}
    assert db.word_frequency_document_state.count_documents({}) == 2
    assert db.word_frequency_source_stats.find_one({"_id": "wikipedia_wa"})["doc_count"] == 1

    db.documents.insert_one(
        {
            "source": "wikipedia_wa",
            "title": "երրորդ",
            "text": "համ",
            "metadata": {"wa_score": 6.0, "enrichment_date": "2026-02-01T00:00:00+00:00"},
        }
    )
    incremental_merge.run(config)

    updated = load_word_totals(db)
    assert updated == {"բառ": 3.5, "համ": 4.0}

    incremental_merge.run(config)

    rerun = load_word_totals(db)
    assert rerun == updated
    merge_meta = db.metadata.find_one({"stage": "incremental_merge"})
    assert merge_meta["docs_processed"] == 0


def test_incremental_merge_replaces_existing_document_contribution(monkeypatch):
    db = MongoClient()["western_armenian_corpus"]
    first_id, _second_id = setup_mongo_data(db)

    monkeypatch.setattr(
        "hytools.ingestion._shared.helpers.open_mongodb_client",
        lambda cfg: fake_open_mongodb_client(db),
    )

    config = {"ingestion": {"frequency_aggregator": {}}}

    frequency_aggregator.run(config)

    db.documents.update_one(
        {"_id": first_id},
        {
            "$set": {
                "text": "դար դար դար",
                "metadata.enrichment_date": "2026-02-03T00:00:00+00:00",
            }
        },
    )

    incremental_merge.run(config)

    updated = load_word_totals(db)
    assert updated == {"դար": 3.0, "համ": 3.0}

    stored_state = db.word_frequency_document_state.find_one({"_id": first_id})
    assert stored_state["token_counts"] == {"դար": 3}


def test_incremental_merge_reconciles_deleted_documents(monkeypatch):
    db = MongoClient()["western_armenian_corpus"]
    _first_id, second_id = setup_mongo_data(db)

    monkeypatch.setattr(
        "hytools.ingestion._shared.helpers.open_mongodb_client",
        lambda cfg: fake_open_mongodb_client(db),
    )

    config = {"ingestion": {"frequency_aggregator": {}}}

    frequency_aggregator.run(config)
    db.documents.delete_one({"_id": second_id})

    incremental_merge.run(config)

    assert load_word_totals(db) == {"բառ": 2.0}
    assert db.word_frequency_document_state.count_documents({}) == 1
    assert db.word_frequency_source_stats.count_documents({}) == 1
    assert db.word_frequency_source_stats.find_one({"_id": "newspaper"}) is None

    merge_meta = db.metadata.find_one({"stage": "incremental_merge"})
    assert merge_meta["docs_processed"] == 0
    assert merge_meta["removed_docs_processed"] == 1
    assert merge_meta["note"] == "reconciled_stale_document_state"


def test_incremental_merge_reconciles_documents_that_leave_branch_scope(monkeypatch):
    db = MongoClient()["western_armenian_corpus"]
    _first_id, second_id = setup_mongo_data(db)

    monkeypatch.setattr(
        "hytools.ingestion._shared.helpers.open_mongodb_client",
        lambda cfg: fake_open_mongodb_client(db),
    )

    config = {
        "ingestion": {
            "frequency_aggregator": {
                "internal_language_branch": "hye-w",
            }
        }
    }

    frequency_aggregator.run(config)

    db.documents.update_one(
        {"_id": second_id},
        {
            "$set": {
                "metadata.internal_language_branch": "hye-e",
                "metadata.enrichment_date": "2026-02-05T00:00:00+00:00",
            }
        },
    )

    incremental_merge.run(config)

    assert load_word_totals(db) == {"բառ": 2.0}
    assert db.word_frequency_document_state.count_documents({}) == 1
    assert db.word_frequency_document_state.find_one({"_id": second_id}) is None

    merge_meta = db.metadata.find_one({"stage": "incremental_merge"})
    assert merge_meta["removed_docs_processed"] == 1
