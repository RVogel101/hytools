"""Helpers to map source rows into central core contracts."""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from core_contracts import DialectTag, DocumentRecord, LexiconEntry
from core_contracts.hashing import sha256_normalized


def _parse_json_field(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {}


def anki_card_row_to_lexicon_entry(row: Mapping[str, Any]) -> LexiconEntry:
    """Convert an ``anki_cards`` row into canonical ``LexiconEntry``."""

    return LexiconEntry(
        lemma=str(row.get("word", "")).strip(),
        translation=_nullable_text(row.get("translation")),
        pos=_nullable_text(row.get("pos")),
        pronunciation=_nullable_text(row.get("pronunciation")),
        frequency_rank=_nullable_int(row.get("frequency_rank")),
        syllable_count=_nullable_int(row.get("syllable_count")),
        dialect_tag=DialectTag.WESTERN_ARMENIAN,
        metadata={
            "anki_note_id": row.get("anki_note_id"),
            "deck_name": row.get("deck_name"),
            "sub_deck_name": row.get("sub_deck_name"),
            "custom_level": row.get("custom_level"),
            "metadata_json": _parse_json_field(row.get("metadata_json")),
            "morphology_json": _parse_json_field(row.get("morphology_json")),
        },
    )


def sentence_row_to_document_record(row: Mapping[str, Any]) -> DocumentRecord:
    """Convert a local ``sentences`` row into canonical ``DocumentRecord``."""

    text = str(row.get("armenian_text", "")).strip()
    source_family = "anki_sentences"
    source_url: Optional[str] = None

    return DocumentRecord(
        document_id=f"sentence:{row.get('id')}",
        source_family=source_family,
        text=text,
        title=_nullable_text(row.get("form_label")),
        source_url=source_url,
        content_hash=sha256_normalized(text),
        char_count=len(text),
        dialect_tag=DialectTag.WESTERN_ARMENIAN,
        metadata={
            "card_id": row.get("card_id"),
            "english_text": row.get("english_text"),
            "grammar_type": row.get("grammar_type"),
            "created_at": row.get("created_at"),
            "vocabulary_used": row.get("vocabulary_used"),
        },
    )



def _nullable_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def wa_fingerprint_row_to_document_record(row: Mapping[str, Any]) -> DocumentRecord:
    """Convert a WesternArmenianLLM fingerprint CSV row to ``DocumentRecord``.

    Note: fingerprint exports typically do not include raw text; the row often
    includes a pre-computed normalized hash (``sha256(text_normalized)``).
    """

    raw_dialect = str(row.get("dialect_tag", "")).strip().lower()
    if raw_dialect in {"western_armenian", "wa", "hyw"}:
        dialect = DialectTag.WESTERN_ARMENIAN
    elif raw_dialect in {"eastern_armenian", "ea", "hy"}:
        dialect = DialectTag.EASTERN_ARMENIAN
    elif raw_dialect == "mixed":
        dialect = DialectTag.MIXED
    else:
        dialect = DialectTag.UNKNOWN

    source = _nullable_text(row.get("source")) or "wa_export"
    path_id = _nullable_text(row.get("id/path")) or _nullable_text(row.get("id"))
    content_hash = _nullable_text(row.get("sha256(text_normalized)"))

    document_id = path_id or (f"sha256:{content_hash}" if content_hash else "unknown")
    title = _nullable_text(row.get("title"))
    char_count = _nullable_int(row.get("char_count"))

    return DocumentRecord(
        document_id=document_id,
        source_family=source,
        text="",
        title=title,
        source_url=path_id,
        content_hash=content_hash,
        char_count=char_count,
        dialect_tag=dialect,
        metadata={
            "source_path": path_id,
            "fingerprint_only": True,
        },
    )


def _nullable_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
