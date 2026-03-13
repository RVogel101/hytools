#!/usr/bin/env python3
"""Import Anki SQLite DB rows into MongoDB as corpus documents.

Reads from SQLite (armenian_cards.db) and inserts into MongoDB:
- LexiconEntry records from anki_cards table -> source="anki_lexicon"
- DocumentRecord records from sentences table -> source="anki_sentences"
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from ingestion._shared.helpers import open_mongodb_client, insert_or_skip
from ingestion._shared.mappers import (
    anki_card_row_to_lexicon_entry,
    sentence_row_to_document_record,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import Anki SQLite DB rows into MongoDB"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/anki/armenian_cards.db"),
        help="Path to source SQLite DB",
    )
    parser.add_argument(
        "--mongodb-config",
        type=Path,
        default=None,
        help="Path to pipeline config YAML (database.mongodb_uri, database.mongodb_database). Default: config/settings.yaml or built-in defaults",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional row limit per exported table (0 = all)",
    )
    return parser.parse_args()


def _load_config(config_path: Path | None) -> dict:
    """Load MongoDB config from YAML or return defaults."""
    if config_path is not None and config_path.exists():
        import yaml

        with open(config_path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    default_path = Path(__file__).parents[2] / "config" / "settings.yaml"
    if default_path.exists():
        import yaml

        with open(default_path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    return {}


def _rows_query(base: str, limit: int) -> str:
    if limit and limit > 0:
        return f"{base} LIMIT {int(limit)}"
    return base


def _entry_to_dict(entry) -> dict:
    """Convert dataclass to JSON-serializable dict."""
    d = {}
    for k, v in entry.__dict__.items():
        if hasattr(v, "value"):
            d[k] = v.value
        else:
            d[k] = v
    return d


def export_lexicon(conn: sqlite3.Connection, client, limit: int, config: dict) -> int:
    query = _rows_query(
        "SELECT anki_note_id, word, translation, pos, frequency_rank, syllable_count, metadata_json, morphology_json, deck_name, sub_deck_name, custom_level FROM anki_cards",
        limit,
    )
    count = 0
    for row in conn.execute(query):
        row_dict = dict(row)
        morph = row_dict.get("morphology_json")
        if isinstance(morph, str) and morph.strip():
            try:
                morph_json = json.loads(morph)
                if isinstance(morph_json, dict):
                    row_dict["pronunciation"] = morph_json.get("english_approx")
            except json.JSONDecodeError:
                pass
        entry = anki_card_row_to_lexicon_entry(row_dict)
        entry_dict = _entry_to_dict(entry)
        title = f"lexicon:{entry.lemma}"
        text = json.dumps(entry_dict, ensure_ascii=False)
        if insert_or_skip(
            client,
            source="anki_lexicon",
            title=title,
            text=text,
            metadata=entry_dict,
            config=config,
        ):
            count += 1
    return count


def export_documents(conn: sqlite3.Connection, client, limit: int, config: dict) -> int:
    query = _rows_query(
        "SELECT id, card_id, form_label, armenian_text, english_text, grammar_type, created_at, vocabulary_used FROM sentences",
        limit,
    )
    count = 0
    for row in conn.execute(query):
        row_dict = dict(row)
        record = sentence_row_to_document_record(row_dict)
        title = record.document_id or record.title or "unknown"
        if insert_or_skip(
            client,
            source="anki_sentences",
            title=title,
            text=record.text,
            metadata={
                "document_id": record.document_id,
                "source_family": record.source_family,
                "content_hash": record.content_hash,
                "char_count": record.char_count,
                "dialect_tag": record.dialect_tag.value if hasattr(record.dialect_tag, "value") else str(record.dialect_tag),
                **(record.metadata or {}),
            },
            config=config,
        ):
            count += 1
    return count


def run(config: dict) -> None:
    """Import Anki SQLite DB into MongoDB. Uses config for paths and database.

    Config keys: paths.anki_db_path or ingestion.import_anki_sqlite.db_path,
    ingestion.import_anki_sqlite.limit (0 = all), and database.* for MongoDB.
    """
    paths = config.get("paths", {})
    ing_cfg = config.get("ingestion", {}).get("import_anki_sqlite", {}) or config.get("scraping", {}).get("extraction", {})
    db_path = Path(ing_cfg.get("db_path") or paths.get("anki_db_path") or "data/anki/armenian_cards.db")
    limit = int(ing_cfg.get("limit", 0) or 0)

    if not db_path.exists():
        raise FileNotFoundError(f"Anki database not found: {db_path}")

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB unavailable. Ensure pymongo is installed and MongoDB is reachable.")
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            lexicon_count = export_lexicon(conn, client, limit, config)
            docs_count = export_documents(conn, client, limit, config)
        finally:
            conn.close()

    print(f"Inserted LexiconEntry records: {lexicon_count} (source=anki_lexicon)")
    print(f"Inserted DocumentRecord records: {docs_count} (source=anki_sentences)")


def main() -> int:
    args = parse_args()
    config = _load_config(args.mongodb_config)
    if not args.db_path.exists():
        print(f"Database not found: {args.db_path}")
        return 1
    config.setdefault("paths", {})["anki_db_path"] = str(args.db_path)
    config.setdefault("ingestion", {}).setdefault("import_anki_sqlite", {})["db_path"] = str(args.db_path)
    config.setdefault("ingestion", {}).setdefault("import_anki_sqlite", {})["limit"] = args.limit
    try:
        run(config)
        return 0
    except (FileNotFoundError, RuntimeError) as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
