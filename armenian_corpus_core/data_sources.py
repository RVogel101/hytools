"""Interfaces for external projects to obtain pre-aggregated corpus data.

This module is intended to become the "centralized database" mentioned by the
Hyebot project.  Downstream applications can import from here to retrieve
collections of document records (news, books, OCR corpora, etc.) without
needing to know where the raw data lives.

The functions below provide both stub interfaces (for downstream monkey-patching)
and concrete helpers that read from scraped data on disk when available.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from armenian_corpus_core.core_contracts import DocumentRecord
from armenian_corpus_core.core_contracts.hashing import sha256_normalized


def get_news_documents(data_dir: Path | None = None) -> Iterable[DocumentRecord]:
    """Yield all news-related documents that have been ingested into the core
    corpus.

    If *data_dir* is provided, scans the newspaper JSONL checkpoint files
    under ``data_dir/raw/newspapers/`` and yields ``DocumentRecord`` instances.
    Otherwise raises ``NotImplementedError`` so callers know to configure a
    data source.
    """
    if data_dir is None:
        raise NotImplementedError(
            "No news document source has been configured. "
            "Pass data_dir or see armenian_corpus_core.data_sources for integration guidelines."
        )

    import json

    newspapers_dir = data_dir / "raw" / "newspapers"
    if not newspapers_dir.exists():
        return

    for jsonl in newspapers_dir.rglob("*_articles.jsonl"):
        source_name = jsonl.stem.replace("_articles", "")
        with open(jsonl, encoding="utf-8") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                text = entry.get("text", "")
                if not text:
                    continue
                url = entry.get("url", "").strip()
                document_id = url or sha256_normalized(text)
                yield DocumentRecord(
                    document_id=document_id,
                    source_family=f"newspaper:{source_name}",
                    text=text,
                    source_url=url or None,
                    metadata={
                        "armenian_chars": entry.get("armenian_chars", 0),
                        "text_sha1": entry.get("text_sha1", ""),
                    },
                )


def get_news_sources() -> list[dict]:
    """Return metadata about the news sources available in the scraping package.

    Returns a list of dicts with ``name``, ``url``, and ``type`` keys,
    drawn from the newspaper and eastern_armenian scraper configurations.
    """
    sources: list[dict] = []

    try:
        from armenian_corpus_core.scraping.newspaper import _ALL_SOURCES
        for name, src in _ALL_SOURCES.items():
            sources.append({
                "name": name,
                "url": src.base_url,
                "type": "western_armenian_newspaper",
            })
    except ImportError:
        pass

    try:
        from armenian_corpus_core.scraping.eastern_armenian import NEWS_AGENCIES
        for name, cfg in NEWS_AGENCIES.items():
            sources.append({
                "name": name,
                "url": cfg["url"],
                "type": "eastern_armenian_news",
            })
    except ImportError:
        pass

    try:
        from armenian_corpus_core.scraping.rss_news import ALL_RSS_SOURCES
        for src in ALL_RSS_SOURCES:
            sources.append({
                "name": src["name"],
                "url": src["url"],
                "type": f"rss_{src.get('category', 'news')}",
            })
    except ImportError:
        pass

    return sources
