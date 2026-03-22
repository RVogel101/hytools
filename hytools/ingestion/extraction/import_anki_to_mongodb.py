#!/usr/bin/env python3
"""Import Anki data into MongoDB via AnkiConnect.

Connects to a running Anki desktop (AnkiConnect) and imports flashcard notes
into MongoDB using the corpus document schema.

This script is strictly read-only with respect to Anki— it only queries AnkiConnect
(note lookup via `findNotes`/`notesInfo`) and does not modify or write any notes,
decks, or cards back into the Anki desktop database.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

from hytools.ingestion._shared.helpers import open_mongodb_client
from hytools.ingestion._shared.mappers import anki_card_row_to_lexicon_entry
from hytools.ingestion._shared.schema import CARD_SCHEMA_KEYS, REQUIRED_CARD_FIELDS

try:
    from pymongo.errors import DuplicateKeyError  # type: ignore[reportMissingModuleSource]
except ImportError:
    DuplicateKeyError = Exception


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import Anki data into MongoDB via AnkiConnect."
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
        help="Optional limit on total notes to import (0 = all)",
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


def _get_anki_connect_url(config: dict) -> str:
    """Return the AnkiConnect URL (default: http://localhost:8765)."""
    return (
        config.get("anki_connect", {}).get("url")
        or config.get("ankiconnect", {}).get("url")
        or "http://localhost:8765"
    )


def _find_anki_notes(ankiconnect_url: str, query: str = "deck:*") -> list[int]:
    """Find note IDs via AnkiConnect."""
    payload = {"action": "findNotes", "version": 6, "params": {"query": query}}
    resp = requests.post(ankiconnect_url, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("result", []) or []


def _get_notes_info(ankiconnect_url: str, note_ids: list[int]) -> list[dict]:
    """Fetch full note info for given note IDs."""
    if not note_ids:
        return []
    payload = {"action": "notesInfo", "version": 6, "params": {"notes": note_ids}}
    resp = requests.post(ankiconnect_url, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("result", []) or []


def _get_anki_deck_names(ankiconnect_url: str) -> list[str]:
    """Get all deck names via AnkiConnect."""
    payload = {"action": "deckNames", "version": 6}
    resp = requests.post(ankiconnect_url, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("result", []) or []


def _split_deck_name(deck_name: str | None) -> tuple[str, str]:
    """Split a full deck name into (deck, sub_deck).

    Anki represents nested decks as "Parent::Child".
    """
    if not deck_name:
        return "", ""
    parts = [p.strip() for p in deck_name.split("::") if p.strip()]
    if not parts:
        return "", ""
    return parts[0], parts[1] if len(parts) > 1 else ""


def _normalize_ankiconnect_note(note: dict[str, Any]) -> dict[str, Any]:
    """Convert AnkiConnect note JSON into the expected row dict format."""
    fields = note.get("fields", {}) or {}

    def _first_non_empty(*keys: str) -> Optional[str]:
        for k in keys:
            v = None
            if isinstance(fields, dict):
                v = fields.get(k, {}).get("value") if isinstance(fields.get(k), dict) else fields.get(k)
            if v is None:
                v = note.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    deck_name_raw = note.get("deckName") or note.get("deck")
    deck_name, sub_deck_name = _split_deck_name(deck_name_raw)

    # Keep the full AnkiConnect note record available for downstream inspection.
    # Preserve existing shorthand fields for backward compatibility.
    # Normalize to the contract defined in ingestion._shared.schema.
    row = {
        "anki_note_id": int(note.get("noteId") or note.get("id") or 0),
        "deck_name": deck_name,
        "sub_deck_name": sub_deck_name,
        "anki_deck_name": deck_name,
        "word": _first_non_empty("armenian", "Armenian", "Word", "word", "Front", "front", "phrase"),
        "translation": _first_non_empty("english", "English", "Translation", "meaning", "Back", "back", "definition"),
        "pos": None,
        "card_type": "anki_note:vocab",
        "frequency_rank": 9999,
        "syllable_count": 0,
        "tags": note.get("tags"),
        "model_name": note.get("modelName"),
        "deck_id": note.get("deckId"),
        "guid": note.get("guid"),
        "fields": fields,
        "flags": note.get("flags"),
        "data": note.get("data"),
        "usn": note.get("usn"),
        "mod": note.get("mod"),
        "created": note.get("created"),
        "cards": note.get("cards"),
        "metadata_json": _first_non_empty("metadata_json", "metadata") or "{}",
        "morphology_json": _first_non_empty("morphology_json", "morphology") or "{}",
        "custom_level": None,
    }

    # Enforce the schema contract (ensures missing keys are present in docs)
    for key in CARD_SCHEMA_KEYS:
        row.setdefault(key, None)

    return row


def _entry_to_dict(entry) -> dict:
    """Convert dataclass to JSON-serializable dict."""
    d = {}
    for k, v in entry.__dict__.items():
        if hasattr(v, "value"):
            d[k] = v.value
        else:
            d[k] = v
    return d


def _validate_card_row(row: dict[str, Any]) -> dict[str, Any]:
    """Validate required card schema fields and normalize values."""

    def _is_blank(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    missing = [
        k
        for k in REQUIRED_CARD_FIELDS
        if k not in row or _is_blank(row.get(k))
    ]
    if missing:
        raise ValueError(f"Missing required card fields: {missing}")

    # Ensure types are sane
    if isinstance(row.get("anki_note_id"), str) and row["anki_note_id"].isdigit():
        row["anki_note_id"] = int(row["anki_note_id"])

    return row


def _export_lexicon_from_rows(rows: Iterable[dict[str, Any]], client, config: dict) -> int:
    """Import a sequence of lexicon-like row dicts into MongoDB cards collection."""
    count = 0
    _skipped_notes: list[dict[str, Any]] = []
    for row in rows:
        morph = row.get("morphology_json")
        if isinstance(morph, str) and morph.strip():
            try:
                morph_json = json.loads(morph)
                if isinstance(morph_json, dict):
                    row["pronunciation"] = morph_json.get("english_approx")
            except json.JSONDecodeError:
                pass

        # Validate strict schema before inserting
        try:
            card_doc = _validate_card_row(row)
        except ValueError as e:
            # Some Anki notes may lack required fields (e.g. blank front/back); skip them.
            # Capture first few examples for debugging.
            _skipped_notes.append(row)
            if len(_skipped_notes) <= 3:
                note_id = row.get("anki_note_id")
                fields_keys = list(row.get("fields", {}).keys()) if isinstance(row.get("fields"), dict) else []
                print(f"Skipping note id={note_id} (missing required fields) -> fields keys: {fields_keys}")
            continue

        # Convert to canonical LexiconEntry for metadata (used for search/lookup)
        entry = anki_card_row_to_lexicon_entry(card_doc)
        entry_dict = _entry_to_dict(entry)
        card_doc["metadata_json"] = card_doc.get("metadata_json") or "{}"
        card_doc["morphology_json"] = card_doc.get("morphology_json") or "{}"

        try:
            client.cards.insert_one(card_doc)
            count += 1
        except DuplicateKeyError:
            # Duplicate card based on unique index (anki_note_id)
            continue

    if _skipped_notes:
        print(f"Skipped {len(_skipped_notes)} notes due to missing required fields (e.g. blank word/translation).")
    return count


def run(config: dict) -> None:
    """Import Anki data into MongoDB via AnkiConnect.

    Args:
        config: pipeline configuration (MongoDB, AnkiConnect settings)

    Config keys:
      - ingestion.import_anki_to_mongodb.limit (0 = all)
      - database.* for MongoDB
      - anki_connect.url (optional) for AnkiConnect endpoint
    """
    ing_cfg = config.get("ingestion", {}).get("import_anki_to_mongodb", {})
    limit = int(ing_cfg.get("limit", 0) or 0)

    try:
        with open_mongodb_client(config) as client:
            if client is None:
                raise RuntimeError("MongoDB unavailable. Ensure pymongo is installed and MongoDB is reachable.")

            ankiconnect_url = _get_anki_connect_url(config)
            deck_names = _get_anki_deck_names(ankiconnect_url)
            if not deck_names:
                raise RuntimeError(f"AnkiConnect returned no decks at {ankiconnect_url}")

            rows: List[dict[str, Any]] = []
            remaining = limit if limit and limit > 0 else None

            for deck in deck_names:
                # Anki's query syntax requires deck names with spaces to be quoted.
                quoted_deck = deck.replace('"', '\\"')
                query = f"deck:\"{quoted_deck}\""
                note_ids = _find_anki_notes(ankiconnect_url, query=query)
                if not note_ids:
                    continue
                if remaining is not None:
                    note_ids = note_ids[:remaining]
                notes = _get_notes_info(ankiconnect_url, note_ids)
                rows.extend(_normalize_ankiconnect_note(n) for n in notes)
                print(f"Fetched {len(notes)} notes from deck {deck!r}")
                if remaining is not None:
                    remaining -= len(notes)
                    if remaining <= 0:
                        break

            lexicon_count = _export_lexicon_from_rows(rows, client, config)

            # Report where data went and basic schema info while still connected.
            db_name = getattr(client, "database_name", "<unknown>")
            uri = getattr(client, "uri", "<unknown>")

            print(f"Inserted LexiconEntry records: {lexicon_count} (source=anki_lexicon)")
            print(f"MongoDB URI: {uri}")
            print(f"MongoDB database: {db_name}")

            cards_coll = getattr(client, "cards", None)
            if cards_coll is not None:
                card_count = cards_coll.count_documents({})
                print(f"Cards collection: {cards_coll.name} (total={card_count})")
                sample = cards_coll.find_one({})
                if sample:
                    print("Sample card fields:", sorted(sample.keys()))
                else:
                    print("No sample card found to infer schema.")
            else:
                print("Could not access the cards collection for schema reporting.")

    except Exception as exc:
        # Avoid crashing when some notes are invalid or connection issues occur.
        print(f"Import failed: {exc}")
        return


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args()
    config = _load_config(args.mongodb_config)
    try:
        run(config)
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
