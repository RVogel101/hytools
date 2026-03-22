from __future__ import annotations

from hytools.ingestion._shared.helpers import (
    ArticleChunk,
    split_issue_into_articles,
)


def test_single_article_when_no_headers() -> None:
    text = "պարզ տեքստ\nերկրորդ գիծ\nերրորդ գիծ"
    articles = split_issue_into_articles(text, max_bytes=1_000_000)
    assert len(articles) == 1
    assert isinstance(articles[0], ArticleChunk)
    assert "պարզ տեքստ" in articles[0].text


def test_multiple_articles_with_headers() -> None:
    text = (
        "ՊԻՈՆԵՐ ԹԵՂԵԿԱԿԱՆ\n\n"
        "առաջին հոդվածի տեքստ\n\n"
        "ԳԼՈՒԽ ՄԱՍ ԱՐԱՑ\n\n"
        "երկրորդ հոդվածի տեքստ\n"
    )
    articles = split_issue_into_articles(text, max_bytes=1_000_000)
    # Expect two articles based on the two headers.
    assert len(articles) == 2
    titles = [a.title or "" for a in articles]
    assert titles[0].startswith("ՊԻՈՆԵՐ ԹԵՂԵԿԱԿԱՆ")
    assert titles[1].startswith("ԳԼՈՒԽ ՄԱՍ ԱՐԱՑ")


def test_max_bytes_enforced_by_subsplitting() -> None:
    base_para = "պարագիր " * 100
    long_text = ("ՎԵՐՆԱԳԻՐ\n\n" + ("\n\n".join([base_para] * 200)))
    # Force small max_bytes to trigger splitting.
    articles = split_issue_into_articles(long_text, max_bytes=5_000)
    # We still expect at least 2 chunks, all under limit.
    assert len(articles) >= 2
    for art in articles:
        assert len(art.text.encode("utf-8")) <= 5_000

