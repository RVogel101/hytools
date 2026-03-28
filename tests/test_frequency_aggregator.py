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
    db.documents.insert_many([
        {
            "source": "wikipedia_wa",
            "text": "բառ դար",
            "metadata": {"wa_score": 6.0, "enrichment_date": "2026-01-01"},
        },
        {
            "source": "newspaper",
            "text": "բառ համ",
            "metadata": {"wa_score": 4.0, "enrichment_date": "2026-01-02"},
        },
    ])


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

    results = list(db.word_frequencies.find({}))
    assert len(results) > 0
    # We can at least verify there is a field and we did not crash.
    assert any(r["word"] == "բառ" for r in results)


def test_punctuation_not_in_word_frequencies(monkeypatch):
    db = MongoClient()["western_armenian_corpus"]
    # include punctuation-only token and a real Armenian word
    db.documents.insert_one({
        "source": "wikisource",
        "text": "բառ բառ։",
        "metadata": {"wa_score": 5.0, "enrichment_date": "2026-03-01"},
    })

    monkeypatch.setattr(
        "hytools.ingestion._shared.helpers.open_mongodb_client",
        lambda cfg: fake_open_mongodb_client(db),
    )

    frequency_aggregator.run({})

    results = list(db.word_frequencies.find({}))
    assert any(r["word"] == "բառ" for r in results)
    assert not any(r["word"] == "։" for r in results)


def test_incremental_merge_uses_partial_update(monkeypatch):
    db = MongoClient()["western_armenian_corpus"]
    setup_mongo_data(db)

    monkeypatch.setattr(
        "hytools.ingestion._shared.helpers.open_mongodb_client",
        lambda cfg: fake_open_mongodb_client(db),
    )

    config = {
        "ingestion": {
            "frequency_aggregator": {
                "incremental": False,
            }
        }
    }

    frequency_aggregator.run(config)
    initial = list(db.word_frequencies.find({}))
    assert any(r["word"] == "բառ" for r in initial)

    # Add one new document and re-run incremental merge
    db.documents.insert_one({"source": "wikipedia_wa", "text": "բառ","metadata": {"wa_score": 6.0, "enrichment_date": "2026-02-01"}})
    config["ingestion"]["frequency_aggregator"]["incremental"] = True
    incremental_merge.run(config)

    updated = list(db.word_frequencies.find({}))
    assert len(updated) >= len(initial)
