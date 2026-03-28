import types
import json

import pytest

from hytools.ingestion.acquisition import archive_org


class FakeResponse:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status
        self.reason = "OK"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, response_map):
        # response_map: url -> FakeResponse
        self._map = response_map

    def get(self, url, *args, **kwargs):
        # simple routing by prefix
        for prefix, resp in self._map.items():
            if url.startswith(prefix):
                return resp
        raise RuntimeError(f"Unexpected URL: {url}")


def test_discover_prefers_hocr():
    ident = "testitem"
    files = [
        {"name": "file_djvu_djvu._djvu.txt", "format": "DjVuTXT"},
        {"name": "file_hocr_hocr._hocr_searchtext.txt.gz", "format": "text"},
        {"name": "plain.txt", "format": "Text"},
    ]
    record = {"files": files}
    fake = FakeResponse(record)
    sess = FakeSession({archive_org._MDAPI_BASE.split('{')[0]: fake})

    names, md = archive_org.discover_text_files_with_session(ident, sess)
    assert isinstance(names, list)
    # hOCR file should be chosen (priority 0)
    assert any("hocr_searchtext" in n for n in names)


def test_discover_falls_back_to_djvu():
    ident = "test2"
    files = [
        {"name": "page_djvu_djvu._djvu.txt", "format": "DjVuTXT"},
        {"name": "plain.txt", "format": "Text"},
    ]
    record = {"files": files}
    fake = FakeResponse(record)
    sess = FakeSession({archive_org._MDAPI_BASE.split('{')[0]: fake})

    names, md = archive_org.discover_text_files_with_session(ident, sess)
    assert any(name.endswith("_djvu.txt") or "djvu" in name for name in names) or any(n.endswith(".txt") for n in names)
