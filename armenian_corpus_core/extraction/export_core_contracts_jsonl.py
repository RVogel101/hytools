#!/usr/bin/env python3
"""Export lousardzag DB rows to migration-safe core contract JSONL files.

Outputs:
- 08-data/export_lexicon_entries.jsonl
- 08-data/export_document_records.jsonl
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from lousardzag.core_shims.mappers import (
    anki_card_row_to_lexicon_entry,
    sentence_row_to_document_record,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export DB rows as core contract JSONL")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("08-data/armenian_cards.db"),
        help="Path to source SQLite DB",
    )
    parser.add_argument(
        "--lexicon-out",
        type=Path,
        default=Path("08-data/export_lexicon_entries.jsonl"),
        help="Output JSONL for LexiconEntry records",
    )
    parser.add_argument(
        "--documents-out",
        type=Path,
        default=Path("08-data/export_document_records.jsonl"),
        help="Output JSONL for DocumentRecord records",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional row limit per exported table (0 = all)",
    )
    return parser.parse_args()


def _rows_query(base: str, limit: int) -> str:
    if limit and limit > 0:
        return f"{base} LIMIT {int(limit)}"
    return base


def export_lexicon(conn: sqlite3.Connection, out_path: Path, limit: int) -> int:
    query = _rows_query(
        "SELECT anki_note_id, word, translation, pos, frequency_rank, syllable_count, metadata_json, morphology_json, deck_name, sub_deck_name, custom_level FROM anki_cards",
        limit,
    )
    count = 0
    with out_path.open("w", encoding="utf-8") as f:
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
            f.write(json.dumps(entry.__dict__, ensure_ascii=False) + "\n")
            count += 1
    return count


def export_documents(conn: sqlite3.Connection, out_path: Path, limit: int) -> int:
    query = _rows_query(
        "SELECT id, card_id, form_label, armenian_text, english_text, grammar_type, created_at, vocabulary_used FROM sentences",
        limit,
    )
    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for row in conn.execute(query):
            row_dict = dict(row)
            record = sentence_row_to_document_record(row_dict)
            f.write(json.dumps(record.__dict__, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> int:
    args = parse_args()

    if not args.db_path.exists():
        print(f"Database not found: {args.db_path}")
        return 1

    args.lexicon_out.parent.mkdir(parents=True, exist_ok=True)
    args.documents_out.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(args.db_path))
    conn.row_factory = sqlite3.Row
    try:
        lexicon_count = export_lexicon(conn, args.lexicon_out, args.limit)
        docs_count = export_documents(conn, args.documents_out, args.limit)
    finally:
        conn.close()

    print(f"Exported LexiconEntry records: {lexicon_count} -> {args.lexicon_out}")
    print(f"Exported DocumentRecord records: {docs_count} -> {args.documents_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
