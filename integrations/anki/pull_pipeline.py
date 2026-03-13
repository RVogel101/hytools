"""Read-only export of all Anki data, then import into local SQLite.

Read-only Anki export pipeline for armenian-corpus-core.

Flow:
1) Read notes from Anki via AnkiConnect (no writes to Anki)
2) Export full payload to JSON
3) Upsert all notes into local SQLite database
4) Save note-type field map
"""

from __future__ import annotations

import base64
import html
import json
import logging
import os
import re
import shutil
import sqlite3
import tempfile
import time
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from .client import AnkiConnect

if TYPE_CHECKING:
    from ..database.card_database import CardDatabase

logger = logging.getLogger(__name__)

# Patterns for media references in Anki field HTML
RE_SOUND = re.compile(r"\[sound:([^\]]+)\]")
RE_IMG = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)


# ─── Low-level helpers ────────────────────────────────────────────────


def request_with_retry(ac: AnkiConnect, action: str, retries: int = 3, **params):
    """Send a request with exponential backoff retries."""
    for attempt in range(retries):
        try:
            return ac._request(action, **params)
        except Exception as e:
            if attempt == retries - 1:
                raise
            wait = 2 ** (attempt + 1)
            logger.warning("Retry %d in %ds: %s", attempt + 1, wait, e)
            time.sleep(wait)


def _extract_field(fields: dict, candidates: list[str]) -> str:
    """Extract first non-empty candidate field (case-insensitive)."""
    for candidate in candidates:
        for field_name, value in fields.items():
            if field_name.lower() == candidate.lower() and isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    return stripped
    return ""


def _clean_html(text: str) -> str:
    """Remove HTML tags and decode HTML entities from text."""
    if not text:
        return text
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _first_nonempty_short(fields: dict) -> str:
    """Return first field value under 200 chars, or empty string."""
    for value in fields.values():
        if isinstance(value, str):
            stripped = value.strip()
            if stripped and len(stripped) < 200:
                return stripped
    return ""


# ─── APKG parsing ────────────────────────────────────────────────────


def parse_apkg(apkg_path: str, media_dir: Path | None = None) -> list[dict]:
    """Extract notes and media from an .apkg file."""
    notes: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(apkg_path, "r") as zf:
            zf.extractall(tmp)

        db_path = None
        for name in ["collection.anki21", "collection.anki2"]:
            candidate = os.path.join(tmp, name)
            if os.path.exists(candidate):
                db_path = candidate
                break
        if not db_path:
            logger.warning("No SQLite db found in %s", apkg_path)
            return notes

        media_map_path = os.path.join(tmp, "media")
        media_count = 0
        if os.path.exists(media_map_path) and media_dir is not None:
            with open(media_map_path, "r", encoding="utf-8") as mf:
                media_map = json.load(mf)
            media_dir.mkdir(parents=True, exist_ok=True)
            for numeric_name, real_name in media_map.items():
                src = os.path.join(tmp, numeric_name)
                dst = media_dir / real_name
                if os.path.exists(src) and not dst.exists():
                    shutil.copy2(src, dst)
                    media_count += 1
        if media_count:
            logger.info("Extracted %d media files", media_count)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        col_row = cur.execute("SELECT models FROM col").fetchone()
        models = json.loads(col_row["models"])

        for row in cur.execute("SELECT id, mid, flds, tags FROM notes"):
            model_id = str(row["mid"])
            model = models.get(model_id, {})
            model_name = model.get("name", "Unknown")
            field_names = [f["name"] for f in model.get("flds", [])]
            field_values = row["flds"].split("\x1f")
            fields = {}
            for i, name in enumerate(field_names):
                fields[name] = field_values[i] if i < len(field_values) else ""
            tags = row["tags"].strip().split() if row["tags"].strip() else []
            notes.append(
                {
                    "noteId": row["id"],
                    "modelName": model_name,
                    "tags": tags,
                    "fields": fields,
                }
            )
        conn.close()
    return notes


# ─── Export strategies ────────────────────────────────────────────────


def export_via_apkg(
    ac: AnkiConnect, deck_name: str, media_dir: Path | None = None
) -> list[dict]:
    """Export one deck via exportPackage, parse, then remove temp file."""
    tmp_dir = tempfile.gettempdir()
    apkg_path = os.path.join(tmp_dir, "_anki_temp_export.apkg").replace("\\", "/")
    result = request_with_retry(
        ac,
        "exportPackage",
        deck=deck_name,
        path=apkg_path,
        includeSched=False,
    )
    if not result:
        logger.warning("exportPackage returned false for %s", deck_name)
        return []
    notes = parse_apkg(apkg_path, media_dir=media_dir)
    os.remove(apkg_path)
    return notes


def find_media_refs(fields: dict) -> set[str]:
    """Find sound/image references in field HTML."""
    refs: set[str] = set()
    for value in fields.values():
        refs.update(RE_SOUND.findall(value))
        refs.update(RE_IMG.findall(value))
    return refs


def fetch_media_via_api(
    ac: AnkiConnect, media_filenames: set[str], media_dir: Path
) -> int:
    """Download media files from Anki via retrieveMediaFile API."""
    media_dir.mkdir(parents=True, exist_ok=True)
    fetched = 0
    for fname in media_filenames:
        dst = media_dir / fname
        if dst.exists():
            continue
        try:
            data = request_with_retry(ac, "retrieveMediaFile", filename=fname)
            if data:
                dst.write_bytes(base64.b64decode(data))
                fetched += 1
        except Exception:
            pass
    return fetched


def export_via_notesinfo(
    ac: AnkiConnect, deck_name: str, media_dir: Path | None = None
) -> list[dict]:
    """Fallback export path for unstable exportPackage calls."""
    note_ids = request_with_retry(ac, "findNotes", query=f'deck:"{deck_name}"')
    if not note_ids:
        return []

    batch_size = 25
    actions = []
    for i in range(0, len(note_ids), batch_size):
        chunk = note_ids[i : i + batch_size]
        actions.append({"action": "notesInfo", "params": {"notes": chunk}})

    results = request_with_retry(ac, "multi", actions=actions) or []
    notes: list[dict] = []
    all_media: set[str] = set()
    for batch_result in results:
        if isinstance(batch_result, dict) and batch_result.get("error"):
            logger.warning("Batch error: %s", batch_result["error"])
            continue
        batch_notes = (
            batch_result
            if isinstance(batch_result, list)
            else batch_result.get("result", [])
        )
        for n in batch_notes:
            fields = {k: v["value"] for k, v in n["fields"].items()}
            all_media.update(find_media_refs(fields))
            notes.append(
                {
                    "noteId": n["noteId"],
                    "modelName": n["modelName"],
                    "tags": n["tags"],
                    "fields": fields,
                }
            )

    if all_media and media_dir is not None:
        fetched = fetch_media_via_api(ac, all_media, media_dir)
        if fetched:
            logger.info("Fetched %d media files via API", fetched)

    return notes


# ─── Field map inventory ─────────────────────────────────────────────


def write_field_name_map(ac: AnkiConnect, output_dir: Path) -> None:
    """Write note-type → field-names mapping and deduplicated field list."""
    models = request_with_retry(ac, "modelNamesAndIds") or {}
    by_model: dict[str, list[str]] = {}
    dedup: set[str] = set()

    for model_name in sorted(models.keys()):
        fields = request_with_retry(ac, "modelFieldNames", modelName=model_name) or []
        by_model[model_name] = fields
        dedup.update(fields)

    output_dir.mkdir(parents=True, exist_ok=True)
    field_map_path = output_dir / "anki_field_names_by_note_type.json"
    dedup_path = output_dir / "anki_field_names_dedup.json"

    with open(field_map_path, "w", encoding="utf-8") as f:
        json.dump(by_model, f, ensure_ascii=False, indent=2)
    with open(dedup_path, "w", encoding="utf-8") as f:
        json.dump(sorted(dedup), f, ensure_ascii=False, indent=2)

    logger.info("Saved note-type field map: %s", field_map_path)
    logger.info("Saved deduplicated field list: %s", dedup_path)


# ─── DB cleanup ──────────────────────────────────────────────────────


def cleanup_test_data(db: "CardDatabase") -> int:
    """Remove test/junk data from database before import."""
    logger.info("Cleaning up test data from database: %s", db.db_path)
    with db._connect() as conn:
        result = conn.execute("DELETE FROM anki_cards WHERE word LIKE 'test_%'")
        test_word_count = result.rowcount
        conn.commit()
    if test_word_count > 0:
        logger.info("Deleted %d test cards", test_word_count)
    return test_word_count


def cleanup_html_in_existing_cards(db: "CardDatabase") -> int:
    """Clean HTML tags and entities from existing database records."""
    logger.info("Cleaning HTML from existing cards: %s", db.db_path)
    with db._connect() as conn:
        cursor = conn.execute(
            """
            SELECT id, word, translation, pos
            FROM anki_cards
            WHERE word LIKE '%<%' OR word LIKE '%&%;%'
               OR translation LIKE '%<%' OR translation LIKE '%&%;%'
               OR pos LIKE '%<%' OR pos LIKE '%&%;%'
            """
        )
        rows = cursor.fetchall()
        cleaned_count = 0
        for row_id, word, translation, pos in rows:
            cleaned_word = _clean_html(word) if word else word
            cleaned_translation = _clean_html(translation) if translation else translation
            cleaned_pos = _clean_html(pos) if pos else pos
            conn.execute(
                "UPDATE anki_cards SET word = ?, translation = ?, pos = ? WHERE id = ?",
                (cleaned_word, cleaned_translation, cleaned_pos, row_id),
            )
            cleaned_count += 1
        conn.commit()
    if cleaned_count > 0:
        logger.info("Cleaned HTML from %d existing cards", cleaned_count)
    return cleaned_count


# ─── Main export + load pipeline ─────────────────────────────────────


def load_export_into_db(
    export_payload: dict[str, list[dict]], db: "CardDatabase"
) -> int:
    """Upsert exported notes into a CardDatabase."""
    logger.info("Loading data into database: %s", db.db_path)

    total_upserted = 0
    for deck_name, notes in export_payload.items():
        if not notes:
            continue

        deck_upserted = 0
        for note in notes:
            note_id = note.get("noteId")
            model_name = note.get("modelName", "")
            fields = note.get("fields", {})
            tags = note.get("tags", [])

            word = _extract_field(fields, ["Word", "Armenian", "Front", "Question"])
            if not word:
                word = _first_nonempty_short(fields)
            if not word:
                word = f"note_{note_id}" if note_id is not None else "note_unknown"
            word = _clean_html(word)

            translation = _extract_field(
                fields, ["Translation", "English", "Meaning", "Back", "Answer"]
            )
            translation = _clean_html(translation)

            pos = _extract_field(fields, ["PartOfSpeech", "POS", "Type", "Word Type"])
            pos = _clean_html(pos)

            metadata = {
                "anki_note_id": note_id,
                "anki_model_name": model_name,
                "anki_deck_name": deck_name,
                "anki_tags": tags,
                "anki_fields": fields,
            }

            card_type = (
                f"anki_note:{note_id}" if note_id is not None else "anki_note:unknown"
            )

            if "::" in deck_name:
                parent_deck, child_deck = deck_name.split("::", 1)
            else:
                parent_deck = deck_name
                child_deck = ""

            try:
                db.upsert_card(
                    word=word,
                    translation=translation,
                    pos=pos,
                    card_type=card_type,
                    metadata=metadata,
                    anki_note_id=note_id,
                    deck_name=parent_deck,
                    sub_deck_name=child_deck,
                )
                total_upserted += 1
                deck_upserted += 1
            except Exception as e:
                logger.warning("Failed upsert note %s: %s", note_id, e)

        logger.info("%s: upserted %d notes", deck_name, deck_upserted)

    return total_upserted


def run_pull_pipeline(
    data_dir: Path,
    media_dir: Path | None = None,
    url: str | None = None,
) -> int:
    """Run the full Anki pull pipeline.

    Args:
        data_dir: Directory for export JSON and database files.
        media_dir: Directory for extracted media (default: data_dir / "anki_media").
        url: AnkiConnect URL override (default: localhost:8765).

    Returns:
        Total number of upserted notes.
    """
    from ..database.card_database import CardDatabase

    ac = AnkiConnect(url=url)
    if not ac.ping():
        raise RuntimeError("AnkiConnect not reachable — is Anki running?")

    data_dir.mkdir(parents=True, exist_ok=True)
    if media_dir is None:
        media_dir = data_dir / "anki_media"

    write_field_name_map(ac, data_dir)

    decks = ac.deck_names()
    logger.info("Found %d decks", len(decks))

    # Only export leaf decks to avoid duplicates
    leaf_decks = []
    for d in sorted(decks):
        if not any(other.startswith(d + "::") for other in decks):
            leaf_decks.append(d)
        else:
            logger.info("Skipping parent deck: %s", d)

    export: dict[str, list[dict]] = {}
    for deck in leaf_decks:
        try:
            notes = export_via_apkg(ac, deck, media_dir=media_dir)
            logger.info("%s: %d notes (via exportPackage)", deck, len(notes))
        except Exception as e:
            logger.warning(
                "%s: exportPackage failed (%s), trying notesInfo fallback...", deck, e
            )
            try:
                notes = export_via_notesinfo(ac, deck, media_dir=media_dir)
                logger.info("%s: %d notes (via multi+notesInfo)", deck, len(notes))
            except Exception as e2:
                logger.error("%s: FAILED - %s", deck, e2)
                notes = []

        if notes:
            export[deck] = notes

    # Save export JSON
    export_path = data_dir / "anki_export.json"
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(export, f, ensure_ascii=False, indent=2)
    logger.info("Saved export: %s", export_path)

    # Load into database
    db = CardDatabase(db_path=data_dir / "armenian_cards.db")
    cleanup_test_data(db)
    cleanup_html_in_existing_cards(db)
    total = load_export_into_db(export, db)

    # Remove export JSON after successful load
    export_path.unlink(missing_ok=True)
    logger.info("Pull pipeline complete: %d notes upserted", total)
    return total
