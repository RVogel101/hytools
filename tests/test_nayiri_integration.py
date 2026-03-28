import io
import json
import zipfile
from pathlib import Path

import pytest

from hytools.ingestion.acquisition import nayiri


class DummyResponse:
    def __init__(self, data: bytes):
        self._data = data

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=8192):
        for i in range(0, len(self._data), chunk_size):
            yield self._data[i : i + chunk_size]

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FakeCollection:
    def __init__(self):
        self.data = {}

    def update_one(self, filter_query, update_doc, upsert=False):
        key = filter_query.get("entry_id")
        exists = key in self.data
        self.data[key] = update_doc["$set"]

        class Result:
            pass

        res = Result()
        res.upserted_id = None if exists else 1
        return res


class FakeDb:
    def __init__(self):
        self.collections = {}

    def get_collection(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]


class FakeClient:
    def __init__(self):
        self.db = FakeDb()
        self.inserted_documents = []

    def insert_document(self, **kw):
        self.inserted_documents.append(kw)
        # emulate 1 document inserted; in reality, the pipeline uses Mongo API
        return True


@pytest.fixture(autouse=True)
def patch_requests(monkeypatch):
    def fake_get(url, stream=True, timeout=30):
        preds = url.endswith("nayiri-armenian-lexicon-2026-02-15-v1.json.zip")
        if preds:
            lexicon = {
                "lexemes": [
                    {
                        "lexemeId": "1",
                        "description": "բառ (word)",
                        "lemmaType": "NOMINAL",
                        "lemmas": [
                            {
                                "lemmaId": "100",
                                "lemmaString": "բառ",
                                "partOfSpeech": "noun",
                                "lemmaDisplayString": "բառ (word)",
                                "numWordForms": 1,
                                "wordForms": [{"s": "բառ"}],
                                "definitions": "word",
                            }
                        ],
                    }
                ],
                "metadata": {"source": "nayiri"},
            }
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("nayiri_lexicon.json", json.dumps(lexicon, ensure_ascii=False))
            buf.seek(0)
            return DummyResponse(buf.read())

        if url.endswith("nayiri-corpus-of-western-armenian-2026-02-25-v2.zip"):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("authors.properties", "auth1={\"name\":\"Author Name\"}")
                zf.writestr("publications.properties", "pub1={\"name\":\"Publication Name\"}")
                content = "id=JXPzhQ\nauthor=auth1\npublication=pub1\nwrittenLanguageVariant=WA\nBEGIN_DOCUMENT_CONTENT\nSample text"
                zf.writestr("data-store/example.txt", content)
            buf.seek(0)
            return DummyResponse(buf.read())

        raise ValueError(f"Unexpected URL: {url}")

    monkeypatch.setattr(nayiri.requests, "get", fake_get)
    yield


def test_import_lexicon_from_url(tmp_path):
    client = FakeClient()
    config = {
        "cache_dir": str(tmp_path),
        "scraping": {"nayiri": {"lexicon_url": "https://example.com/nayiri-armenian-lexicon-2026-02-15-v1.json.zip"}},
    }
    inserted = nayiri.import_lexicon_from_url(config, client)
    assert inserted == 1
    entry = client.db.get_collection("nayiri_entries").data.get("nayiri:1:100")
    assert entry is not None
    assert entry["headword"] == "բառ"
    assert entry["lexeme_description"] == "բառ (word)"
    assert entry["lemma_display_string"] == "բառ (word)"
    assert entry["lemma_num_word_forms"] == 1


def test_import_corpus_from_url(tmp_path):
    client = FakeClient()
    config = {
        "cache_dir": str(tmp_path),
        "scraping": {"nayiri": {"corpus_url": "https://example.com/nayiri-corpus-of-western-armenian-2026-02-25-v2.zip"}},
    }
    inserted = nayiri.import_corpus_from_url(config, client)
    assert inserted == 1
    assert len(client.inserted_documents) == 1
    doc = client.inserted_documents[0]
    assert doc["source"] == "nayiri_wa_corpus"
    assert doc["metadata"]["nayiri"]["id"] == "JXPzhQ"
    assert doc["metadata"]["nayiri"]["writtenlanguagevariant"] == "WA"
    assert doc["author"] == {"name": "Author Name"}
    assert doc["metadata"]["publication"]["name"] == "Publication Name"

