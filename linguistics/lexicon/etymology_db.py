"""Etymology and loanword-origin storage (Phase 1: Wiktextract/kaikki import).

Schema: lemma -> source (wiktionary | nayiri | manual), confidence,
optional etymology_text and relationship types. Stored in MongoDB collection
`etymology`. Used for loanword tracking and dictionary lookup.

See docs/development/ETYMOLOGY_STEM_TRANSLITERATION_STRATEGIES.md and
docs/concept_guides/MONGODB_CORPUS_SCHEMA.md.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

SOURCE_WIKTIONARY = "wiktionary"
SOURCE_NAYIRI = "nayiri"
SOURCE_MANUAL = "manual"
DEFAULT_WIKTIONARY_CONFIDENCE = 0.85


def _normalize_lemma(word: str) -> str:
    """Normalize lemma for storage (NFC, lowercase) so lookup matches tokenizer output."""
    try:
        from cleaning.armenian_tokenizer import normalize
        return normalize(word.strip()) if word else ""
    except ImportError:
        import unicodedata
        return unicodedata.normalize("NFC", (word or "").strip().lower())


def normalize_lemma(word: str) -> str:
    """Public: same normal form as stored in etymology collection."""
    return _normalize_lemma(word)


def _extract_relationships_from_categories(categories: list[str]) -> list[str]:
    """Map Wiktionary category strings to relationship type labels."""
    out: list[str] = []
    for cat in categories or []:
        cat_lower = cat.lower()
        if "borrowed from" in cat_lower or "terms borrowed from" in cat_lower:
            m = re.search(r"from\s+(\w+)", cat_lower)
            if m:
                out.append("borrowed_from_" + m.group(1).lower())
        if "derived from" in cat_lower:
            m = re.search(r"from\s+(\w+)", cat_lower)
            if m:
                out.append("derived_from_" + m.group(1).lower())
    return list(dict.fromkeys(out))


def wiktextract_line_to_etymology_doc(line: dict[str, Any], confidence: float = DEFAULT_WIKTIONARY_CONFIDENCE) -> dict[str, Any] | None:
    """Convert a single Wiktextract JSONL line (Armenian) to an etymology document."""
    lang = (line.get("lang_code") or "").lower() or (line.get("lang") or "")
    if lang != "hy" and "armenian" not in (lang or "").lower():
        return None

    lemma_raw = line.get("head") or line.get("word") or ""
    if not lemma_raw or not isinstance(lemma_raw, str):
        return None

    lemma = _normalize_lemma(lemma_raw)
    if not lemma:
        return None

    etymology_text = line.get("etymology_text")
    if isinstance(etymology_text, list):
        etymology_text = " ".join(str(x) for x in etymology_text) if etymology_text else None
    elif not isinstance(etymology_text, str):
        etymology_text = None

    relationships: list[str] = []
    for sense in line.get("senses") or []:
        if isinstance(sense, dict):
            relationships.extend(_extract_relationships_from_categories(sense.get("categories") or []))
    relationships.extend(_extract_relationships_from_categories(line.get("categories") or []))
    relationships = list(dict.fromkeys(relationships))

    return {
        "lemma": lemma,
        "source": SOURCE_WIKTIONARY,
        "confidence": confidence,
        "etymology_text": etymology_text,
        "relationships": relationships,
        "updated_at": datetime.now(timezone.utc),
        "pos": line.get("pos"),
        "raw_head": lemma_raw[:200],
    }


def upsert_etymology(collection: Any, doc: dict[str, Any]) -> bool:
    """Insert or update one etymology document by lemma (unique)."""
    if not doc or not doc.get("lemma"):
        return False
    lemma = doc["lemma"]
    update = {k: v for k, v in doc.items() if k != "lemma"}
    update["updated_at"] = datetime.now(timezone.utc)
    try:
        result = collection.update_one(
            {"lemma": lemma},
            {"$set": update},
            upsert=True,
        )
        return bool(result.upserted_count or result.modified_count)
    except Exception as e:
        logger.warning("etymology upsert failed for %s: %s", lemma[:50], e)
        return False


def load_wiktextract_jsonl(path: str | Path, lang_filter: str = "hy", max_entries: int | None = None) -> Iterable[dict[str, Any]]:
    """Yield Wiktextract JSONL lines filtered by language."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            lang = (obj.get("lang_code") or "").lower() or (obj.get("lang") or "")
            if lang != lang_filter and "armenian" not in (lang or "").lower():
                continue
            count += 1
            if max_entries is not None and count > max_entries:
                return
            yield obj


def import_etymology_from_wiktextract(
    jsonl_path: str | Path,
    collection: Any,
    *,
    max_entries: int | None = None,
    confidence: float = DEFAULT_WIKTIONARY_CONFIDENCE,
    log_every: int = 5000,
) -> tuple[int, int]:
    """Read Wiktextract JSONL and upsert Armenian entries. Returns (processed_count, upserted_count)."""
    processed = 0
    upserted = 0
    for line in load_wiktextract_jsonl(jsonl_path, max_entries=max_entries):
        doc = wiktextract_line_to_etymology_doc(line, confidence=confidence)
        if doc and upsert_etymology(collection, doc):
            upserted += 1
        processed += 1
        if log_every and processed % log_every == 0:
            logger.info("etymology import: processed=%d upserted=%d", processed, upserted)
    return processed, upserted


__all__ = [
    "SOURCE_WIKTIONARY",
    "SOURCE_NAYIRI",
    "SOURCE_MANUAL",
    "DEFAULT_WIKTIONARY_CONFIDENCE",
    "wiktextract_line_to_etymology_doc",
    "upsert_etymology",
    "load_wiktextract_jsonl",
    "import_etymology_from_wiktextract",
    "normalize_lemma",
]
