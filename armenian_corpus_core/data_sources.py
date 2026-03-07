"""Interfaces for external projects to obtain pre-aggregated corpus data.

This module is intended to become the "centralized database" mentioned by the
Hyebot project.  Downstream applications can import from here to retrieve
collections of document records (news, books, OCR corpora, etc.) without
needing to know where the raw data lives.

The functions below are currently stubs; integration repositories are expected
to monkey‑patch or extend them with concrete implementations that open the
relevant database or read from a cached JSONL export.
"""
from __future__ import annotations

from typing import Iterable

from armenian_corpus_core.core_contracts import DocumentRecord


def get_news_documents() -> Iterable[DocumentRecord]:
    """Yield all news-related documents that have been ingested into the core
    corpus.

    The upstream environment is responsible for providing a real data source.
    This could be an SQLite database, a collection of JSONL files, or a
    network service.  For now the function simply raises ``NotImplemented``
    so that callers know to override it during integration testing.
    """
    raise NotImplementedError(
        "No news document source has been configured. "
        "Please see armenian_corpus_core.data_sources for integration guidelines."
    )


def get_news_sources() -> Iterable[dict]:
    """Return metadata about the news sources currently aggregated by the core.

    Each item is a simple dict containing at least ``name`` and ``url``; extra
    fields (``rss_url``, ``category``, etc.) may be supplied by the provider.
    """
    # default implementation returns an empty list so that callers can safely
    # iterate without needing to import ``typing`` themselves.
    return []
