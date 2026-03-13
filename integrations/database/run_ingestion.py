"""Load cached JSONL/articles from data/raw into MongoDB.

Used by CI when restoring cache: ingest any previously scraped JSONL
so the pipeline can resume or avoid re-running acquisition. Run before ingestion.

Uses insert_or_skip so document_metrics (e.g. word_counts) are computed on ingest.

Usage::
    python -m integrations.database.run_ingestion --raw-only
    python -m integrations.database.run_ingestion --raw-only --mongodb-uri mongodb://localhost:27017/
    python -m integrations.database.run_ingestion --raw-only --skip-if-unavailable
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _ingest_jsonl(path: Path, client, source: str, config: dict | None = None) -> tuple[int, int]:
    """Ingest a JSONL file. Returns (inserted, skipped). Uses insert_or_skip for metrics on ingest."""
    try:
        from ingestion._shared.helpers import insert_or_skip
    except ImportError:
        # Fallback if ingestion not available (e.g. integrations used standalone)
        insert_or_skip = None
    inserted = skipped = 0
    cfg = config or {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = doc.get("text") or doc.get("content") or ""
            title = doc.get("title") or doc.get("url", "")[:200] or path.stem
            if not text.strip():
                skipped += 1
                continue
            if insert_or_skip is not None:
                ok = insert_or_skip(
                    client,
                    source=source,
                    title=title,
                    text=text,
                    url=doc.get("url"),
                    metadata=doc.get("metadata", {}),
                    config=cfg,
                )
                if ok:
                    inserted += 1
                else:
                    skipped += 1
            else:
                try:
                    client.insert_document(
                        source=source,
                        title=title,
                        text=text,
                        url=doc.get("url"),
                        metadata=doc.get("metadata", {}),
                    )
                    inserted += 1
                except Exception:
                    skipped += 1
    return inserted, skipped


def run(
    raw_dir: Path | None = None,
    mongodb_uri: str = "mongodb://localhost:27017/",
    mongodb_database: str = "western_armenian_corpus",
    skip_if_unavailable: bool = False,
    config: dict | None = None,
) -> dict:
    """Ingest JSONL from data/raw into MongoDB.

    Scans for *_articles.jsonl, articles.jsonl and inserts into documents.
    Uses insert_or_skip when scraping is available so document_metrics are computed.
    """
    raw_dir = raw_dir or Path("data/raw")
    if not raw_dir.exists():
        logger.info("Raw dir %s does not exist, skipping ingestion", raw_dir)
        return {"inserted": 0, "skipped": 0, "files": 0}

    try:
        from integrations.database.mongodb_client import MongoDBCorpusClient
    except ImportError:
        if skip_if_unavailable:
            logger.info("MongoDB client unavailable, skipping ingestion")
            return {"inserted": 0, "skipped": 0, "files": 0}
        raise

    total_inserted = total_skipped = 0
    files_processed = 0
    cfg = config or {}

    with MongoDBCorpusClient(uri=mongodb_uri, database_name=mongodb_database) as client:
        for jsonl in raw_dir.rglob("*.jsonl"):
            if "error" in jsonl.name.lower() or "log" in jsonl.name.lower():
                continue
            source = jsonl.parent.name or "raw"
            try:
                ins, sk = _ingest_jsonl(jsonl, client, source, config=cfg)
                total_inserted += ins
                total_skipped += sk
                files_processed += 1
                if ins or sk:
                    logger.info("Ingested %s: %d inserted, %d skipped", jsonl.name, ins, sk)
            except Exception as exc:
                if skip_if_unavailable:
                    logger.warning("Failed to ingest %s: %s", jsonl, exc)
                else:
                    raise

    return {"inserted": total_inserted, "skipped": total_skipped, "files": files_processed}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest cached JSONL from data/raw into MongoDB")
    parser.add_argument("--raw-only", action="store_true", help="Only ingest from data/raw (default)")
    parser.add_argument("--mongodb-uri", default="mongodb://localhost:27017/")
    parser.add_argument("--mongodb-database", default="western_armenian_corpus")
    parser.add_argument("--skip-if-unavailable", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    try:
        stats = run(
            mongodb_uri=args.mongodb_uri,
            mongodb_database=args.mongodb_database,
            skip_if_unavailable=args.skip_if_unavailable,
        )
        print(f"Ingestion complete: {stats['inserted']} inserted, {stats['files']} files")
    except Exception as exc:
        if args.skip_if_unavailable:
            print(f"Ingestion skipped: {exc}")
        else:
            raise


if __name__ == "__main__":
    main()
