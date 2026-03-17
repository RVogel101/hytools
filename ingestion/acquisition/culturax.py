"""CulturaX Armenian dataset downloader.

Streams the Armenian (hy) subset of the CulturaX dataset from HuggingFace
and inserts every document into MongoDB, tagging each with its detected
dialect (``western_armenian`` or ``eastern_armenian``).
Checkpoint for resume is stored in MongoDB metadata collection.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_CULTURAX_STAGE = "culturax"


def _classify_dialect(text: str) -> str:
    """Classify text as western_armenian or eastern_armenian."""
    try:
        from ingestion._shared.helpers import compute_wa_score, WA_SCORE_THRESHOLD
        score = compute_wa_score(text[:5000])
        return "western_armenian" if score >= WA_SCORE_THRESHOLD else "eastern_armenian"
    except ImportError:
        return "unknown"


def _load_checkpoint_from_mongodb(client) -> tuple[int, int]:
    """Load processed/written counts from MongoDB metadata."""
    if client is None:
        return 0, 0
    entry = client.metadata.find_one({"stage": _CULTURAX_STAGE})
    if not entry:
        return 0, 0
    return (
        int(entry.get("processed", 0)),
        int(entry.get("written", 0)),
    )


def _save_checkpoint_to_mongodb(client, processed: int, written: int, dialect_counts: dict) -> None:
    """Save checkpoint to MongoDB metadata."""
    if client is None:
        return
    from datetime import datetime, timezone
    client.metadata.replace_one(
        {"stage": _CULTURAX_STAGE},
        {
            "stage": _CULTURAX_STAGE,
            "processed": processed,
            "written": written,
            "dialect_counts": dialect_counts,
            "timestamp": datetime.now(timezone.utc),
        },
        upsert=True,
    )


def run(config: dict) -> None:
    """Entry-point: download the Armenian CulturaX subset and stream to MongoDB."""
    from datasets import load_dataset  # type: ignore[import]

    from ingestion._shared.helpers import insert_or_skip, open_mongodb_client

    scrape_cfg = config.get("scraping", {}).get("culturax", {})
    dataset_name: str = scrape_cfg.get("dataset_name", "uonlp/CulturaX")
    language: str = scrape_cfg.get("language", "hy")
    streaming: bool = scrape_cfg.get("streaming", True)
    min_chars: int = int(scrape_cfg.get("min_chars", 100))
    max_docs: int | None = scrape_cfg.get("max_docs")

    with open_mongodb_client(config) as mongodb_client:
        if mongodb_client is None:
            raise RuntimeError("MongoDB is required but unavailable")

        already_processed, already_written = _load_checkpoint_from_mongodb(mongodb_client)

        logger.info(
            "Loading CulturaX dataset '%s' (language=%s, streaming=%s, resume_from=%d)",
            dataset_name, language, streaming, already_processed,
        )
        dataset = load_dataset(dataset_name, language, split="train", streaming=streaming, trust_remote_code=True)

        processed = 0
        written = already_written
        dialect_counts: dict[str, int] = {}
        try:
            for doc in dataset:
                processed += 1

                if processed <= already_processed:
                    continue

                text = str(doc.get("text", "") if isinstance(doc, dict) else "")
                if len(text) < min_chars:
                    if processed % 10_000 == 0:
                        _save_checkpoint_to_mongodb(mongodb_client, processed, written, dialect_counts)
                    continue

                dialect = _classify_dialect(text)
                dialect_counts[dialect] = dialect_counts.get(dialect, 0) + 1

                title = (doc.get("url", "") or f"culturax_{processed}") if isinstance(doc, dict) else f"culturax_{processed}"
                doc_url = (doc.get("url", "") if isinstance(doc, dict) else "") or None
                if insert_or_skip(
                    mongodb_client,
                    source="culturax",
                    title=str(title),
                    text=text,
                    url=doc_url,
                    metadata={
                        "source_type": "web_crawl",
                        "source_language_code": "hyw" if dialect == "western_armenian" else "hye" if dialect == "eastern_armenian" else "hy",
                    },
                    config=config,
                ):
                    written += 1

                if processed % 10_000 == 0:
                    _save_checkpoint_to_mongodb(mongodb_client, processed, written, dialect_counts)
                    logger.info(
                        "  Processed %d, inserted %d — dialect breakdown: %s",
                        processed, written, dialect_counts,
                    )

                if max_docs is not None and written >= max_docs:
                    logger.info("Reached max_docs=%d; stopping early.", max_docs)
                    break

        finally:
            _save_checkpoint_to_mongodb(mongodb_client, processed, written, dialect_counts)

        logger.info(
            "CulturaX ingest complete: inserted=%d (processed=%d) — %s",
            written, processed, dialect_counts,
        )
