"""HathiTrust Digital Library scraper for Armenian texts.

Uses the HathiTrust Bibliographic API and Data API to search for and download
public-domain Armenian-language holdings. HathiTrust contains 17M+ digitized
books with strong coverage of 19th-20th century academic and religious texts.

A catalog file (``hathitrust_catalog.json``) tracks discovered items and their
download status for resume capability.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import requests

from ingestion._shared.helpers import (
    insert_or_skip,
    load_catalog_from_mongodb,
    log_item,
    log_stage,
    open_mongodb_client,
    save_catalog_to_mongodb,
    try_wa_filter,
)

logger = logging.getLogger(__name__)
_STAGE = "hathitrust"

_SOLR_API = "https://catalog.hathitrust.org/api/volumes/brief/json/{htid}"
_DATA_API = "https://babel.hathitrust.org/cgi/pt"
_REQUEST_DELAY = 2.0


def load_htrc_bulk(
    bulk_path: Path,
    client: object | None = None,
    config: dict | None = None,
) -> dict:
    """Load catalog and optionally ingest from HTRC bulk data (Extracted Features or full-text package).

    HTRC bulk data requires HTRC membership/agreement. See:
    https://www.hathitrust.org/htrc_ef
    https://www.hathitrust.org/member-libraries/resources-for-librarians/data-resources

    Args:
        bulk_path: Path to a HTRC bulk export (e.g. Extracted Features JSON directory or archive).
        client: MongoDBCorpusClient (optional); if None and config provided, uses open_mongodb_client.
        config: Pipeline config for MongoDB.

    Returns:
        Summary dict with keys like items_read, items_ingested, errors.
    """
    if not bulk_path.exists():
        logger.error("HTRC bulk path not found: %s", bulk_path)
        return {"items_read": 0, "items_ingested": 0, "errors": ["path_not_found"]}
    # Stub: full implementation would parse HTRC Extracted Features or full-text JSON
    # and insert into MongoDB with same schema as _download_and_ingest.
    logger.warning(
        "HTRC bulk loader is a stub. To integrate: (1) obtain HTRC bulk data (e.g. Extracted Features); "
        "(2) parse volume JSON per HTRC schema; (3) extract text or page-level features; "
        "(4) call insert_or_skip for each volume. Path was: %s", bulk_path,
    )
    return {"items_read": 0, "items_ingested": 0, "errors": ["stub_not_implemented"]}

DEFAULT_QUERIES: list[str] = [
    "language:arm",
    "armenian language",
    "\u0570\u0561\u0575\u0565\u0580\u0565\u0576",  # հայերեն
]


_SEARCH_URL = "https://catalog.hathitrust.org/Search/Results"
_SEARCH_HEADERS = {
    "User-Agent": "ArmenianCorpusCore/1.0 (Education/Research)",
    "Accept": "text/html",
}

_KNOWN_ARMENIAN_HTIDS: list[str] = [
    "mdp.39015005476548",
    "mdp.39015006854065",
    "inu.30000089516612",
    "mdp.39015064384558",
    "mdp.39015035625909",
    "uc1.b3440238",
    "mdp.39015028036804",
    "mdp.39015016311581",
    "njp.32101075741144",
    "mdp.39015063918729",
    "uc1.b4062901",
    "hvd.32044019890820",
    "mdp.39015010867453",
    "inu.30000049057303",
    "mdp.39015028036788",
    "mdp.39015016311599",
]


def search_items(
    queries: list[str],
    max_per_query: int = 200,
) -> dict[str, dict]:
    """Search HathiTrust catalog for Armenian texts.

    Uses a two-pronged approach:
    1. Scrapes the HathiTrust catalog search HTML for each query to discover
       volume HTIDs from search result links.
    2. Falls back to a curated seed list of known Armenian holdings so the
       scraper always has something to work with.

    For each discovered HTID, fetches metadata from the Bibliographic API.
    """
    catalog: dict[str, dict] = {}

    try:
        from bs4 import BeautifulSoup
        _bs4_available = True
    except ImportError:
        _bs4_available = False
        logger.warning("beautifulsoup4 not installed — using seed catalog only")

    if _bs4_available:
        session = requests.Session()
        session.headers.update(_SEARCH_HEADERS)

        for qi, query in enumerate(queries, 1):
            logger.info("HathiTrust search query %d/%d: %s", qi, len(queries), query)
            page = 1
            found_this_query = 0

            while found_this_query < max_per_query:
                try:
                    resp = session.get(
                        _SEARCH_URL,
                        params={"lookfor": query, "type": "all", "page": page},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "html.parser")

                    links = soup.select('a[href*="babel.hathitrust.org/cgi/pt?id="]')
                    if not links:
                        links = soup.select('a[href*="/Record/"]')

                    htids_on_page: list[tuple[str, Any]] = []
                    for link in links:
                        href = link.get("href", "")
                        if "id=" in href:
                            htid = href.split("id=")[-1].split("&")[0].split(";")[0]
                            if htid and htid not in catalog:
                                htids_on_page.append((htid, link))

                    if not htids_on_page:
                        break

                    for htid, link in htids_on_page:
                        title_tag = link.find_parent("div")
                        title = htid
                        if title_tag:
                            title_el = title_tag.select_one(".title, h3, h4")
                            if title_el:
                                title = title_el.get_text(strip=True)

                        catalog[htid] = {
                            "title": title,
                            "query": query,
                            "downloaded": False,
                            "pages_downloaded": 0,
                        }
                        found_this_query += 1
                        if found_this_query >= max_per_query:
                            break

                    page += 1
                    time.sleep(_REQUEST_DELAY)

                except requests.RequestException as exc:
                    logger.warning("Search error on query %d page %d: %s", qi, page, exc)
                    break

            logger.info("  Found %d items for query: %s", found_this_query, query)
            time.sleep(_REQUEST_DELAY)

    for htid in _KNOWN_ARMENIAN_HTIDS:
        if htid in catalog:
            continue
        meta = get_volume_metadata(htid)
        title = htid
        if meta:
            records = meta.get("records", {})
            for rec in records.values():
                title = rec.get("titles", [htid])[0] if rec.get("titles") else htid
                break
        catalog[htid] = {
            "title": title,
            "query": "seed_list",
            "downloaded": False,
            "pages_downloaded": 0,
        }
        time.sleep(0.5)

    logger.info("HathiTrust catalog: %d items total", len(catalog))
    return catalog


def build_catalog_from_hathifile(
    hathifile_path: Path,
    enrich_with_biblio: bool = True,
) -> dict[str, dict]:
    """Build catalog from a downloaded Hathifiles tab-delimited file.

    Download Hathifiles from:
    https://www.hathitrust.org/member-libraries/resources-for-librarians/data-resources/hathifiles

    Filter by language=arm for Armenian. Optionally enrich metadata via Bibliographic API.

    Args:
        hathifile_path: Path to hathi_full_*.txt or hathi_upd_*.txt
        enrich_with_biblio: If True, fetch title etc. from Bibliographic API per HTID

    Returns:
        Catalog dict {htid: {title, ...}}
    """
    catalog: dict[str, dict] = {}
    if not hathifile_path.exists():
        logger.error("Hathifile not found: %s", hathifile_path)
        return catalog

    lines = hathifile_path.read_text(encoding="utf-8", errors="replace").strip().split("\n")
    if not lines:
        return catalog

    header = lines[0].split("\t")
    col_lang = None
    col_htid = None
    for i, h in enumerate(header):
        h_lower = h.lower()
        if "lang" in h_lower and "language" in h_lower or h_lower == "lang":
            col_lang = i
        if "htid" in h_lower or h_lower == "id":
            col_htid = i
    if col_lang is None:
        col_lang = 11
    if col_htid is None:
        col_htid = 0

    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) <= max(col_lang, col_htid):
            continue
        lang = parts[col_lang].strip().lower() if col_lang < len(parts) else ""
        htid = parts[col_htid].strip() if col_htid < len(parts) else ""
        if lang != "arm" or not htid or "." not in htid:
            continue
        catalog[htid] = {"title": htid, "source": "hathifile", "downloaded": False, "pages_downloaded": 0}

    if enrich_with_biblio and catalog:
        logger.info("Enriching %d items via Bibliographic API...", len(catalog))
        for i, htid in enumerate(catalog):
            if i > 0 and i % 50 == 0:
                time.sleep(_REQUEST_DELAY)
            meta = get_volume_metadata(htid)
            if meta:
                for rec in meta.get("records", {}).values():
                    titles = rec.get("titles", [])
                    if titles:
                        catalog[htid]["title"] = titles[0]
                    break
            time.sleep(0.3)

    logger.info("Hathifile catalog: %d Armenian items", len(catalog))
    return catalog


def get_volume_metadata(htid: str) -> dict | None:
    """Retrieve metadata for a specific HathiTrust ID."""
    url = _SOLR_API.format(htid=htid.replace(":", "+"))
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("Metadata API error for %s: %s", htid, exc)
        return None


def _fetch_page_text(htid: str, page_seq: int) -> str | None:
    """Download OCR text for a single page. Returns content or None. No file writes."""
    params = {"id": htid, "seq": page_seq, "view": "plaintext"}
    try:
        resp = requests.get(_DATA_API, params=params, timeout=60)
        resp.raise_for_status()
        text = resp.text
        return text if len(text) >= 50 else None
    except Exception as exc:
        log_item(logger, "debug", _STAGE, htid, "fetch_page", status="error", error=str(exc), seq=page_seq)
        return None


def _download_volume_text(htid: str, max_pages: int = 1000) -> tuple[str | None, int]:
    """Download all pages of a volume. Returns (combined_text, count). No file writes."""
    parts: list[str] = []
    consecutive_fails = 0
    max_consecutive_fails = 5

    for seq in range(1, max_pages + 1):
        text = _fetch_page_text(htid, seq)
        if text:
            parts.append(text)
            consecutive_fails = 0
        else:
            consecutive_fails += 1
            if consecutive_fails >= max_consecutive_fails:
                break
        time.sleep(_REQUEST_DELAY)

    if not parts:
        return None, 0
    combined = "\n\n".join(parts)
    log_item(logger, "info", _STAGE, htid, "download_volume", status="ok", pages=len(parts), chars=len(combined))
    return combined, len(parts)


def _download_and_ingest(client, catalog: dict[str, dict], apply_wa_filter: bool, config: dict | None = None) -> dict:
    """Download volumes and insert directly to MongoDB. No file writes.

    When full text is unavailable (403, no pages, or too short), stores catalog metadata
    via Bibliographic API fallback (get_volume_metadata) so we have a record for discovery.
    """
    stats = {"inserted": 0, "duplicates": 0, "skipped_wa": 0, "skipped_short": 0, "metadata_only": 0}

    for i, (htid, item) in enumerate(catalog.items(), 1):
        if item.get("downloaded") and item.get("ingested") is not None:
            continue

        text, pages = _download_volume_text(htid)
        item["downloaded"] = True
        item["pages_downloaded"] = pages

        if not text or len(text) < 50:
            item["ingested"] = False
            stats["skipped_short"] += 1
            # Bibliographic API fallback: store metadata when full text unavailable
            meta = get_volume_metadata(htid)
            if meta:
                item["metadata_only"] = True
                item["biblio"] = meta
                records = meta.get("records", {})
                for rec in records.values():
                    if rec.get("titles"):
                        item["title"] = rec["titles"][0]
                    break
                stats["metadata_only"] += 1
                log_item(logger, "debug", _STAGE, htid, "biblio_fallback", status="metadata_stored")
            continue

        if apply_wa_filter and try_wa_filter(text[:5000]) is False:
            item["ingested"] = False
            stats["skipped_wa"] += 1
            log_item(logger, "debug", _STAGE, htid, "ingest", status="skipped_wa")
            continue

        ok = insert_or_skip(
            client,
            source="hathitrust",
            title=item.get("title", htid),
            text=text,
            url=f"https://babel.hathitrust.org/cgi/pt?id={htid}",
            metadata={"source_type": "book", "htid": htid},
            config=config,
        )
        item["ingested"] = ok
        if ok:
            stats["inserted"] += 1
        else:
            stats["duplicates"] += 1

        if i % 10 == 0:
            save_catalog_to_mongodb(client, "hathitrust", catalog)
            log_stage(logger, _STAGE, "progress", i=i, total=len(catalog), inserted=stats["inserted"])

    save_catalog_to_mongodb(client, "hathitrust", catalog)
    return stats


def run(config: dict) -> None:
    """Entry-point: catalog, download, and ingest. MongoDB only, no JSON/txt storage."""
    config = config or {}
    scrape_cfg = config.get("scraping", {}).get("hathitrust", {})
    queries = scrape_cfg.get("queries", DEFAULT_QUERIES)
    max_per_query = scrape_cfg.get("max_results", 200)
    apply_wa_filter = scrape_cfg.get("apply_wa_filter", True)

    log_stage(logger, _STAGE, "run_start", queries=len(queries))

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required but unavailable")
        catalog = load_catalog_from_mongodb(client, "hathitrust")
        if not catalog:
            hathifile = scrape_cfg.get("hathifile_path")
            if hathifile and Path(hathifile).exists():
                log_stage(logger, _STAGE, "building_from_hathifile", path=hathifile)
                catalog = build_catalog_from_hathifile(
                    Path(hathifile),
                    enrich_with_biblio=scrape_cfg.get("enrich_hathifile", True),
                )
            else:
                log_stage(logger, _STAGE, "building_from_search")
                catalog = search_items(queries, max_per_query)
            n = save_catalog_to_mongodb(client, "hathitrust", catalog)
            log_stage(logger, _STAGE, "catalog_saved", count=n)

        if catalog:
            stats = _download_and_ingest(client, catalog, apply_wa_filter, config)
            log_stage(logger, _STAGE, "run_complete", inserted=stats["inserted"], duplicates=stats["duplicates"],
                      skipped_wa=stats["skipped_wa"], skipped_short=stats["skipped_short"],
                      metadata_only=stats.get("metadata_only", 0))
        else:
            log_stage(logger, _STAGE, "run_complete", status="no_catalog")
