"""Incremental merge stage: process only updated/added documents since last run."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _get_last_merge_timestamp(client):
    meta = client.get_latest_metadata("incremental_merge") or {}
    ts = meta.get("timestamp")
    return ts


def _build_query(last_ts: datetime | None) -> dict:
    if not last_ts:
        # First-time run: process all docs with any enriched metadata
        return {"metadata.enrichment_date": {"$exists": True}}
    return {"metadata.enrichment_date": {"$gt": last_ts}}


def run(config: dict) -> None:
    from hytools.ingestion._shared.helpers import open_mongodb_client

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for incremental merge")

        last_ts = _get_last_merge_timestamp(client)
        query = _build_query(last_ts)
        docs_col = client.documents

        total_docs = docs_col.count_documents(query)
        logger.info("Incremental merge: found %d docs to process", total_docs)

        # For now, this stage reuses frequency_aggregator on the subset of docs.
        # It writes a fresh word_frequencies collection at minimal run count.
        # TODO: optimize to update only changed words instead of full rebuild.

        from hytools.ingestion.aggregation.frequency_aggregator import run as run_freq

        config_copy = dict(config)
        config_copy.setdefault("ingestion", {}).setdefault("frequency_aggregator", {})
        config_copy["ingestion"]["frequency_aggregator"]["_document_filter"] = query

        run_freq(config_copy)

        client.metadata.replace_one(
            {"stage": "incremental_merge"},
            {"stage": "incremental_merge", "timestamp": datetime.now(timezone.utc), "docs_processed": total_docs},
            upsert=True,
        )
