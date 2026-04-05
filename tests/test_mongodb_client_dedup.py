from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hytools.integrations.database.mongodb_client import DuplicateKeyError, MongoDBCorpusClient, _compute_text_hashes


def test_compute_text_hashes_returns_primary_and_normalized_hashes():
    content_hash, normalized_hash = _compute_text_hashes("  բարեւ\nաշխարհ  ")

    assert content_hash
    assert normalized_hash
    assert content_hash != normalized_hash


def test_insert_document_raises_before_insert_when_content_hash_exists():
    client = MongoDBCorpusClient()
    docs = MagicMock()
    docs.find_one.return_value = {"_id": "existing", "title": "Existing Title", "source": "news"}
    client._db = {"documents": docs}

    with pytest.raises(DuplicateKeyError):
        client.insert_document(source="news", title="Duplicate", text="same text")

    docs.insert_one.assert_not_called()