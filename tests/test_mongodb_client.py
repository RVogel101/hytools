"""Tests for hytools.integrations.database.mongodb_client (mock-based, no live MongoDB)."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime

from hytools.integrations.database.mongodb_client import MongoDBCorpusClient, _mongo_retry


class TestMongoDBCorpusClientInit:
    def test_defaults(self):
        client = MongoDBCorpusClient()
        assert client.uri == "mongodb://localhost:27017/"
        assert client.database_name == "western_armenian_corpus"
        assert client._client is None
        assert client._db is None

    def test_custom_params(self):
        client = MongoDBCorpusClient(uri="mongodb://host:1234/", database_name="test_db")
        assert client.uri == "mongodb://host:1234/"
        assert client.database_name == "test_db"

    def test_db_property_raises_when_not_connected(self):
        client = MongoDBCorpusClient()
        with pytest.raises(RuntimeError, match="Not connected"):
            _ = client.db


class TestContextManager:
    @patch.object(MongoDBCorpusClient, "connect")
    @patch.object(MongoDBCorpusClient, "close")
    def test_context_manager(self, mock_close, mock_connect):
        with MongoDBCorpusClient() as client:
            mock_connect.assert_called_once()
        mock_close.assert_called_once()


class TestClose:
    def test_close_when_connected(self):
        client = MongoDBCorpusClient()
        client._client = MagicMock()
        client._db = MagicMock()
        client.close()
        assert client._client is None
        assert client._db is None

    def test_close_when_not_connected(self):
        client = MongoDBCorpusClient()
        client.close()  # should not raise


class TestCollectionProperties:
    def test_documents_property(self):
        client = MongoDBCorpusClient()
        mock_db = MagicMock()
        client._db = mock_db
        _ = client.documents
        mock_db.__getitem__.assert_called_with("documents")

    def test_cards_property(self):
        client = MongoDBCorpusClient()
        mock_db = MagicMock()
        client._db = mock_db
        _ = client.cards
        mock_db.__getitem__.assert_called_with("cards")

    def test_metadata_property(self):
        client = MongoDBCorpusClient()
        mock_db = MagicMock()
        client._db = mock_db
        _ = client.metadata
        mock_db.__getitem__.assert_called_with("metadata")


class TestInsertDocument:
    def _make_connected_client(self):
        client = MongoDBCorpusClient()
        mock_db = MagicMock()
        client._db = mock_db
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        mock_result = MagicMock()
        mock_result.inserted_id = "abc123"
        mock_collection.insert_one.return_value = mock_result
        return client, mock_collection

    def test_insert_returns_id(self):
        client, mock_col = self._make_connected_client()
        doc_id = client.insert_document(
            source="test", title="Test Doc", text="Some text"
        )
        assert doc_id == "abc123"
        mock_col.insert_one.assert_called_once()

    def test_insert_doc_structure(self):
        client, mock_col = self._make_connected_client()
        client.insert_document(
            source="wikipedia", title="Article", text="Content here",
            url="http://example.com", author="Author"
        )
        call_args = mock_col.insert_one.call_args[0][0]
        assert call_args["source"] == "wikipedia"
        assert call_args["title"] == "Article"
        assert call_args["text"] == "Content here"
        assert "content_hash" in call_args
        assert "normalized_content_hash" in call_args
        assert call_args["metadata"]["url"] == "http://example.com"
        assert call_args["metadata"]["author"] == "Author"
        assert call_args["processing"]["normalized"] is False

    def test_insert_duplicate_raises(self):
        from hytools.integrations.database.mongodb_client import DuplicateKeyError
        client, mock_col = self._make_connected_client()
        mock_col.insert_one.side_effect = DuplicateKeyError("duplicate")
        with pytest.raises(DuplicateKeyError):
            client.insert_document(source="test", title="t", text="t")


class TestGetDocument:
    def test_get_existing(self):
        client = MongoDBCorpusClient()
        mock_db = MagicMock()
        client._db = mock_db
        mock_col = MagicMock()
        mock_db.__getitem__.return_value = mock_col
        mock_col.find_one.return_value = {"_id": "abc", "text": "hello"}

        with patch("hytools.integrations.database.mongodb_client.ObjectId", create=True) as mock_oid:
            # Patch bson import inside the method
            import hytools.integrations.database.mongodb_client as mod
            with patch.dict("sys.modules", {"bson": MagicMock()}):
                result = client.get_document("abc123")

    def test_get_nonexistent(self):
        client = MongoDBCorpusClient()
        mock_db = MagicMock()
        client._db = mock_db
        mock_col = MagicMock()
        mock_db.__getitem__.return_value = mock_col
        mock_col.find_one.return_value = None
        # Even if bson import fails, get_document returns None on error
        result = client.get_document("nonexistent")
        assert result is None


class TestFindDocuments:
    def _make_client(self):
        client = MongoDBCorpusClient()
        mock_db = MagicMock()
        client._db = mock_db
        mock_col = MagicMock()
        mock_db.__getitem__.return_value = mock_col
        mock_cursor = MagicMock()
        mock_cursor.limit.return_value = [{"_id": "1"}, {"_id": "2"}]
        mock_col.find.return_value = mock_cursor
        return client, mock_col

    def test_find_no_filters(self):
        client, mock_col = self._make_client()
        results = client.find_documents()
        mock_col.find.assert_called_once_with({})

    def test_find_with_source(self):
        client, mock_col = self._make_client()
        client.find_documents(source="wikipedia")
        call_args = mock_col.find.call_args[0][0]
        assert call_args["source"] == "wikipedia"

    def test_find_with_processed(self):
        client, mock_col = self._make_client()
        client.find_documents(processed=True)
        call_args = mock_col.find.call_args[0][0]
        assert call_args["processing.filtered"] is True


class TestCountDocuments:
    def test_count_all(self):
        client = MongoDBCorpusClient()
        mock_db = MagicMock()
        client._db = mock_db
        mock_col = MagicMock()
        mock_db.__getitem__.return_value = mock_col
        mock_col.count_documents.return_value = 42
        assert client.count_documents() == 42
        mock_col.count_documents.assert_called_once_with({})

    def test_count_by_source(self):
        client = MongoDBCorpusClient()
        mock_db = MagicMock()
        client._db = mock_db
        mock_col = MagicMock()
        mock_db.__getitem__.return_value = mock_col
        mock_col.count_documents.return_value = 10
        assert client.count_documents(source="wikipedia") == 10
        mock_col.count_documents.assert_called_once_with({"source": "wikipedia"})


class TestLogPipelineRun:
    def test_log_run(self):
        client = MongoDBCorpusClient()
        mock_db = MagicMock()
        client._db = mock_db
        mock_col = MagicMock()
        mock_db.__getitem__.return_value = mock_col
        client.log_pipeline_run("scraping", "ok", {"count": 5})
        mock_col.insert_one.assert_called_once()
        doc = mock_col.insert_one.call_args[0][0]
        assert doc["stage"] == "scraping"
        assert doc["status"] == "ok"
        assert doc["details"]["count"] == 5


class TestGetLatestRun:
    def test_get_latest(self):
        client = MongoDBCorpusClient()
        mock_db = MagicMock()
        client._db = mock_db
        mock_col = MagicMock()
        mock_db.__getitem__.return_value = mock_col
        mock_col.find_one.return_value = {"stage": "scraping", "status": "ok"}
        result = client.get_latest_run("scraping")
        assert result["stage"] == "scraping"

    def test_alias_exists(self):
        assert MongoDBCorpusClient.get_latest_metadata is MongoDBCorpusClient.get_latest_run


class TestUpsertCatalogItems:
    def test_upsert(self):
        client = MongoDBCorpusClient()
        mock_db = MagicMock()
        client._db = mock_db
        mock_col = MagicMock()
        mock_db.__getitem__.return_value = mock_col
        catalog = {"item1": {"title": "Book1"}, "item2": {"title": "Book2"}}
        count = client.upsert_catalog_items("loc", catalog)
        assert count == 2
        assert mock_col.update_one.call_count == 2


class TestMongoRetryDecorator:
    def test_retry_decorator_is_callable(self):
        assert callable(_mongo_retry)

    def test_decorated_function_works(self):
        @_mongo_retry
        def sample():
            return 42
        assert sample() == 42
