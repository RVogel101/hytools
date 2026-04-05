"""Incremental merge stage: apply document deltas to frequency state."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _get_last_merge_marker(client):
    merge_meta = client.get_latest_metadata("incremental_merge") or {}
    marker = merge_meta.get("last_enrichment_date")
    if marker:
        return marker

    rebuild_meta = client.get_latest_metadata("frequency_aggregator") or {}
    return rebuild_meta.get("last_enrichment_date")


def _build_query(base_query: dict, last_marker: str | None) -> dict:
    query = dict(base_query)
    if not last_marker:
        query["metadata.enrichment_date"] = {"$exists": True}
        return query

    query["metadata.enrichment_date"] = {"$gt": last_marker}
    return query


def _find_stale_document_state_ids(client, base_query: dict, doc_state_col, batch_size: int = 1000) -> list:
    stale_ids: list = []
    pending_ids: list = []

    def _flush_batch() -> None:
        if not pending_ids:
            return
        query = dict(base_query)
        query["_id"] = {"$in": list(pending_ids)}
        active_ids = {
            doc["_id"]
            for doc in client.documents.find(query, {"_id": 1})
        }
        stale_ids.extend(doc_id for doc_id in pending_ids if doc_id not in active_ids)
        pending_ids.clear()

    for state in doc_state_col.find({}, {"_id": 1}):
        pending_ids.append(state["_id"])
        if len(pending_ids) >= batch_size:
            _flush_batch()

    _flush_batch()
    return stale_ids


def run(config: dict) -> None:
    from hytools.ingestion._shared.helpers import open_mongodb_client
    from hytools.ingestion.aggregation import frequency_aggregator

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for incremental merge")

        base_query = frequency_aggregator._build_docs_query(config)
        query_signature = frequency_aggregator._query_signature(base_query)
        state_meta = client.get_latest_metadata("frequency_aggregator") or {}

        freq_col, doc_state_col, source_totals_col, source_stats_col = frequency_aggregator._get_collections(client)
        frequency_aggregator._ensure_indexes(freq_col, doc_state_col, source_totals_col, source_stats_col)

        needs_bootstrap = (
            state_meta.get("query_signature") != query_signature
            or (
                client.documents.count_documents(base_query) > 0
                and doc_state_col.count_documents({}) == 0
            )
        )

        if needs_bootstrap:
            logger.info("Incremental merge: bootstrapping frequency state from current corpus")
            summary = frequency_aggregator._run_full_rebuild(client, config)
            summary["note"] = "bootstrapped_full_rebuild"
        else:
            last_marker = _get_last_merge_marker(client)
            query = _build_query(base_query, last_marker)
            total_docs = client.documents.count_documents(query)
            stale_doc_ids = _find_stale_document_state_ids(client, base_query, doc_state_col)
            logger.info(
                "Incremental merge: found %d changed docs and %d stale document states to reconcile",
                total_docs,
                len(stale_doc_ids),
            )
            summary = frequency_aggregator.run_incremental_update(
                client,
                config,
                query,
                removed_doc_ids=stale_doc_ids,
            )
            if summary.get("last_enrichment_date") is None and last_marker:
                summary["last_enrichment_date"] = last_marker
            if summary.get("removed_docs_processed"):
                summary["note"] = "reconciled_stale_document_state"

        client.metadata.replace_one(
            {"stage": "incremental_merge"},
            frequency_aggregator._build_frequency_metadata_doc(
                "incremental_merge",
                summary,
                query_signature,
            ),
            upsert=True,
        )
