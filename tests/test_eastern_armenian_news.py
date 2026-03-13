"""Tests for Eastern Armenian news scraping helpers (moved from WesternArmenianLLM)."""

from ingestion.acquisition.news import (
    _ea_extract_article_page_metadata,
    _ea_extract_candidate_article_urls,
    _ea_extract_readable_text,
    _ea_parse_datetime,
    _ea_parse_rss_feed,
)


def test_parse_rss_feed_items():
    """RSS parser should return normalized items with title/link/date/category."""
    rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Test Feed</title>
        <item>
          <title>Test Title</title>
          <link>https://example.am/article-1</link>
          <pubDate>Wed, 05 Mar 2026 10:22:00 +0400</pubDate>
          <category>Politics</category>
        </item>
      </channel>
    </rss>
    """

    items = _ea_parse_rss_feed(rss, base_url="https://example.am")
    assert len(items) == 1
    assert items[0]["title"] == "Test Title"
    assert items[0]["url"] == "https://example.am/article-1"
    assert items[0]["category"] == "Politics"
    assert items[0]["published"] is not None


def test_extract_readable_text_prefers_article_paragraphs():
    """HTML extractor should pull readable text from article paragraphs."""
    html = """
    <html>
      <body>
        <header>Menu</header>
        <article>
          <p>This is a sufficiently long paragraph intended for extraction testing in the article container.</p>
          <p>The second paragraph is also long enough and should be preserved in the extracted output text.</p>
        </article>
      </body>
    </html>
    """

    text = _ea_extract_readable_text(html)
    assert "sufficiently long paragraph intended for extraction" in text
    assert "second paragraph is also long enough" in text


def test_parse_datetime_rfc822():
    """Datetime parser should handle RFC-822 timestamps from RSS feeds."""
    parsed = _ea_parse_datetime("Wed, 05 Mar 2026 10:22:00 +0400")
    assert parsed is not None
    assert "2026-03-05" in parsed


def test_extract_candidate_article_urls_filters_numeric_articles():
    """Fallback URL extractor should keep only article URLs matching configured patterns."""
    html = """
    <html><body>
      <a href="/hy/article/politics">Politics Category</a>
      <a href="/hy/article/332462">Article A</a>
      <a href="https://armtimes.com/hy/article/332463?ref=home">Article B</a>
      <a href="/hy/hashtag/kino">Hashtag</a>
    </body></html>
    """

    urls = _ea_extract_candidate_article_urls(
        html,
        base_url="https://armtimes.com",
        article_url_patterns=[r"^https?://(?:www\.)?armtimes\.com/hy/article/\d+/?$"],
    )

    assert urls == [
        "https://armtimes.com/hy/article/332462",
        "https://armtimes.com/hy/article/332463",
    ]


def test_extract_article_page_metadata_reads_title_and_published_time():
    """Article metadata parser should use OG title and published-time meta tag."""
    html = """
    <html>
      <head>
        <meta property="og:title" content="Sample Armenian Article" />
        <meta property="article:published_time" content="2026-03-05T08:00:00+04:00" />
        <meta property="article:section" content="Politics" />
      </head>
      <body><article><p>content</p></article></body>
    </html>
    """

    meta = _ea_extract_article_page_metadata(html)
    assert meta["title"] == "Sample Armenian Article"
    assert meta["category"] == "Politics"
    assert meta["published"] is not None
    assert "2026-03-05" in meta["published"]
