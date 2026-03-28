import pytest

from hytools.ingestion.acquisition import dpla


def test_normalize_title_fallback():
    doc = {"id": "abc123", "sourceResource": {}}
    norm = dpla._normalize_item(doc)
    assert norm["title"] == "abc123"


def test_normalize_language_iso():
    doc = {"id": "x", "sourceResource": {"language": [{"iso639_3": "hye", "name": "Eastern Armenian"}]}}
    norm = dpla._normalize_item(doc)
    assert norm["source_language_code"] == "hye"


def test_normalize_author_list_and_description():
    doc = {
        "id": "y",
        "sourceResource": {
            "title": ["T1"],
            "description": ["Desc part1", "Desc part2"],
            "creator": ["Author Name"]
        }
    }
    norm = dpla._normalize_item(doc)
    assert norm["title"] == "T1"
    assert "Desc part1" in norm["text"]
    assert norm["author"] == "Author Name"
