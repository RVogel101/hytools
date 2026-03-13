"""DPLA (Digital Public Library of America) scraper for Armenian and Armenia-related books.

Pulls metadata (and optional description-as-text) from the DPLA API:
- Armenian-language items: sourceResource.language.name=Armenian, type=text.
- English-language items about Armenia/Armenians: full-text search + language=English, type=text.

Language codes: hye (Eastern Armenian), hyw (Western Armenian), hyc (Classical Armenian),
hy (undetermined Armenian), eng (English). Uses sourceResource.language.iso639_3 when present.

Writing category is inferred from sourceResource.type and sourceResource.format when possible
(Book, Manuscript, etc.); see DPLA Field Reference.

Pagination: Uses page_size=500 (API max) and fetches all pages until no more results.
DPLA API caps at 100 pages per query (50,000 items max per query).

API key: Request via curl (see docs/development/requests_guides/request_dpla_api_key.sh or DPLA_API_KEY.md). Set
  config["scraping"]["dpla"]["api_key"] or env DPLA_API_KEY.

Usage::
    python -m ingestion.runner run --only dpla
    python -m ingestion.acquisition.dpla run
"""

from __future__ import annotations

import logging
import os
import time
from urllib.parse import quote_plus, urlencode

import requests

from ingestion._shared.helpers import (
    insert_or_skip,
    log_item,
    log_stage,
    open_mongodb_client,
)
from ingestion.enrichment.metadata_tagger import get_source_metadata

logger = logging.getLogger(__name__)
_STAGE = "dpla"

_API_BASE = "https://api.dp.la/v2/items"
# DPLA allows up to 500 items per page and max 100 pages per query (50k items per query)
_PAGE_SIZE = 500
_API_MAX_PAGE = 100
_REQUEST_DELAY = 0.5
_USER_AGENT = "ArmenianCorpusCore/1.0 (Education/Research; armenian-corpus-building)"

# English-language query: books about Armenians, Armenia, Armenian language, biographies, Armenian authors
_ENGLISH_ARMENIA_QUERY = "Armenia OR Armenian OR Armenians OR Armenian language OR Armenian history OR Armenian literature OR Armenian genocide OR Armenian diaspora OR biography Armenian"

# Restrict to text-type items (books, manuscripts, etc.)
_SOURCE_RESOURCE_TYPE_TEXT = "text"


def _get_api_key(config: dict) -> str | None:
    """Return DPLA API key from config or environment.

    If config has api_key set to the literal string \"DPLA_API_KEY\", the key is
    read from the environment variable DPLA_API_KEY (so the secret stays out of the YAML).
    """
    key = (config.get("scraping", {}) or {}).get("dpla", {}) or {}
    if isinstance(key, dict):
        raw = key.get("api_key") or os.environ.get("DPLA_API_KEY")
    else:
        raw = key
    if (raw or "").strip() == "DPLA_API_KEY":
        raw = os.environ.get("DPLA_API_KEY")
    return (raw or "").strip() or None


def _language_from_api(lang_list) -> str:
    """Map DPLA sourceResource.language to language_code.

    Returns: hye (Eastern Armenian), hyw (Western Armenian), hyc (Classical Armenian),
    hy (undetermined Armenian), eng (English), or und for other/unknown.
    Uses iso639_3 when present; otherwise infers from language name.
    """
    if not lang_list:
        return "und"
    first = lang_list[0] if isinstance(lang_list, list) else lang_list
    if not first:
        return "und"
    if isinstance(first, dict):
        iso = (first.get("iso639_3") or first.get("iso639-3") or "").strip().lower()
        name = (first.get("name") or "").strip().lower()
        if iso in ("hye", "hyw", "hyc"):
            return iso
        if iso == "eng":
            return "eng"
        if "armenian" in name:
            if "eastern" in name or "reformed" in name:
                return "hye"
            if "western" in name:
                return "hyw"
            if "classical" in name or "grabar" in name or "old" in name:
                return "hyc"
            return "hy"  # undetermined Armenian
        if "english" in name:
            return "eng"
        return "und"
    if isinstance(first, str):
        s = first.strip().lower()
        if "armenian" in s:
            return "hy"
        if "english" in s:
            return "eng"
    return "und"


def _infer_writing_category(sr: dict) -> str:
    """Infer writing_category from DPLA sourceResource.type and sourceResource.format.

    DPLA Field Reference: sourceResource.type (text, image, sound, etc.),
    sourceResource.format (file format, physical medium, e.g. Book, Manuscript).
    """
    fmt = sr.get("format")
    if isinstance(fmt, list):
        fmt = " ".join(str(f) for f in fmt if f).lower()
    else:
        fmt = (fmt or "").lower()
    type_val = (sr.get("type") or "")
    if isinstance(type_val, list):
        type_val = " ".join(str(t) for t in type_val if t).lower()
    else:
        type_val = type_val.lower()
    # Format often has "Book", "Manuscript", "Journal", etc. (case varies in API)
    if "manuscript" in fmt or "manuscript" in type_val:
        return "manuscript"
    if "journal" in fmt or "periodical" in fmt or "newspaper" in fmt:
        return "news"
    if "liturg" in fmt or "religious" in fmt or "prayer" in fmt:
        return "liturgical"
    if "scientific" in fmt or "research" in fmt or "article" in fmt:
        return "scientific_paper"
    if "book" in fmt or "book" in type_val or "text" in type_val:
        return "book"
    if "article" in fmt or "article" in type_val:
        return "article"
    # Default for text-type items
    return "book"


def _normalize_item(doc: dict) -> dict | None:
    """Extract title, text, url, language_code, writing_category, creator from a DPLA item doc."""
    sr = doc.get("sourceResource") or {}
    title = sr.get("title")
    if isinstance(title, list):
        title = title[0] if title else ""
    if not title or not str(title).strip():
        title = doc.get("id", "dpla_unknown")
    title = str(title).strip()

    description = sr.get("description")
    if isinstance(description, list):
        description = " ".join(str(d) for d in description if d)
    else:
        description = str(description or "").strip()
    text = description  # Use description as body when no full text

    url = doc.get("isShownAt")
    if not url and isinstance(doc.get("object"), dict):
        url = (doc.get("object") or {}).get("@id")
    if not isinstance(url, str):
        url = None
    url = (url or "").strip() or None

    lang_list = sr.get("language")
    language_code = _language_from_api(lang_list)

    writing_category = _infer_writing_category(sr)

    creator = sr.get("creator")
    if isinstance(creator, list):
        creator = creator[0] if creator else None
    author = (creator or "").strip() if isinstance(creator, str) else None

    return {
        "title": title,
        "text": text,
        "url": url,
        "language_code": language_code,
        "writing_category": writing_category,
        "author": author,
        "dpla_id": doc.get("id"),
        "data_provider": doc.get("dataProvider"),
    }


def _fetch_page(
    api_key: str,
    params: dict,
    session: requests.Session,
) -> tuple[list[dict], int]:
    """Fetch one page of DPLA items. Returns (docs, total_count)."""
    params = dict(params)
    params["api_key"] = api_key
    params.setdefault("page_size", _PAGE_SIZE)
    url = _API_BASE + "?" + urlencode(params, quote_via=quote_plus)
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    docs = data.get("docs") or []
    count = data.get("count", 0)
    return docs, count


def _run_query(
    config: dict,
    client,
    session: requests.Session,
    api_key: str,
    params: dict,
    label: str,
) -> tuple[int, int]:
    """Run a single DPLA query with full pagination; insert into MongoDB. Returns (inserted, skipped)."""
    params = dict(params)
    params["page_size"] = _PAGE_SIZE
    inserted, skipped = 0, 0
    page = 1
    while page <= _API_MAX_PAGE:
        params["page"] = page
        try:
            docs, total = _fetch_page(api_key, params, session)
        except Exception as e:
            log_item(logger, "warning", _STAGE, f"{label}_page_{page}", "fetch", error=str(e))
            logger.warning("DPLA %s page %s failed: %s", label, page, e)
            break
        if not docs:
            break
        for doc in docs:
            norm = _normalize_item(doc)
            if not norm:
                continue
            meta = get_source_metadata("dpla")
            meta["language_code"] = norm["language_code"]
            meta["writing_category"] = norm["writing_category"]
            meta["dpla_id"] = norm.get("dpla_id")
            meta["data_provider"] = norm.get("data_provider")
            ok = insert_or_skip(
                client,
                source="dpla",
                title=norm["title"],
                text=norm["text"],
                url=norm["url"],
                author=norm.get("author"),
                metadata=meta,
                config=config,
            )
            if ok:
                inserted += 1
                log_item(logger, "info", _STAGE, norm.get("dpla_id") or norm["title"][:50], "inserted")
            else:
                skipped += 1
        time.sleep(_REQUEST_DELAY)
        if len(docs) < _PAGE_SIZE:
            break
        page += 1
    return inserted, skipped


def run(config: dict) -> None:
    """Run DPLA ingestion: Armenian-language items and English-language Armenia-related items.
    Fetches all pages (up to API limit of 100 pages per query, 500 items/page).
    """
    api_key = _get_api_key(config)
    if not api_key:
        raise RuntimeError(
            "DPLA API key required. Set config['scraping']['dpla']['api_key'] or env DPLA_API_KEY. "
            "Request a key: curl -v -X POST https://api.dp.la/v2/api_key/YOUR_EMAIL@example.com"
        )
    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for DPLA ingestion")
        session = requests.Session()
        session.headers["User-Agent"] = _USER_AGENT
        log_stage(logger, _STAGE, "start")
        ins_a, skip_a = _run_query(
            config, client, session, api_key,
            {
                "sourceResource.language.name": "Armenian",
                "sourceResource.type": _SOURCE_RESOURCE_TYPE_TEXT,
            },
            "armenian",
        )
        ins_e, skip_e = _run_query(
            config, client, session, api_key,
            {
                "q": _ENGLISH_ARMENIA_QUERY,
                "sourceResource.language.name": "English",
                "sourceResource.type": _SOURCE_RESOURCE_TYPE_TEXT,
            },
            "english_armenia",
        )
        log_stage(logger, _STAGE, "done")
        logger.info(
            "DPLA: Armenian inserted=%s skipped=%s; English-Armenia inserted=%s skipped=%s",
            ins_a, skip_a, ins_e, skip_e,
        )


if __name__ == "__main__":
    import yaml
    from pathlib import Path
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    cfg = {}
    path = Path("config/settings.yaml")
    if path.is_file():
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    run(cfg)
