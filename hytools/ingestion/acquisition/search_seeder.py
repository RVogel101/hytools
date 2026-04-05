"""DuckDuckGo-based seed discovery for the web crawler.

This module is intentionally lightweight and optional: when the
``duckduckgo-search`` package is unavailable, callers simply receive no
additional seeds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Sequence
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


DEFAULT_QUERY_TEMPLATES: tuple[str, ...] = (
    "western armenian diaspora news",
    "western armenian literary magazine",
    "western armenian community site",
    "western armenian church site",
    "site:.am western armenian",
    "site:.org western armenian armenian diaspora",
    "site:.ca western armenian armenian community",
)


@dataclass(frozen=True)
class SearchSeedResult:
    query: str
    url: str
    title: str = ""
    snippet: str = ""


def _root_url(url: str) -> str | None:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def load_existing_corpus_seed_urls(client, *, limit: int = 250) -> list[str]:
    """Promote already-known corpus URLs into domain-level seeds.

    Existing corpus documents frequently point at high-value Armenian
    domains.  The crawler only needs the domain root as a seed because it
    performs its own breadth-first traversal from there.
    """

    if client is None:
        return []

    roots: list[str] = []
    seen: set[str] = set()
    try:
        cursor = client.documents.find(
            {
                "source": {"$ne": "web_crawler"},
                "metadata.url": {"$exists": True, "$nin": [None, ""]},
            },
            {"metadata.url": 1},
        ).limit(max(int(limit), 0))
        for doc in cursor:
            url = ((doc or {}).get("metadata") or {}).get("url")
            root = _root_url(url)
            if root and root not in seen:
                seen.add(root)
                roots.append(root)
    except Exception as exc:
        logger.warning("Search seeder: could not load corpus URL seeds: %s", exc)
    return roots


class DuckDuckGoSearchSeeder:
    """Discover new crawl seeds from DuckDuckGo search results."""

    def __init__(
        self,
        *,
        queries: Sequence[str] | None = None,
        max_results_per_query: int = 10,
        blocked_domains: Iterable[str] | None = None,
    ):
        self.queries = [q.strip() for q in (queries or DEFAULT_QUERY_TEMPLATES) if q and q.strip()]
        self.max_results_per_query = max(1, int(max_results_per_query))
        self.blocked_domains = {item.strip().lower() for item in (blocked_domains or []) if item}

    def _iter_results(self, query: str) -> Iterable[SearchSeedResult]:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            logger.warning(
                "DuckDuckGo search seeding requested but duckduckgo-search is not installed"
            )
            return []

        results: list[SearchSeedResult] = []
        try:
            with DDGS() as ddgs:
                for item in ddgs.text(query, max_results=self.max_results_per_query) or []:
                    href = (item or {}).get("href") or (item or {}).get("url") or ""
                    if not href:
                        continue
                    results.append(
                        SearchSeedResult(
                            query=query,
                            url=href,
                            title=(item or {}).get("title") or "",
                            snippet=(item or {}).get("body") or "",
                        )
                    )
        except Exception as exc:
            logger.warning("DuckDuckGo query failed for %r: %s", query, exc)
        return results

    def _is_allowed_result(self, result: SearchSeedResult) -> bool:
        parsed = urlparse(result.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False

        hostname = parsed.netloc.lower()
        for blocked in self.blocked_domains:
            if hostname == blocked or hostname.endswith(f".{blocked}"):
                return False
        return True

    def discover_seed_urls(self, extra_queries: Sequence[str] | None = None) -> list[str]:
        """Return unique root URLs discovered from configured queries."""

        seen: set[str] = set()
        seeds: list[str] = []
        queries = self.queries + [q.strip() for q in (extra_queries or []) if q and q.strip()]

        for query in queries:
            for result in self._iter_results(query):
                if not self._is_allowed_result(result):
                    continue
                root = _root_url(result.url)
                if root and root not in seen:
                    seen.add(root)
                    seeds.append(root)

        return seeds