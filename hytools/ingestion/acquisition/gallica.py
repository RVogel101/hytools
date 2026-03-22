"""Gallica (French National Library) scraper for Armenian texts.

Uses the Gallica SRU API to search for Armenian-language monographs,
then downloads OCR text where available. Catalog-based with resume.

Note: If the stage is skipped, check config (scraping.gallica.enabled). When enabled,
SRU or OCR fetch can occasionally fail for some items; the pipeline logs and
continues. Use ``python -m ingestion.acquisition.gallica catalog --status`` to inspect catalog state.

Pipeline usage::

    python -m ingestion.runner run --only gallica

Standalone::

    python -m ingestion.acquisition.gallica run
    python -m ingestion.acquisition.gallica catalog --status
    python -m ingestion.acquisition.gallica catalog --refresh
"""

from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

from hytools.ingestion._shared.helpers import (
    compute_wa_score,
    insert_or_skip,
    is_western_armenian,
    load_catalog_from_mongodb,
    log_item,
    log_stage,
    open_mongodb_client,
    save_catalog_to_mongodb,
    WA_SCORE_THRESHOLD,
)

logger = logging.getLogger(__name__)
_STAGE = "gallica"

_SRU_API = "https://gallica.bnf.fr/SRU"
_REQUEST_DELAY = 1.0
_PAGE_SIZE = 50

# BnF uses "arm" for Armenian (dc.language)
DEFAULT_QUERIES: list[str] = [
    '(dc.language any "arm") and (dc.type any "monographie")',
    '(dc.language any "arm") and (dc.type any "fascicule")',
    '(metadata all "arménien") and (dc.type any "monographie")',
    '(dc.subject any "arménien") and (dc.type any "monographie")',
]


def _extract_ark(identifiers: list[str]) -> str | None:
    """Extract ARK from dc:identifier values (e.g. ark:/12148/bpt6k3228953)."""
    for val in identifiers:
        if isinstance(val, str) and "ark:/12148/" in val:
            match = re.search(r"ark:/12148/([a-z0-9]+)", val)
            if match:
                return match.group(1)
    return None


def _parse_sru_response(xml_text: str) -> tuple[list[dict], int]:
    """Parse SRU XML response, return list of records and total count."""
    records = []
    total = 0

    try:
        root = ET.fromstring(xml_text)
        # Strip namespaces for simpler traversal
        for el in root.iter():
            if "}" in el.tag:
                el.tag = el.tag.split("}", 1)[1]

        num_el = root.find(".//numberOfRecords")
        if num_el is not None and num_el.text:
            total = int(num_el.text)

        for rec in root.findall(".//record"):
            data = rec.find(".//recordData")
            if data is None:
                continue

            title = ""
            identifiers = []
            creators = []
            dates = []
            for child in data.iter():
                tag = (child.tag.split("}")[-1] if "}" in child.tag else child.tag).lower()
                text = "".join(child.itertext()).strip()
                if tag == "title":
                    title = text or title
                elif tag == "identifier":
                    identifiers.append(text)
                elif tag == "creator":
                    creators.append(text)
                elif "date" in tag and "indexation" not in tag:
                    dates.append(text)

            ark = _extract_ark(identifiers)
            if not ark:
                continue

            records.append({
                "ark": ark,
                "title": title or ark,
                "creator": creators[0] if creators else "",
                "date": dates[0] if dates else "",
                "downloaded": False,
                "has_ocr": None,
            })
    except ET.ParseError as exc:
        logger.warning("SRU XML parse error: %s", exc)

    return records, total


def search_items(
    queries: list[str],
    max_per_query: int = 200,
) -> dict[str, dict]:
    """Query Gallica SRU API and return catalog dict keyed by ARK."""
    catalog: dict[str, dict] = {}

    for qi, query in enumerate(queries, 1):
        logger.info("Gallica search query %d/%d: %s", qi, len(queries), query[:60])
        start = 1

        while start <= max_per_query:
            params = {
                "version": "1.2",
                "operation": "searchRetrieve",
                "query": query,
                "maximumRecords": _PAGE_SIZE,
                "startRecord": start,
            }
            try:
                resp = requests.get(_SRU_API, params=params, timeout=30)
                resp.raise_for_status()
                recs, total = _parse_sru_response(resp.text)
            except Exception as exc:
                logger.warning("Gallica SRU error on query %d start %d: %s", qi, start, exc)
                break

            for r in recs:
                ark = r.get("ark")
                if ark and ark not in catalog:
                    r["query_source"] = query
                    catalog[ark] = r

            if not recs or len(recs) < _PAGE_SIZE:
                break
            start += len(recs)
            if start > max_per_query:
                break
            time.sleep(_REQUEST_DELAY)

    logger.info("Gallica catalog: %d unique items", len(catalog))
    return catalog


def _fetch_ocr_text(ark: str) -> str | None:
    """Fetch OCR text for a Gallica document. Returns None if not available."""
    # Try document-level texte URL (some docs expose full text)
    url = f"https://gallica.bnf.fr/ark:/12148/{ark}.texte"
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            return None
        text = resp.text
        # May be HTML; strip tags if needed
        if "<" in text and ">" in text:
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 100:
            return None
        return text
    except Exception as exc:
        logger.debug("OCR fetch failed for %s: %s", ark, exc)
        return None


def _classify_dialect(text: str) -> str:
    return "western_armenian" if is_western_armenian(text) else "eastern_armenian"


def _download_and_ingest(client, catalog: dict[str, dict], config: dict | None = None) -> dict:
    """Fetch OCR text and insert directly to MongoDB. No file writes."""
    stats = {"inserted": 0, "duplicates": 0, "skipped": 0}
    for i, (ark, item) in enumerate(catalog.items(), 1):
        if item.get("downloaded") and item.get("ingested") is not None:
            continue

        text = _fetch_ocr_text(ark)
        item["downloaded"] = True
        item["has_ocr"] = text is not None

        if not text or len(text.strip()) < 50:
            item["ingested"] = False
            stats["skipped"] += 1
            log_item(logger, "debug", _STAGE, ark, "ingest", status="no_ocr_or_short")
            time.sleep(_REQUEST_DELAY)
            continue

        dialect = _classify_dialect(text)
        lang_code = "hyw" if dialect == "western_armenian" else "hye" if dialect == "eastern_armenian" else "hy"
        ok = insert_or_skip(
            client,
            source="gallica",
            title=item.get("title", ark),
            text=text.strip(),
            url=f"https://gallica.bnf.fr/ark:/12148/{ark}",
            metadata={
                "source_type": "library",
                "ark": ark,
                "source_language_code": lang_code,
                "publication_date": item.get("date") or None,
                "gallica_date": item.get("date", ""),
                "gallica_creator": item.get("creator", ""),
            },
            config=config,
        )
        item["ingested"] = ok
        if ok:
            stats["inserted"] += 1
            log_item(logger, "info", _STAGE, ark, "ingest", status="inserted", chars=len(text))
        else:
            stats["duplicates"] += 1

        if i % 10 == 0:
            save_catalog_to_mongodb(client, "gallica", catalog)
            log_stage(logger, _STAGE, "progress", i=i, total=len(catalog), inserted=stats["inserted"])
        time.sleep(_REQUEST_DELAY)

    save_catalog_to_mongodb(client, "gallica", catalog)
    return stats


def run(config: dict) -> None:
    """Entry-point: catalog, download, ingest. MongoDB only, no JSON/txt storage."""
    config = config or {}
    scrape_cfg = config.get("scraping", {}).get("gallica", {})
    queries = scrape_cfg.get("queries", DEFAULT_QUERIES)
    max_per_query = scrape_cfg.get("max_results", 200)

    log_stage(logger, _STAGE, "run_start", queries=len(queries))

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required but unavailable")
        catalog = load_catalog_from_mongodb(client, "gallica")
        if not catalog:
            log_stage(logger, _STAGE, "building_catalog")
            catalog = search_items(queries, max_per_query)
            save_catalog_to_mongodb(client, "gallica", catalog)
        stats = _download_and_ingest(client, catalog, config)
        log_stage(logger, _STAGE, "run_complete", inserted=stats["inserted"], duplicates=stats["duplicates"], skipped=stats["skipped"])


if __name__ == "__main__":
    import argparse
    import sys
    import yaml

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Gallica (BnF) Armenian texts scraper")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run full pipeline")
    run_p.add_argument("--config", type=Path, default=None)

    cat_p = sub.add_parser("catalog", help="Manage catalog (MongoDB only)")
    cat_group = cat_p.add_mutually_exclusive_group(required=True)
    cat_group.add_argument("--status", action="store_true")
    cat_group.add_argument("--refresh", action="store_true")
    cat_p.add_argument("--config", type=Path, default=None)
    cat_p.add_argument("--max-per-query", type=int, default=200)

    args = parser.parse_args()

    if args.command == "run":
        cfg = {}
        if args.config and args.config.exists():
            with open(args.config, encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}
        run(cfg)

    elif args.command == "catalog":
        cfg = {}
        if args.config and args.config.exists():
            with open(args.config, encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}
        with open_mongodb_client(cfg) as client:
            if not client:
                print("MongoDB unavailable")
            elif args.status:
                cat = load_catalog_from_mongodb(client, "gallica")
                total = len(cat)
                with_ocr = sum(1 for v in cat.values() if v.get("has_ocr"))
                print(f"Catalog (MongoDB): {total} items")
                print(f"  With OCR: {with_ocr}")
            elif args.refresh:
                existing = load_catalog_from_mongodb(client, "gallica")
                fresh = search_items(DEFAULT_QUERIES, args.max_per_query)
                for ark, item in fresh.items():
                    if ark not in existing:
                        existing[ark] = item
                    elif existing[ark].get("downloaded"):
                        existing[ark]["downloaded"] = True
                        existing[ark]["has_ocr"] = existing[ark].get("has_ocr")
                save_catalog_to_mongodb(client, "gallica", existing)
                print(f"Catalog refreshed: {len(existing)} items")

    else:
        parser.print_help()
        sys.exit(1)
