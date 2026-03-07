"""Western Armenian Wikipedia dump downloader and processor.

Downloads the hyw (Western Armenian) Wikipedia XML dump from
``dumps.wikimedia.org/hywwiki/`` and extracts plain text by streaming
the bz2-compressed XML.  Wikitext markup is cleaned via regex.

Supports both file-based storage and direct MongoDB insertion.
"""

from __future__ import annotations

import bz2
import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

try:
    from pymongo.errors import DuplicateKeyError  # type: ignore[reportMissingImports]
except ImportError:
    DuplicateKeyError = Exception  # placeholder when pymongo not installed

logger = logging.getLogger(__name__)

_DUMP_BASE = "https://dumps.wikimedia.org/{lang}wiki/{date}/"
_ARTICLES_DUMP = "{lang}wiki-{date}-pages-articles.xml.bz2"

# ── Wikitext cleanup regexes ────────────────────────────────────────────────
_RE_TEMPLATE = re.compile(r"\{\{[^}]*\}\}")
_RE_FILE_LINK = re.compile(r"\[\[(File|Image|Պատկ):.*?\]\]", re.IGNORECASE)
_RE_CATEGORY = re.compile(r"\[\[Category:.*?\]\]", re.IGNORECASE)
_RE_EXT_LINK = re.compile(r"\[https?://[^\]]*\]")
_RE_REF = re.compile(r"<ref[^>]*>.*?</ref>|<ref[^/]*/?>", re.DOTALL)
_RE_HTML_TAG = re.compile(r"<[^>]+>")
_RE_HEADING = re.compile(r"={2,6}\s*(.*?)\s*={2,6}")
_RE_BOLD_ITALIC = re.compile(r"'{2,5}")
_RE_LIST_MARKER = re.compile(r"^[*#:;]+\s*", re.MULTILINE)
_RE_TABLE = re.compile(r"\{\|.*?\|\}", re.DOTALL)
_RE_INTERNAL_LINK = re.compile(r"\[\[([^|\]]*\|)?([^\]]+)\]\]")
_RE_REDIRECT = re.compile(r"^#REDIRECT", re.IGNORECASE)


def _resolve_dump_date(lang: str, requested: str) -> str:
    """Return the latest available dump date if *requested* is 'latest'."""
    if requested != "latest":
        return requested
    url = _DUMP_BASE.format(lang=lang, date="latest") + "dumpstatus.json"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("version", "latest")
    except Exception:
        return "latest"


def download_dump(lang: str, date: str, dest_dir: Path) -> Path:
    """Download the Wikipedia articles XML dump and return its path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = _ARTICLES_DUMP.format(lang=lang, date=date)
    url = _DUMP_BASE.format(lang=lang, date=date) + filename
    dest = dest_dir / filename

    if dest.exists():
        logger.info("Dump already downloaded: %s", dest)
        return dest

    logger.info("Downloading Wikipedia dump from %s", url)
    with requests.get(url, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
    logger.info("Download complete: %s (%d bytes)", dest, dest.stat().st_size)
    return dest


def clean_wikitext(raw: str) -> str:
    """Strip wikitext markup from *raw* and return plain text."""
    text = raw
    text = _RE_TEMPLATE.sub("", text)
    text = _RE_TABLE.sub("", text)
    text = _RE_FILE_LINK.sub("", text)
    text = _RE_CATEGORY.sub("", text)
    text = _RE_REF.sub("", text)
    text = _RE_HTML_TAG.sub("", text)
    text = _RE_EXT_LINK.sub("", text)
    text = _RE_HEADING.sub(r"\1", text)
    text = _RE_BOLD_ITALIC.sub("", text)
    text = _RE_LIST_MARKER.sub("", text)
    text = _RE_INTERNAL_LINK.sub(r"\2", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_articles(dump_path: Path, output_dir: Path) -> int:
    """Stream the bz2 XML dump, extract and clean article text.

    Only article-namespace pages (ns == 0) are kept.  Redirect pages are
    skipped.  Each article is saved as a separate ``.txt`` file under
    *output_dir*.

    Returns the number of articles extracted.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Extracting articles from %s -> %s", dump_path, output_dir)

    count = 0
    with bz2.open(dump_path, "rt", encoding="utf-8") as fh:
        context = ET.iterparse(fh, events=("end",))
        title = ""
        ns = ""
        for _event, elem in context:
            tag = elem.tag.split("}", 1)[-1]

            if tag == "title":
                title = elem.text or ""
            elif tag == "ns":
                ns = elem.text or ""
            elif tag == "text" and ns == "0":
                raw = elem.text or ""
                if not raw or _RE_REDIRECT.match(raw):
                    elem.clear()
                    continue
                cleaned = clean_wikitext(raw)
                if len(cleaned) < 50:
                    elem.clear()
                    continue
                safe_name = re.sub(r'[<>:"/\\|?*]', "_", title)[:200]
                out_path = output_dir / f"{safe_name}.txt"
                out_path.write_text(cleaned, encoding="utf-8")
                count += 1
                if count % 1000 == 0:
                    logger.info("  Extracted %d articles...", count)
            if tag == "page":
                elem.clear()

    logger.info("Extraction complete: %d articles", count)
    return count


def extract_articles_to_mongodb(dump_path: Path, mongodb_client, lang: str = "hyw") -> dict:
    """Stream the bz2 XML dump and insert articles directly into MongoDB.

    Returns dict with stats: inserted, duplicates, errors, skipped.
    """
    logger.info("Extracting articles from %s -> MongoDB", dump_path)
    stats = {"inserted": 0, "duplicates": 0, "errors": 0, "skipped": 0}

    with bz2.open(dump_path, "rt", encoding="utf-8") as fh:
        context = ET.iterparse(fh, events=("end",))
        title = ""
        ns = ""

        for _event, elem in context:
            tag = elem.tag.split("}", 1)[-1]

            if tag == "title":
                title = elem.text or ""
            elif tag == "ns":
                ns = elem.text or ""
            elif tag == "text" and ns == "0":
                raw = elem.text or ""
                if not raw or _RE_REDIRECT.match(raw):
                    elem.clear()
                    stats["skipped"] += 1
                    continue

                cleaned = clean_wikitext(raw)
                if len(cleaned) < 50:
                    elem.clear()
                    stats["skipped"] += 1
                    continue

                try:
                    mongodb_client.insert_document(
                        source="wikipedia",
                        title=title,
                        text=cleaned,
                        metadata={
                            "source_type": "encyclopedia",
                            "language_code": lang,
                            "dump_file": dump_path.name,
                        },
                    )
                    stats["inserted"] += 1

                    if stats["inserted"] % 1000 == 0:
                        logger.info(
                            "  Inserted %d articles (duplicates: %d, errors: %d)...",
                            stats["inserted"],
                            stats["duplicates"],
                            stats["errors"],
                        )
                except DuplicateKeyError:
                    stats["duplicates"] += 1
                except Exception as e:
                    logger.error("Error inserting article '%s': %s", title, e)
                    stats["errors"] += 1

            if tag == "page":
                elem.clear()

    logger.info(
        "Extraction complete: %d inserted, %d duplicates, %d errors, %d skipped",
        stats["inserted"],
        stats["duplicates"],
        stats["errors"],
        stats["skipped"],
    )
    return stats


def run(config: dict, use_mongodb: bool = False) -> None:
    """Entry-point: download and extract Western Armenian Wikipedia."""
    raw_dir = Path(config["paths"]["raw_dir"]) / "wikipedia"
    wiki_cfg = config["scraping"]["wikipedia"]
    lang: str = wiki_cfg["language"]
    date: str = _resolve_dump_date(lang, wiki_cfg["dump_date"])

    dump_path = download_dump(lang, date, raw_dir)

    if use_mongodb:
        try:
            from pymongo import MongoClient  # type: ignore[reportMissingImports]

            mongodb_uri = config.get("database", {}).get("mongodb_uri", "mongodb://localhost:27017/")
            db_name = config.get("database", {}).get("mongodb_database", "western_armenian_corpus")

            logger.info("Using MongoDB storage")
            client = MongoClient(mongodb_uri)
            db = client[db_name]
            stats = extract_articles_to_mongodb(dump_path, db, lang)
            logger.info(
                "MongoDB insertion complete: %d inserted, %d duplicates",
                stats["inserted"],
                stats["duplicates"],
            )
            client.close()
        except ImportError:
            logger.error("pymongo not installed. Run: pip install pymongo")
            logger.info("Falling back to file-based storage")
            extract_articles(dump_path, raw_dir / "extracted")
    else:
        logger.info("Using file-based storage")
        extract_articles(dump_path, raw_dir / "extracted")
