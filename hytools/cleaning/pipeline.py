"""High-level text cleaning and deduplication pipeline for hytools.

This module provides an opinionated end-to-end pipeline with a strict
internal_language_tag filter and dedicated output schema so raw source
MongoDB documents are retained.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from hytools.ingestion._shared.helpers import (
    open_mongodb_client,
    classify_text_classification,
)
from hytools.cleaning.normalizer import normalize

logger = logging.getLogger(__name__)

PIPELINE_VERSION = "1.0"
LANGUAGE_TAGGING_VERSION = "v1"


def extract_from_mongo(
    config: dict,
    source_collection: str = "documents",
    output_collection: str = "documents_cleaned",
    filter_query: dict | None = None,
) -> dict:
    """Copy documents from raw collection into a clean staging collection."""
    filter_query = filter_query or {"metadata.internal_language_tag": "hye-w"}

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB client unavailable")

        src = client.db[source_collection]
        dst = client.db[output_collection]

        # Keep old collection intact, use separate output collection.
        dst.delete_many({})

        docs = list(src.find(filter_query))
        imported = 0

        for doc in docs:
            base = {k: v for k, v in doc.items() if k != "_id"}
            if "_id" in doc:
                base["_source_id"] = str(doc["_id"])
                base["_id"] = doc["_id"]
            base.setdefault("processing", {}).update(
                {
                    "normalized": False,
                    "deduplicated": False,
                    "filtered": False,
                    "internal_language_classified": False,
                }
            )
            base.setdefault("metadata", {}).update(
                {
                    "source_pipeline_version": PIPELINE_VERSION,
                    "language_tagging_version": LANGUAGE_TAGGING_VERSION,
                }
            )
            dst.insert_one(base)
            imported += 1

        if imported == 0:
            logger.warning(
                "No documents found in %s with filter %s. Skipping import.",
                source_collection,
                filter_query,
            )
            return {"imported": 0}

        logger.info("extract_from_mongo: imported %d docs from %s to %s", imported, source_collection, output_collection)

        return {
            "source_collection": source_collection,
            "output_collection": output_collection,
            "filter_query": filter_query,
            "imported": imported,
        }


def apply_language_tagging(
    config: dict,
    collection: str = "documents_cleaned",
    tag_field: str = "metadata.internal_language_tag",
    require_tag: str = "hye-w",
) -> dict:
    """Classify each document and write internal_language_tag/score."""
    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB client unavailable")

        coll = client.db[collection]
        updated = 0

        for doc in coll.find({}):
            text = doc.get("text", "")
            if not isinstance(text, str) or not text.strip():
                logger.warning("Skipping document with empty text field: %s", doc.get("_id"))
                continue

            if "metadata" not in doc:
                logger.warning("Skipping document with missing metadata: %s", doc.get("_id"))
                continue

            # Update metadata.internal_language_branch based on classification
            classification = classify_text_classification(text)
            branch = classification.get("label")
            confidence = float(classification.get("confidence", 0.0))

            if branch == "likely_western":
                doc["metadata"]["internal_language_branch"] = "hye-w"
            elif branch == "likely_eastern":
                doc["metadata"]["internal_language_branch"] = "hye-e"
            elif branch == "likely_classical":
                doc["metadata"]["internal_language_branch"] = "hye-c"
            else:
                doc["metadata"]["internal_language_branch"] = "unknown"

            coll.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "processing.dialect_classified": True,
                        "metadata.internal_language_branch": doc["metadata"]["internal_language_branch"],
                        "metadata.confidence_dialect": confidence,
                        "metadata.language_tagging_version": LANGUAGE_TAGGING_VERSION,
                    }
                },
            )
            updated += 1

        if updated == 0:
            logger.warning(
                "apply_language_tagging: no documents updated in %s. Skipping tagging.",
                collection,
            )
            return {"updated": 0}

        logger.info("apply_language_tagging: updated %d documents in %s", updated, collection)

        return {"updated": updated}


def apply_text_cleaning(
    config: dict,
    collection: str = "documents_cleaned",
    require_tag: str = "hye-w",
) -> dict:
    """Normalize text; update metadata for dedupe and language branch."""
    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB client unavailable")

        coll = client.db[collection]
        updated = 0

        for doc in coll.find({"metadata.internal_language_tag": require_tag}):
            text = doc.get("text", "")
            normalized_text = normalize(text)
            normalized_hash = hashlib.sha256(normalized_text.encode("utf-8", errors="replace")).hexdigest()

            coll.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "text": normalized_text,
                        "processing.normalized": True,
                        "metadata.normalized_content_hash": normalized_hash,
                        "metadata.dedupe_hash": normalized_hash,
                    }
                },
            )
            updated += 1

        if updated == 0:
            raise RuntimeError(f"apply_text_cleaning: no documents normalized in {collection}")

        return {
            "collection": collection,
            "normalized": updated,
        }


def dedupe_documents(
    config: dict,
    collection: str = "documents_cleaned",
    require_tag: str = "hye-w",
) -> dict:
    """Mark duplicates based on normalized hash and optionally remove them."""
    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB client unavailable")

        coll = client.db[collection]
        seen_hashes: set[str] = set()
        total = 0
        duplicates = 0

        cursor = coll.find({"metadata.internal_language_tag": require_tag})
        if isinstance(cursor, list):
            cursor = sorted(
                cursor,
                key=lambda d: (
                    d.get("metadata", {}).get("normalized_content_hash", ""),
                    d.get("_id", 0),
                ),
            )
        elif hasattr(cursor, "sort"):
            cursor = cursor.sort([("metadata.normalized_content_hash", 1), ("_id", 1)])
        else:
            cursor = sorted(
                cursor,
                key=lambda d: (
                    d.get("metadata", {}).get("normalized_content_hash", ""),
                    d.get("_id", 0),
                ),
            )

        for doc in cursor:
            total += 1
            dedupe_hash = doc.get("metadata", {}).get("normalized_content_hash")
            if not dedupe_hash:
                continue

            if dedupe_hash in seen_hashes:
                duplicates += 1
                coll.update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "processing.deduplicated": True,
                            "processing.filtered": False,
                        }
                    },
                )
            else:
                seen_hashes.add(dedupe_hash)
                coll.update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "processing.deduplicated": False,
                            "processing.filtered": True,
                        }
                    },
                )

        if total == 0:
            raise RuntimeError(f"dedupe_documents: no documents found in {collection}")

        logger.info("dedupe_documents: %d total, %d duplicates", total, duplicates)

        return {
            "collection": collection,
            "total": total,
            "duplicates": duplicates,
            "kept": total - duplicates,
        }


def eastern_audit(config: dict, collection: str = "documents_cleaned") -> dict:
    """Perform a light audit for Eastern influence in the cleaned collection."""
    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB client unavailable")

        coll = client.db[collection]
        total = coll.count_documents({"processing.filtered": True})
        eastern = coll.count_documents({"processing.filtered": True, "metadata.internal_language_tag": "hye-e"})
        classical = coll.count_documents({"processing.filtered": True, "metadata.internal_language_tag": "hye-c"})

        ratio_eastern = float(eastern) / max(total, 1)
        ratio_classical = float(classical) / max(total, 1)

        if ratio_eastern > 0.01:
            logger.warning("eastern_audit: high eastern ratio %.3f (threshold 0.01)", ratio_eastern)

        return {
            "collection": collection,
            "total_filtered": total,
            "eastern_filtered": eastern,
            "classical_filtered": classical,
            "ratio_eastern": ratio_eastern,
            "ratio_classical": ratio_classical,
        }


def emit_corpus(
    config: dict,
    collection: str = "documents_cleaned",
    output_path: str | Path = "./data/cleaned_corpus",
    require_tag: str = "hye-w",
) -> dict:
    """Write vetted corpus to output path (JSONL + individual txt)."""
    out = Path(output_path)
    out.mkdir(parents=True, exist_ok=True)

    jsonl_path = out / "cleaned_corpus.jsonl"
    saved = 0

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB client unavailable")

        coll = client.db[collection]
        with open(jsonl_path, "w", encoding="utf-8") as fh:
            for doc in coll.find({"processing.filtered": True, "processing.deduplicated": False, "metadata.internal_language_tag": require_tag}):
                metadata = doc.get("metadata", {}).copy()
                metadata["pipeline_version"] = PIPELINE_VERSION
                metadata["language_tagging_version"] = LANGUAGE_TAGGING_VERSION

                record = {
                    "source": doc.get("source"),
                    "title": doc.get("title"),
                    "text": doc.get("text"),
                    "metadata": metadata,
                }
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")

                txt_file = out / f"{doc.get('_id')}.txt"
                txt_file.write_text(doc.get("text", ""), encoding="utf-8")
                saved += 1

    logger.info("emit_corpus: saved %d documents to %s", saved, out)

    return {
        "collection": collection,
        "output_path": str(out),
        "saved": saved,
    }


def create_clean_corpus(
    config: dict,
    source_collection: str = "documents",
    output_collection: str = "documents_cleaned",
    output_path: str | Path = "./data/cleaned_corpus",
) -> dict:
    """Run the full clean corpus pipeline from MongoDB extraction to output."""
    summary: dict[str, Any] = {}

    summary["extract"] = extract_from_mongo(
        config,
        source_collection=source_collection,
        output_collection=output_collection,
        filter_query={"metadata.internal_language_tag": "hye-w"},
    )

    summary["language_tagging"] = apply_language_tagging(
        config,
        collection=output_collection,
        tag_field="metadata.internal_language_tag",
        require_tag="hye-w",
    )

    summary["text_cleaning"] = apply_text_cleaning(
        config,
        collection=output_collection,
        require_tag="hye-w",
    )

    summary["dedupe"] = dedupe_documents(
        config,
        collection=output_collection,
        require_tag="hye-w",
    )

    summary["eastern_audit"] = eastern_audit(config, collection=output_collection)

    summary["emit"] = emit_corpus(
        config,
        collection=output_collection,
        output_path=output_path,
        require_tag="hye-w",
    )

    summary["pipeline_version"] = PIPELINE_VERSION
    summary["finished_at"] = time.time()

    return summary


if __name__ == "__main__":
    import argparse
    from hytools.config.settings import load_config

    parser = argparse.ArgumentParser(prog="python -m hytools.cleaning.pipeline")
    parser.add_argument("--config", default="config/settings.yaml", help="Pipeline config path")
    parser.add_argument("--output", default="data/cleaned_corpus", help="Corpus output path")
    args = parser.parse_args()

    cfg = load_config(args.config) if os.path.exists(args.config) else {}
    summary = create_clean_corpus(cfg, output_path=args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
