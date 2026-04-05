"""Shared compatibility helpers for ingestion and acquisition modules."""

from __future__ import annotations

import html
import json
import logging
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from hytools.ingestion._shared.metadata import InternalLanguageBranch

import requests

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MongoDB helpers (kept compatible with prior public API)
# ---------------------------------------------------------------------------
try:
    from pymongo.errors import DuplicateKeyError  # type: ignore[reportMissingImports]
except ImportError:
    DuplicateKeyError = Exception  # type: ignore[misc,assignment]


def _get_mongodb_config(config: dict) -> tuple[str, str]:
    db_cfg = config.get("database", {})
    uri = db_cfg.get("mongodb_uri", "mongodb://localhost:27017/")
    db_name = db_cfg.get("mongodb_database", "western_armenian_corpus")
    return uri, db_name


@contextmanager
def open_mongodb_client(config: dict) -> Generator:
    try:
        from hytools.integrations.database.mongodb_client import MongoDBCorpusClient
    except ImportError:
        logger.error("pymongo not installed. Run: pip install pymongo")
        yield None
        return

    uri, db_name = _get_mongodb_config(config)
    client = MongoDBCorpusClient(uri=uri, database_name=db_name)
    try:
        client.connect()
        logger.info("Connected to MongoDB: %s", db_name)
    except Exception as exc:
        logger.error("MongoDB connection failed: %s", exc)
        yield None
        return
    try:
        yield client
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Backwards-compatible re-exports for legacy consumers
# Some modules import WA/EA marker getters and constants from
# `hytools.ingestion._shared.helpers`; those functions now live in
# `hytools.linguistics.dialect.branch_dialect_classifier`. Provide
# lightweight re-exports and reasonable defaults to avoid ImportError
# when older import paths are used.
# ---------------------------------------------------------------------------
try:
    from hytools.linguistics.dialect.branch_dialect_classifier import (
        WA_SCORE_THRESHOLD,
        _has_armenian_script as _any_armenian_script,
        classify_text_classification,
        compute_wa_score,
        get_classical_markers,
        get_armenian_punctuation,
        get_ea_regex_patterns,
        get_eastern_markers,
        get_lexical_markers,
        get_wa_standalone_patterns,
        get_wa_suffix_patterns,
        get_wa_vocabulary_markers,
        get_word_internal_e_long_re,
        get_word_ending_ay_re,
        get_word_ending_oy_re,
        get_wa_authors,
        get_wa_publication_cities,
        get_wa_score_threshold,
    )

    # Provide constants expected by older callers
    _ARMENIAN_PUNCT = get_armenian_punctuation()
    _WA_PUBLICATION_CITIES = list(get_wa_publication_cities())
    _EAST_ARMENIAN_AUTHORS = []

    import re as _re

    _REFORMED_SUFFIX_RE = _re.compile(r"\u0578\u0582\u0569\u0575\u0578\u0582\u0576")
    _CLASSICAL_SUFFIX_RE = _re.compile(r"\u0578\u0582\u0569\u056B\u0582\u0576")

    # Minimal placeholders for word-boundary helpers (previously provided)
    _ARM_WB_L = r""
    _ARM_WB_R = r""
    _ARM_PRECEDED = r""
except Exception:  # pragma: no cover - best-effort compatibility shim
    pass


_VALID_INTERNAL_LANGUAGE_BRANCHES = {
    "hye-w": InternalLanguageBranch.WESTERN_ARMENIAN.value,
    "western-armenian": InternalLanguageBranch.WESTERN_ARMENIAN.value,
    "western armenian": InternalLanguageBranch.WESTERN_ARMENIAN.value,
    "western_armenian": InternalLanguageBranch.WESTERN_ARMENIAN.value,
    "western": InternalLanguageBranch.WESTERN_ARMENIAN.value,
    "hyw": InternalLanguageBranch.WESTERN_ARMENIAN.value,
    "hye-e": InternalLanguageBranch.EASTERN_ARMENIAN.value,
    "eastern-armenian": InternalLanguageBranch.EASTERN_ARMENIAN.value,
    "eastern armenian": InternalLanguageBranch.EASTERN_ARMENIAN.value,
    "eastern_armenian": InternalLanguageBranch.EASTERN_ARMENIAN.value,
    "eastern": InternalLanguageBranch.EASTERN_ARMENIAN.value,
    "hye": InternalLanguageBranch.EASTERN_ARMENIAN.value,
    "eng": InternalLanguageBranch.ENGLISH.value,
    "english": InternalLanguageBranch.ENGLISH.value,
}

_WIKITEXT_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_WIKITEXT_REF_RE = re.compile(r"<ref[^>/]*?>.*?</ref>", re.IGNORECASE | re.DOTALL)
_WIKITEXT_REF_SELF_CLOSING_RE = re.compile(r"<ref[^>]*/>", re.IGNORECASE)
_WIKITEXT_TABLE_RE = re.compile(r"\{\|.*?\|\}", re.DOTALL)
_WIKITEXT_TEMPLATE_RE = re.compile(r"\{\{[^{}]*\}\}")
_WIKITEXT_FILE_RE = re.compile(r"\[\[(?:file|image|category):[^\]]+\]\]", re.IGNORECASE)
_WIKITEXT_LINK_WITH_LABEL_RE = re.compile(r"\[\[([^|\]]+)\|([^\]]+)\]\]")
_WIKITEXT_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_WIKITEXT_EXTERNAL_LINK_RE = re.compile(r"\[https?://[^\s\]]+\s*([^\]]*)\]")
_WIKITEXT_HEADING_RE = re.compile(r"^={2,}\s*(.*?)\s*={2,}$", re.MULTILINE)
_WIKITEXT_HTML_RE = re.compile(r"<[^>]+>")
_WIKIMEDIA_DUMP_DATE_RE = re.compile(r'href="(\d{8})/"')


def normalize_internal_language_branch(value: str | None) -> str | None:
    """Normalize language branch aliases to canonical internal values."""
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("_", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.replace(" ", "-")
    return _VALID_INTERNAL_LANGUAGE_BRANCHES.get(normalized)


def is_valid_internal_language_branch(value: str | None) -> bool:
    """Return True when *value* maps to a known internal language branch."""
    return normalize_internal_language_branch(value) is not None


def try_wa_filter(text: str) -> bool | None:
    """Compatibility WA filter.

    Returns ``True`` for confidently Western Armenian, ``False`` for
    confidently Eastern / non-Armenian text, and ``None`` for ambiguous or
    classical Armenian content that should stay reviewable.
    """
    sample = (text or "")[:12000]
    if not sample.strip():
        return False
    if not _any_armenian_script(sample):
        return False

    result = classify_text_classification(sample)
    label = str(result.get("label", "inconclusive") or "inconclusive")
    confidence = float(result.get("confidence", 0.0) or 0.0)
    western_score = float(result.get("western_score", 0.0) or 0.0)
    eastern_score = float(result.get("eastern_score", 0.0) or 0.0)

    if label == "likely_western":
        return True
    if label == "likely_eastern" and eastern_score > western_score and confidence >= 0.35:
        return False
    if western_score >= WA_SCORE_THRESHOLD and western_score >= eastern_score:
        return True
    if eastern_score >= WA_SCORE_THRESHOLD and eastern_score > western_score and confidence >= 0.35:
        return False
    return None


def load_catalog_from_mongodb(client: Any, source: str) -> dict[str, dict]:
    """Load a source catalog from MongoDB."""
    if client is None:
        return {}
    return client.get_catalog(source)


def save_catalog_to_mongodb(client: Any, source: str, catalog: dict[str, dict]) -> int:
    """Persist a source catalog to MongoDB."""
    if client is None:
        return 0
    return client.upsert_catalog_items(source, catalog)


def _format_log_fields(fields: dict[str, Any]) -> str:
    parts = []
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, (dict, list, tuple)):
            rendered = json.dumps(value, ensure_ascii=False)
        else:
            rendered = str(value)
        parts.append(f"{key}={rendered}")
    return " ".join(parts)


def log_stage(logger_obj: logging.Logger, stage: str, event: str, **fields: Any) -> None:
    """Emit a structured stage-level log message."""
    suffix = _format_log_fields(fields)
    message = f"[{stage}] {event}"
    if suffix:
        message = f"{message} {suffix}"
    logger_obj.info(message)


def log_item(
    logger_obj: logging.Logger,
    level: str,
    stage: str,
    item_id: str,
    action: str,
    **fields: Any,
) -> None:
    """Emit a structured item-level log message."""
    suffix = _format_log_fields(fields)
    message = f"[{stage}] item={item_id} action={action}"
    if suffix:
        message = f"{message} {suffix}"
    log_fn = getattr(logger_obj, level.lower(), logger_obj.info)
    log_fn(message)


def is_redirect(text: str) -> bool:
    """Return True when a MediaWiki text payload is a redirect."""
    return bool(re.match(r"^\s*#(?:redirect|վերաուղղում)\b", text or "", re.IGNORECASE))


def clean_wikitext(raw: str) -> str:
    """Apply conservative wikitext cleanup for dump and API ingestion."""
    text = raw or ""
    text = _WIKITEXT_COMMENT_RE.sub("", text)
    text = _WIKITEXT_REF_RE.sub("", text)
    text = _WIKITEXT_REF_SELF_CLOSING_RE.sub("", text)
    text = _WIKITEXT_TABLE_RE.sub("", text)

    previous = None
    while previous != text:
        previous = text
        text = _WIKITEXT_TEMPLATE_RE.sub("", text)

    text = _WIKITEXT_FILE_RE.sub("", text)
    text = _WIKITEXT_LINK_WITH_LABEL_RE.sub(r"\2", text)
    text = _WIKITEXT_LINK_RE.sub(lambda match: match.group(1).split("|")[-1], text)
    text = _WIKITEXT_EXTERNAL_LINK_RE.sub(lambda match: (match.group(1) or "").strip(), text)
    text = _WIKITEXT_HEADING_RE.sub(r"\1", text)
    text = _WIKITEXT_HTML_RE.sub("", text)
    text = text.replace("'''", "").replace("''", "")
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def resolve_dump_date(language: str, requested: str | None = "latest") -> str:
    """Resolve a Wikimedia dump date, fetching the latest when requested."""
    if requested and requested != "latest":
        return requested

    url = f"https://dumps.wikimedia.org/{language}wiki/"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    matches = _WIKIMEDIA_DUMP_DATE_RE.findall(response.text)
    if not matches:
        raise RuntimeError(f"No dump dates found for {language}wiki")
    return max(matches)


def download_dump(language: str, dump_date: str, raw_dir: Path) -> Path:
    """Download a Wikimedia XML dump to *raw_dir* if it is not already present."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{language}wiki-{dump_date}-pages-articles-multistream.xml.bz2"
    destination = raw_dir / filename
    if destination.exists():
        return destination

    url = f"https://dumps.wikimedia.org/{language}wiki/{dump_date}/{filename}"
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()
    with destination.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)
    return destination


# ---------------------------------------------------------------------------
# Canonical insert helper — used by every scraper in acquisition/
# ---------------------------------------------------------------------------

def insert_or_skip(
    client,
    source: str | None = None,
    title: str | None = None,
    text: str | None = None,
    url: str | None = None,
    author: str | None = None,
    metadata: dict | None = None,
    config: dict | None = None,
    *,
    doc: "ScrapedDocument | None" = None,
) -> bool:
    """Insert a document via *client* or skip if it already exists.

    Accepts **either** a :class:`ScrapedDocument` via *doc* **or** the
    legacy positional / keyword arguments used by existing scrapers.
    When *doc* is supplied the positional args are ignored.

    Returns ``True`` when the document was inserted, ``False`` when it
    was skipped (duplicate content hash).
    """
    from hytools.ingestion._shared.scraped_document import ScrapedDocument

    if doc is not None:
        # Auto-compute quantitative linguistics if not already populated.
        if doc.char_count is None and doc.text and doc.text.strip():
            try:
                doc.compute_standard_linguistics()
            except Exception:
                logger.debug(
                    "compute_standard_linguistics failed for %s",
                    doc.source_family,
                    exc_info=True,
                )
        warnings = doc.validate()
        for w in warnings:
            logger.warning("ScrapedDocument validation: %s [%s]", w, doc.source_family)
    else:
        # Legacy call-path — forward positional args straight to the client.
        doc = None  # sentinel: use raw args below

    try:
        if doc is not None:
            d = doc.to_insert_dict()
            client.insert_document(
                source=d["source"],
                title=d.get("title") or "",
                text=d["text"],
                url=d.get("url"),
                author=d.get("author"),
                metadata=d.get("metadata"),
            )
        else:
            client.insert_document(
                source=source or "",
                title=title or "",
                text=text or "",
                url=url,
                author=author,
                metadata=metadata,
            )
        return True
    except DuplicateKeyError:
        logger.debug("Duplicate skipped: %s / %s", source or (doc and doc.source_family), title or (doc and doc.title))
        return False
    except Exception:
        logger.debug("insert_or_skip failed for %s / %s", source or (doc and doc.source_family), title or (doc and doc.title), exc_info=True)
        return False

