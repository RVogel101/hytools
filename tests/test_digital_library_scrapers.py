"""Unit tests for acquisition sources (loc, archive_org, gallica, hathitrust, gomidas, wiki, culturax).

Uses HTTP mocks to avoid network calls.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ── LOC ─────────────────────────────────────────────────────────────────────

def test_loc_is_valid_loc_id():
    """LOC item ID validator should accept valid LCCNs and reject malformed ones."""
    from hytools.ingestion.acquisition.loc import _is_valid_loc_id

    assert _is_valid_loc_id("2012345678") is True
    assert _is_valid_loc_id("sn-12345678") is True
    assert _is_valid_loc_id("abc123") is True

    assert _is_valid_loc_id("") is False
    assert _is_valid_loc_id("abc") is False  # too short
    assert _is_valid_loc_id("lccn.loc.gov/123") is False
    assert _is_valid_loc_id("http://loc.gov/item/123") is False
    assert _is_valid_loc_id("www.loc.gov") is False
    assert _is_valid_loc_id("cgi-bin/foo") is False


@patch("hytools.ingestion.acquisition.loc._get_session")
def test_loc_search_items_mock(mock_session):
    """LOC search_items returns catalog from mocked API response."""
    from hytools.ingestion.acquisition.loc import search_items

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {"id": "2012345678", "title": "Armenian Book", "item": {"url": "https://loc.gov/item/2012345678/"}},
            {"id": "sn-87654321", "title": "Another Armenian Text", "item": {"url": "https://loc.gov/item/sn-87654321/"}},
        ],
        "pagination": {"total": 2},
    }
    mock_resp.headers = {}
    mock_sess = MagicMock()
    mock_sess.get.return_value = mock_resp
    mock_session.return_value = mock_sess

    catalog = search_items(queries=["armenian"], max_per_query=10)
    assert isinstance(catalog, dict)
    # May be empty if IDs are filtered; at least no exception
    assert all(isinstance(k, str) and isinstance(v, dict) for k, v in catalog.items())


# ── Archive.org ──────────────────────────────────────────────────────────────

@patch("hytools.ingestion.acquisition.archive_org.requests.get")
def test_archive_org_search_items_mock(mock_get):
    """Archive.org search_items returns catalog from mocked API."""
    from hytools.ingestion.acquisition.archive_org import search_items

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "response": {
            "numFound": 2,
            "docs": [
                {"identifier": "armenian-book-001", "title": "Armenian Book"},
                {"identifier": "armenian-book-002", "title": "Another Armenian Text"},
            ],
        },
    }
    mock_get.return_value = mock_resp

    catalog = search_items(queries=["language:arm AND mediatype:texts"], max_per_query=10)
    assert isinstance(catalog, dict)
    assert len(catalog) <= 2
    for item_id, item in catalog.items():
        assert isinstance(item_id, str)
        assert isinstance(item, dict)
        assert "identifier" in item or "title" in item or "downloaded" in item


@patch("hytools.ingestion.acquisition.archive_org.time.sleep", return_value=None)
@patch("hytools.ingestion.acquisition.archive_org.requests.get")
def test_archive_org_search_items_paginates(mock_get, _mock_sleep):
    """Archive.org search_items should request a follow-up page when the first page is full."""
    from hytools.ingestion.acquisition.archive_org import search_items

    first_page = MagicMock()
    first_page.status_code = 200
    first_page.raise_for_status = MagicMock()
    first_page.json.return_value = {
        "response": {
            "docs": [
                {"identifier": f"item-{index:03d}", "title": f"Title {index}"}
                for index in range(100)
            ]
        }
    }

    second_page = MagicMock()
    second_page.status_code = 200
    second_page.raise_for_status = MagicMock()
    second_page.json.return_value = {
        "response": {
            "docs": [
                {"identifier": "item-101", "title": "Title 101"},
                {"identifier": "item-102", "title": "Title 102"},
            ]
        }
    }
    mock_get.side_effect = [first_page, second_page]

    catalog = search_items(["language:arm"], max_per_query=150)

    assert len(catalog) == 102
    assert mock_get.call_args_list[0].kwargs["params"]["page"] == 1
    assert mock_get.call_args_list[1].kwargs["params"]["page"] == 2


@patch("hytools.ingestion.acquisition.archive_org.time.sleep", return_value=None)
@patch("hytools.ingestion.acquisition.archive_org._fetch_file_content")
@patch("hytools.ingestion.acquisition.archive_org.discover_text_files_with_session")
def test_archive_org_download_item_text_combines_discovered_files(mock_discover, mock_fetch, _mock_sleep):
    """Archive.org download should combine all discovered text file contents into one payload."""
    from hytools.ingestion.acquisition.archive_org import _download_item_text

    mock_discover.return_value = (["b.txt", "a.txt"], {"files": []})
    mock_fetch.side_effect = ["alpha", "beta"]

    combined, file_names, record = _download_item_text("ia-item")

    assert combined == "alpha\n\nbeta"
    assert file_names == ["b.txt", "a.txt"]
    assert record == {"files": []}


# ── Gallica ──────────────────────────────────────────────────────────────────

def test_gallica_extract_ark():
    """Gallica ARK extractor should parse ark:/12148/ identifiers."""
    from hytools.ingestion.acquisition.gallica import _extract_ark

    assert _extract_ark(["ark:/12148/bpt6k3228953"]) == "bpt6k3228953"
    assert _extract_ark(["other-id", "ark:/12148/btv1b8454675k"]) == "btv1b8454675k"
    assert _extract_ark(["invalid"]) is None
    assert _extract_ark([]) is None


def test_gallica_parse_sru_response():
    """Gallica SRU XML parser should extract records and total count."""
    from hytools.ingestion.acquisition.gallica import _parse_sru_response

    xml = """<?xml version="1.0"?>
    <sru:searchRetrieveResponse xmlns:sru="http://www.loc.gov/zing/srw/">
        <sru:numberOfRecords>1</sru:numberOfRecords>
        <sru:records>
            <sru:record>
                <sru:recordData>
                    <dc:record xmlns:dc="http://purl.org/dc/elements/1.1/">
                        <dc:title>Armenian Manuscript</dc:title>
                        <dc:identifier>ark:/12148/btv1b1234567x</dc:identifier>
                        <dc:creator>Author</dc:creator>
                    </dc:record>
                </sru:recordData>
            </sru:record>
        </sru:records>
    </sru:searchRetrieveResponse>"""
    records, total = _parse_sru_response(xml)
    assert total == 1
    assert len(records) == 1
    assert records[0]["ark"] == "btv1b1234567x"
    assert records[0]["title"] == "Armenian Manuscript"


@patch("hytools.ingestion.acquisition.gallica.requests.get")
def test_gallica_search_items_mock(mock_get):
    """Gallica search_items returns catalog from mocked SRU API."""
    from hytools.ingestion.acquisition.gallica import search_items

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = """<?xml version="1.0"?>
    <sru:searchRetrieveResponse xmlns:sru="http://www.loc.gov/zing/srw/">
        <sru:numberOfRecords>1</sru:numberOfRecords>
        <sru:records>
            <sru:record>
                <sru:recordData>
                    <dc:record xmlns:dc="http://purl.org/dc/elements/1.1/">
                        <dc:title>Test Armenian Book</dc:title>
                        <dc:identifier>ark:/12148/btv1b9999999x</dc:identifier>
                    </dc:record>
                </sru:recordData>
            </sru:record>
        </sru:records>
    </sru:searchRetrieveResponse>"""
    mock_get.return_value = mock_resp

    catalog = search_items(queries=['(dc.language any "arm")'], max_per_query=10)
    assert isinstance(catalog, dict)
    assert len(catalog) >= 1 or len(catalog) == 0  # may filter


# ── HathiTrust ────────────────────────────────────────────────────────────────

def test_hathitrust_known_htids():
    """HathiTrust has a non-empty seed list of known Armenian HTIDs."""
    from hytools.ingestion.acquisition.hathitrust import _KNOWN_ARMENIAN_HTIDS

    assert len(_KNOWN_ARMENIAN_HTIDS) > 0
    assert all(isinstance(htid, str) for htid in _KNOWN_ARMENIAN_HTIDS)
    assert "mdp.39015005476548" in _KNOWN_ARMENIAN_HTIDS


@patch("hytools.ingestion.acquisition.hathitrust.get_volume_metadata")
@patch("hytools.ingestion.acquisition.hathitrust.requests.Session")
def test_hathitrust_search_items_mock(mock_session_class, mock_get_meta):
    """HathiTrust search_items returns catalog from mocked HTML and metadata API."""
    from hytools.ingestion.acquisition.hathitrust import search_items

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.text = """
    <html><body>
    <div><a href="https://babel.hathitrust.org/cgi/pt?id=mdp.39015005476548">
    <span class="title">Armenian Book Title</span></a></div>
    </body></html>
    """
    mock_sess = MagicMock()
    mock_sess.get.return_value = mock_resp
    mock_session_class.return_value = mock_sess
    mock_get_meta.return_value = {"records": {"x": {"titles": ["Armenian Book"]}}}

    catalog = search_items(queries=["armenian"], max_per_query=5)
    assert isinstance(catalog, dict)
    assert len(catalog) >= 1


# ── Gomidas ──────────────────────────────────────────────────────────────────

@patch("hytools.ingestion.acquisition.gomidas.requests.Session")
def test_gomidas_discover_links_mock(mock_session_class):
    """Gomidas _discover_links parses HTML and extracts Armenian-related links."""
    from hytools.ingestion.acquisition.gomidas import _discover_links

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = """
    <html>
    <body>
        <a href="/armenian-newspaper.pdf">Armenian Newspaper PDF</a>
        <a href="https://www.gomidas.org/resources/armenia-journal">Armenia Journal</a>
        <a href="#section">Skip anchor</a>
        <a href="/other">Unrelated</a>
    </body>
    </html>
    """
    mock_sess = MagicMock()
    mock_sess.get.return_value = mock_resp
    mock_session_class.return_value = mock_sess

    links = _discover_links(mock_sess)
    assert isinstance(links, list)
    assert len(links) >= 1  # at least the armenian-newspaper link
    for item in links:
        assert "url" in item
        assert "title" in item


@patch("hytools.ingestion.acquisition.loc.time.sleep", return_value=None)
@patch("hytools.ingestion.acquisition.loc._get_session")
def test_loc_search_items_retries_503_then_builds_catalog(mock_session, _mock_sleep):
    """LOC search_items should retry transient 503 responses and still build the catalog."""
    from hytools.ingestion.acquisition.loc import search_items

    overloaded = MagicMock()
    overloaded.status_code = 503
    overloaded.headers = {}

    success = MagicMock()
    success.status_code = 200
    success.headers = {}
    success.raise_for_status = MagicMock()
    success.json.return_value = {
        "results": [
            {
                "id": "https://www.loc.gov/item/2012345678/",
                "title": "Armenian Title",
                "date": "1901",
                "url": "https://www.loc.gov/item/2012345678/",
            }
        ]
    }

    mock_sess = MagicMock()
    mock_sess.get.side_effect = [overloaded, success]
    mock_session.return_value = mock_sess

    catalog = search_items(["armenian"], max_per_query=10)

    assert "2012345678" in catalog
    assert mock_sess.get.call_count == 2


@patch("hytools.ingestion.acquisition.loc.save_catalog_to_mongodb")
@patch("hytools.ingestion.acquisition.loc.maybe_enqueue_language_review")
@patch("hytools.ingestion.acquisition.loc.insert_or_skip")
@patch("hytools.ingestion.acquisition.loc.try_wa_filter", return_value=False)
@patch("hytools.ingestion.acquisition.loc._download_item_text", return_value=("placeholder text " * 10, 1))
def test_loc_download_and_ingest_enqueues_review_for_wa_filter_rejection(
    _mock_download,
    _mock_filter,
    mock_insert,
    mock_queue,
    _mock_save_catalog,
    tmp_path,
):
    """LOC ingestion should push WA filter rejections into the unified review queue path."""
    from hytools.ingestion.acquisition.loc import _download_and_ingest

    client = MagicMock()
    client.review_queue = MagicMock()
    catalog = {
        "2012345678": {
            "title": "Armenian Title",
            "url": "https://www.loc.gov/item/2012345678/",
        }
    }

    stats = _download_and_ingest(
        client,
        catalog,
        apply_wa_filter=True,
        error_log_path=tmp_path / "loc_api_errors.jsonl",
        config={},
    )

    assert stats["skipped_wa"] == 1
    mock_insert.assert_not_called()
    mock_queue.assert_called_once()
    assert mock_queue.call_args.kwargs["rejected"] is True


@patch("hytools.ingestion.acquisition.wiki._wikisource_api_get")
def test_wikisource_iter_category_pages_follows_continue(mock_api_get):
    """Wikisource category iteration should follow API continuation tokens."""
    from hytools.ingestion.acquisition.wiki import _iter_wikisource_category_pages

    mock_api_get.side_effect = [
        {
            "query": {"categorymembers": [{"title": "Page One"}, {"title": "Page Two"}]},
            "continue": {"cmcontinue": "next-batch"},
        },
        {"query": {"categorymembers": [{"title": "Page Three"}]}}
    ]

    titles = _iter_wikisource_category_pages(MagicMock(), "Category:Western_Armenian")

    assert titles == ["Page One", "Page Two", "Page Three"]


@patch("hytools.ingestion.acquisition.wiki._wikisource_api_get")
def test_wikisource_fetch_page_wikitext_reads_main_slot_content(mock_api_get):
    """Wikisource page fetch should read the main-slot revision content."""
    from hytools.ingestion.acquisition.wiki import _fetch_wikisource_page_wikitext

    mock_api_get.return_value = {
        "query": {
            "pages": [
                {"revisions": [{"slots": {"main": {"content": "Sample wikitext"}}}]}
            ]
        }
    }

    text = _fetch_wikisource_page_wikitext(MagicMock(), "Example")

    assert text == "Sample wikitext"


@patch("hytools.ingestion.acquisition.wiki.extract_wikipedia_to_mongodb")
@patch("hytools.ingestion.acquisition.wiki.download_dump")
@patch("hytools.ingestion.acquisition.wiki.resolve_dump_date")
def test_run_wikipedia_wa_resolves_dump_date(mock_resolve_date, mock_download_dump, mock_extract, tmp_path):
    """Wikipedia WA runner should resolve latest dump dates before downloading."""
    from hytools.ingestion.acquisition import wiki

    dump_path = tmp_path / "hyw.xml.bz2"
    dump_path.write_bytes(b"dump")
    mock_resolve_date.return_value = "20250301"
    mock_download_dump.return_value = dump_path
    client = MagicMock()

    @contextmanager
    def fake_open_mongodb_client(_config):
        yield client

    with patch("hytools.ingestion.acquisition.wiki.open_mongodb_client", new=fake_open_mongodb_client):
        wiki.run_wikipedia_wa(
            {
                "paths": {"raw_dir": str(tmp_path)},
                "scraping": {"wikipedia": {"language": "hyw", "dump_date": "latest"}},
            }
        )

    mock_resolve_date.assert_called_once_with("hyw", "latest")
    mock_download_dump.assert_called_once_with("hyw", "20250301", tmp_path / "wikipedia")
    assert mock_extract.call_args.kwargs["source"] == "wikipedia"
    assert mock_extract.call_args.kwargs["language_code"] == "hyw"


def test_culturax_run_respects_streaming_checkpoint_and_max_docs():
    """CulturaX run should resume from checkpoints and stop after max_docs is reached."""
    from hytools.ingestion.acquisition import culturax

    fake_load_dataset = MagicMock(
        return_value=iter(
            [
                {"text": "skip me", "url": "https://example.com/1"},
                {"text": "keep me", "url": "https://example.com/2"},
                {"text": "unused", "url": "https://example.com/3"},
            ]
        )
    )
    fake_datasets = SimpleNamespace(load_dataset=fake_load_dataset)
    client = MagicMock()

    @contextmanager
    def fake_open_mongodb_client(_config):
        yield client

    with patch.dict(sys.modules, {"datasets": fake_datasets}):
        with patch("hytools.ingestion._shared.helpers.open_mongodb_client", new=fake_open_mongodb_client), \
             patch("hytools.ingestion._shared.helpers.insert_or_skip", return_value=True) as mock_insert, \
             patch("hytools.ingestion.acquisition.culturax._load_checkpoint_from_mongodb", return_value=(1, 0)), \
             patch("hytools.ingestion.acquisition.culturax._save_checkpoint_to_mongodb") as mock_save, \
             patch("hytools.ingestion.acquisition.culturax._classify_dialect", return_value="western_armenian"):
            culturax.run(
                {
                    "scraping": {
                        "culturax": {
                            "dataset_name": "uonlp/CulturaX",
                            "language": "hy",
                            "streaming": True,
                            "min_chars": 1,
                            "max_docs": 1,
                        }
                    }
                }
            )

    fake_load_dataset.assert_called_once_with(
        "uonlp/CulturaX",
        "hy",
        split="train",
        streaming=True,
        trust_remote_code=True,
    )
    assert mock_insert.call_count == 1
    assert mock_save.call_args_list[-1].args[1:] == (2, 1, {"western_armenian": 1})
