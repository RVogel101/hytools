from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hytools.ingestion.acquisition.search_seeder import (
    DuckDuckGoSearchSeeder,
    SearchSeedResult,
)
from hytools.ingestion.acquisition.web_crawler import CrawlResult, WAWebCrawler
from hytools.ingestion.runner import _build_stages


WA_TEXT = (
    "\u0544\u0565\u0566\u056b \u0574\u0567\u057b \u057f\u0578\u0582\u0576\u0568 "
    "\u0573\u0561\u0574\u0562\u0561\u0580\u0568 \u057d\u056f\u057d\u0561\u0582 "
    "\u0544\u0565\u0566\u056b \u0574\u0567\u057b \u057f\u0578\u0582\u0576\u0568 "
    "\u0573\u0561\u0574\u0562\u0561\u0580\u0568 \u057d\u056f\u057d\u0561\u0582"
)


def _make_crawler(tmp_path: Path, **overrides) -> WAWebCrawler:
    client = overrides.pop("client", None)
    config = {
        "seed_file": str(tmp_path / "crawler_seeds.txt"),
        "discovery_report": str(tmp_path / "crawler_found.csv"),
        "audit_report_csv": str(tmp_path / "wa_crawler_audit.csv"),
        "audit_report_json": str(tmp_path / "wa_crawler_audit.json"),
        "max_depth": 2,
        "max_pages_per_domain": 50,
        "max_total_pages": 50,
        "request_delay_seconds": 1.0,
        "allow_http": False,
        "min_text_chars": 20,
        "min_armenian_ratio": 0.10,
    }
    config.update(overrides)
    return WAWebCrawler(config, client=client)


class _StubRobots:
    def __init__(self, allowed: bool):
        self.allowed = allowed

    def can_fetch(self, _user_agent: str, _url: str) -> bool:
        return self.allowed


def test_load_seeds_from_file(tmp_path: Path):
    seed_file = tmp_path / "crawler_seeds.txt"
    seed_file.write_text(
        "# comment\nhttps://example.com\n\nhttps://sub.example.org/path\n",
        encoding="utf-8",
    )
    crawler = _make_crawler(tmp_path)

    assert crawler.load_seeds() == [
        "https://example.com/",
        "https://sub.example.org/path",
    ]


def test_normalize_url_removes_tracking_query_and_fragment(tmp_path: Path):
    crawler = _make_crawler(tmp_path)

    normalized = crawler.normalize_url(
        "https://Example.com/article?id=5&utm_source=test#section"
    )

    assert normalized == "https://example.com/article?id=5"


def test_check_robots_disallowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    crawler = _make_crawler(tmp_path)
    monkeypatch.setattr(crawler, "_get_robots_parser", lambda _url: _StubRobots(False))

    assert crawler.check_robots("https://example.com/") is False


def test_score_page_western_armenian(tmp_path: Path):
    crawler = _make_crawler(tmp_path)

    classification = crawler.classify_page(WA_TEXT)

    assert classification is not None
    assert classification["dialect_label"] == "likely_western"
    assert classification["source_language_code"] == "hyw"
    assert classification["internal_language_branch"] == "hye-w"


def test_score_page_non_armenian(tmp_path: Path):
    crawler = _make_crawler(tmp_path)

    classification = crawler.classify_page("this is plain english text only")

    assert classification is None
    assert crawler.score_page("this is plain english text only") == (0.0, 0.0)


def test_rate_limit_between_requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    crawler = _make_crawler(tmp_path, request_delay_seconds=1.0)
    monotonic_values = iter([0.0, 0.0, 0.5, 1.0])
    slept: list[float] = []

    monkeypatch.setattr(
        "hytools.ingestion.acquisition.web_crawler.time.monotonic",
        lambda: next(monotonic_values),
    )
    monkeypatch.setattr(
        "hytools.ingestion.acquisition.web_crawler.time.sleep",
        lambda seconds: slept.append(seconds),
    )

    crawler._respect_rate_limit("example.com")
    crawler._respect_rate_limit("example.com")

    assert slept == [pytest.approx(0.5)]


def test_crawl_respects_max_depth_and_pages_per_domain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    crawler = _make_crawler(
        tmp_path,
        max_depth=1,
        max_pages_per_domain=2,
    )

    def fake_result(url: str, depth: int, links: list[str]) -> CrawlResult:
        return CrawlResult(
            url=url,
            original_url=url,
            domain="example.com",
            depth=depth,
            status_code=200,
            text=WA_TEXT,
            title=f"Title {depth}",
            armenian_char_ratio=0.9,
            wa_score=6.0,
            links_found=links,
            fetch_time_ms=10,
            robots_allowed=True,
            dialect_label="likely_western",
            dialect_confidence=0.9,
            western_score=6.0,
            eastern_score=0.0,
            classical_score=0.0,
            source_language_code="hyw",
            internal_language_code="hy",
            internal_language_branch="hye-w",
            dialect="western_armenian",
        )

    results = {
        "https://example.com/": fake_result(
            "https://example.com/",
            0,
            [
                "https://example.com/page-1",
                "https://example.com/page-2",
            ],
        ),
        "https://example.com/page-1": fake_result(
            "https://example.com/page-1",
            1,
            ["https://example.com/page-1/deeper"],
        ),
        "https://example.com/page-2": fake_result(
            "https://example.com/page-2",
            1,
            [],
        ),
    }

    monkeypatch.setattr(crawler, "fetch_page", lambda url, depth=0: results[url])

    profiles = crawler.crawl(["https://example.com/"])

    assert len(profiles) == 1
    profile = profiles[0]
    assert profile.domain == "example.com"
    assert profile.pages_crawled == 2
    assert profile.pages_accepted == 2
    assert (tmp_path / "crawler_found.csv").exists()
    assert (tmp_path / "wa_crawler_audit.csv").exists()
    assert (tmp_path / "wa_crawler_audit.json").exists()


def test_discovery_report_contains_domain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    crawler = _make_crawler(tmp_path, max_depth=0)

    result = CrawlResult(
        url="https://example.com/",
        original_url="https://example.com/",
        domain="example.com",
        depth=0,
        status_code=200,
        text=WA_TEXT,
        title="Example",
        armenian_char_ratio=0.9,
        wa_score=6.0,
        links_found=[],
        fetch_time_ms=10,
        robots_allowed=True,
        dialect_label="likely_western",
        dialect_confidence=0.9,
        western_score=6.0,
        eastern_score=0.0,
        classical_score=0.0,
        source_language_code="hyw",
        internal_language_code="hy",
        internal_language_branch="hye-w",
        dialect="western_armenian",
    )

    monkeypatch.setattr(crawler, "fetch_page", lambda url, depth=0: result)
    crawler.crawl(["https://example.com/"])

    with (tmp_path / "crawler_found.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["domain"] == "example.com"
    assert rows[0]["pages_accepted"] == "1"


def test_search_seeder_filters_blocked_domains(monkeypatch: pytest.MonkeyPatch):
    seeder = DuckDuckGoSearchSeeder(
        queries=["western armenian diaspora"],
        blocked_domains={"blocked.example"},
    )
    fake_results = [
        SearchSeedResult(query="q", url="https://allowed.example/path/a", title="A"),
        SearchSeedResult(query="q", url="https://allowed.example/path/b", title="B"),
        SearchSeedResult(query="q", url="https://blocked.example/path", title="Blocked"),
    ]
    monkeypatch.setattr(seeder, "_iter_results", lambda _query: fake_results)

    seeds = seeder.discover_seed_urls()

    assert seeds == ["https://allowed.example"]


def test_runner_registers_web_crawler_stage():
    stages = _build_stages({"scraping": {"web_crawler": {"enabled": False}}})

    stage = next(stage for stage in stages if stage.name == "web_crawler")

    assert stage.module == "hytools.ingestion.acquisition.web_crawler"
    assert stage.supports_mongodb is True
    assert stage.enabled is False


def test_crawler_enqueues_borderline_page_for_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    client = MagicMock()
    client.review_queue = MagicMock()
    client.db = MagicMock()
    client.db.__getitem__.return_value = MagicMock()
    client.documents.find.return_value = []
    crawler = _make_crawler(tmp_path, client=client, max_depth=0)

    result = CrawlResult(
        url="https://example.com/",
        original_url="https://example.com/",
        domain="example.com",
        depth=0,
        status_code=200,
        text="placeholder text " * 30,
        title="Example",
        armenian_char_ratio=0.08,
        wa_score=3.0,
        links_found=[],
        fetch_time_ms=10,
        robots_allowed=True,
        dialect_label="inconclusive",
        dialect_confidence=0.2,
        western_score=3.0,
        eastern_score=2.7,
        classical_score=0.0,
        source_language_code="hy",
        internal_language_code="hy",
        internal_language_branch=None,
        dialect="unknown",
    )

    monkeypatch.setattr(crawler, "fetch_page", lambda url, depth=0: result)
    crawler.crawl(["https://example.com/"])

    doc = client.review_queue.insert_one.call_args[0][0]
    assert doc["reason"] == "borderline_crawl_page"
    assert doc["stage"] == "web_crawler"
    assert doc["item_id"] == "https://example.com/"