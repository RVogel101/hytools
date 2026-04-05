"""Integration tests for aggregation pipeline gates.

Gate 2: incremental_merge delta idempotency proof.
Gate 6: deterministic corpus_export proof.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import tempfile
from pathlib import Path

import pytest
from mongomock import MongoClient

from hytools.ingestion.aggregation import corpus_export, frequency_aggregator, incremental_merge


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

class FakeClient:
    """Minimal MongoDB client backed by mongomock."""

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


def _seed_documents(db, count: int = 3):
    """Insert a small set of Armenian-text documents and return their IDs."""
    docs = [
        {
            "source": "wikipedia_wa",
            "title": "\u0561\u057c\u0561\u057b\u056b\u0576",
            "text": "\u0562\u0561\u057c \u0562\u0561\u057c \u0564\u0561\u0580",
            "metadata": {
                "wa_score": 6.0,
                "enrichment_date": "2026-01-01T00:00:00+00:00",
                "internal_language_branch": "hye-w",
            },
        },
        {
            "source": "newspaper",
            "title": "\u0565\u0580\u056f\u0580\u0578\u0580\u0564",
            "text": "\u0570\u0561\u0574 \u0570\u0561\u0574 \u0564\u0561\u0580",
            "metadata": {
                "wa_score": 4.0,
                "enrichment_date": "2026-01-02T00:00:00+00:00",
                "internal_language_branch": "hye-w",
            },
        },
        {
            "source": "wikisource",
            "title": "\u0565\u057c\u0580\u0578\u0580\u0564",
            "text": "\u0563\u056b\u0580\u0584 \u0563\u056b\u0580\u0584 \u0563\u056b\u0580\u0584",
            "metadata": {
                "wa_score": 5.5,
                "enrichment_date": "2026-01-03T00:00:00+00:00",
                "internal_language_branch": "hye-w",
            },
        },
    ]
    ids = []
    for doc in docs[:count]:
        ids.append(db.documents.insert_one(doc).inserted_id)
    return ids


def _load_word_totals(db):
    return {
        doc["word"]: doc["total_count"]
        for doc in db.word_frequencies.find({}, {"word": 1, "total_count": 1})
    }


# ---------------------------------------------------------------------------
# Gate 2 — incremental_merge full rebuild → delta → idempotent re-run
# ---------------------------------------------------------------------------

class TestIncrementalMergeDeltaIdempotency:
    """Prove that a full rebuild followed by delta ingests is idempotent."""

    def test_full_rebuild_then_delta_then_rerun_is_idempotent(self, monkeypatch):
        db = MongoClient()["integration_test"]
        ids = _seed_documents(db, count=2)

        monkeypatch.setattr(
            "hytools.ingestion._shared.helpers.open_mongodb_client",
            lambda cfg: fake_open_mongodb_client(db),
        )
        config = {"ingestion": {"frequency_aggregator": {}}}

        # Step 1: full rebuild via frequency_aggregator
        frequency_aggregator.run(config)
        snapshot_after_full = _load_word_totals(db)
        assert snapshot_after_full, "Full rebuild should produce word totals"

        # Step 2: add a new document (delta)
        db.documents.insert_one(
            {
                "source": "wikisource",
                "title": "delta_doc",
                "text": "\u0576\u0578\u0580 \u0576\u0578\u0580",
                "metadata": {
                    "wa_score": 5.0,
                    "enrichment_date": "2026-02-01T00:00:00+00:00",
                    "internal_language_branch": "hye-w",
                },
            }
        )
        incremental_merge.run(config)
        snapshot_after_delta = _load_word_totals(db)
        assert "\u0576\u0578\u0580" in snapshot_after_delta, "Delta doc's token should appear"

        # Step 3: re-run with NO changes — must be idempotent
        incremental_merge.run(config)
        snapshot_after_rerun = _load_word_totals(db)
        assert snapshot_after_rerun == snapshot_after_delta, (
            "Re-running incremental_merge without changes must not alter totals"
        )

        merge_meta = db.metadata.find_one({"stage": "incremental_merge"})
        assert merge_meta["docs_processed"] == 0, (
            "No documents should be processed on idempotent re-run"
        )

    def test_delete_then_rerun_reconciles_correctly(self, monkeypatch):
        db = MongoClient()["integration_test_del"]
        ids = _seed_documents(db, count=3)

        monkeypatch.setattr(
            "hytools.ingestion._shared.helpers.open_mongodb_client",
            lambda cfg: fake_open_mongodb_client(db),
        )
        config = {"ingestion": {"frequency_aggregator": {}}}

        frequency_aggregator.run(config)
        snapshot_before = _load_word_totals(db)

        # Delete one document
        db.documents.delete_one({"_id": ids[1]})
        incremental_merge.run(config)
        snapshot_after = _load_word_totals(db)

        # The deleted doc's unique tokens should be gone or reduced
        merge_meta = db.metadata.find_one({"stage": "incremental_merge"})
        assert merge_meta["removed_docs_processed"] >= 1

        # Idempotent re-run
        incremental_merge.run(config)
        snapshot_rerun = _load_word_totals(db)
        assert snapshot_rerun == snapshot_after


# ---------------------------------------------------------------------------
# Gate 6 — deterministic corpus_export
# ---------------------------------------------------------------------------

class TestDeterministicExport:
    """Prove that exporting the same corpus twice produces identical output."""

    def test_release_partition_is_deterministic(self):
        """Same rows + same seed → identical partition assignment."""
        rows = [
            {"content_hash": f"hash_{i}", "id": str(i), "text": f"text {i}", "source": "test"}
            for i in range(50)
        ]
        seed = "determinism-gate-test"

        result_a = corpus_export.partition_release_rows(
            rows,
            split_seed=seed,
            train_ratio=0.8,
            validation_ratio=0.1,
            test_ratio=0.1,
        )
        result_b = corpus_export.partition_release_rows(
            rows,
            split_seed=seed,
            train_ratio=0.8,
            validation_ratio=0.1,
            test_ratio=0.1,
        )

        for split in ("train", "validation", "test"):
            assert len(result_a[split]) == len(result_b[split]), f"{split} count mismatch"
            for a, b in zip(result_a[split], result_b[split]):
                assert a == b, f"Row mismatch in {split}"

    def test_release_partition_different_seed_differs(self):
        """Different seeds should produce different splits."""
        rows = [
            {"content_hash": f"hash_{i}", "id": str(i), "text": f"text {i}", "source": "test"}
            for i in range(100)
        ]
        result_a = corpus_export.partition_release_rows(
            rows,
            split_seed="seed-alpha",
            train_ratio=0.8,
            validation_ratio=0.1,
            test_ratio=0.1,
        )
        result_b = corpus_export.partition_release_rows(
            rows,
            split_seed="seed-beta",
            train_ratio=0.8,
            validation_ratio=0.1,
            test_ratio=0.1,
        )
        # With 100 rows and different seeds, the splits should differ
        train_hashes_a = {r["content_hash"] for r in result_a["train"]}
        train_hashes_b = {r["content_hash"] for r in result_b["train"]}
        assert train_hashes_a != train_hashes_b, "Different seeds should produce different splits"

    def test_release_partition_ratios_sum_must_be_one(self):
        rows = [{"content_hash": "h", "id": "1"}]
        with pytest.raises(ValueError, match="sum to 1.0"):
            corpus_export.partition_release_rows(
                rows,
                split_seed="x",
                train_ratio=0.5,
                validation_ratio=0.1,
                test_ratio=0.1,
            )

    def test_release_parquet_artifacts_are_byte_identical_for_same_corpus(self, monkeypatch, tmp_path):
        rows = [
            {"id": "3", "content_hash": "ccc", "normalized_content_hash": "ccc", "source": "beta", "text": "three"},
            {"id": "1", "content_hash": "aaa", "normalized_content_hash": "aaa", "source": "alpha", "text": "one"},
            {"id": "2", "content_hash": "bbb", "normalized_content_hash": "bbb", "source": "alpha", "text": "two"},
        ]

        def fake_iter_documents(_config, _dialect_filter=None):
            return iter(rows)

        monkeypatch.setattr(corpus_export, "_iter_documents", fake_iter_documents)
        monkeypatch.setattr(corpus_export, "_utcnow_iso", lambda: "2026-01-01T00:00:00+00:00")

        config = {
            "export": {
                "release": {
                    "dataset_name": "hytools-determinism-test",
                    "dataset_version": "0.0.1",
                    "split_seed": "stable-seed",
                    "train_ratio": 0.67,
                    "validation_ratio": 0.0,
                    "test_ratio": 0.33,
                    "include_huggingface": False,
                    "include_full_parquet": True,
                    "include_dataset_card": False,
                    "include_checksums": False,
                }
            }
        }

        first_root = tmp_path / "release-one"
        second_root = tmp_path / "release-two"
        corpus_export.build_release(config, output_path=first_root)
        corpus_export.build_release(config, output_path=second_root)

        first_full = first_root / "corpus.parquet"
        second_full = second_root / "corpus.parquet"
        first_train = first_root / "splits" / "train.parquet"
        second_train = second_root / "splits" / "train.parquet"
        first_test = first_root / "splits" / "test.parquet"
        second_test = second_root / "splits" / "test.parquet"

        assert first_full.read_bytes() == second_full.read_bytes()
        assert first_train.read_bytes() == second_train.read_bytes()
        assert first_test.read_bytes() == second_test.read_bytes()
