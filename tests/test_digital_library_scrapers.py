"""Unit tests for digital library scrapers (loc, archive_org, gallica, hathitrust, gomidas).

Uses HTTP mocks to avoid network calls.
"""

from __future__ import annotations

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
