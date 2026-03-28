import io
import json
import zipfile

import pytest

from hytools.ingestion.acquisition.nayiri import (
    import_lexicon_from_url,
    import_corpus_from_url,
    parse_lexicon_data,
    parse_corpus_member,
)


class FakeCollection:
    def __init__(self):
        self.docs = {}

    def update_one(self, filter, update, upsert=False):
        entry_id = filter.get("entry_id")
        doc = (update or {}).get("$set") or {}
        class Res:
            upserted_id = None
        if entry_id not in self.docs:
            self.docs[entry_id] = doc
            r = Res()
            r.upserted_id = True
            return r
        else:
            self.docs[entry_id].update(doc)
            r = Res()
            r.upserted_id = None
            return r


class FakeDB:
    def __init__(self):
        self._cols = {}

    def get_collection(self, name):
        if name not in self._cols:
            self._cols[name] = FakeCollection()
        return self._cols[name]


class FakeClient:
    def __init__(self):
        self.db = FakeDB()
        self.inserted = []

    def insert_document(self, source, title, text, author=None, metadata=None, url=None):
        self.inserted.append({
            "source": source,
            "title": title,
            "text": text,
            "author": author,
            "metadata": metadata,
        })
        return "fake_id"


def make_zip_bytes(json_filename=None, json_obj=None, files=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        if json_filename and json_obj is not None:
            zf.writestr(json_filename, json.dumps(json_obj, ensure_ascii=False))
        if files:
            for name, content in files.items():
                zf.writestr(name, content)
    buf.seek(0)
    return buf.getvalue()


class DummyResp:
    def __init__(self, data: bytes):
        self._data = data

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=8192):
        yield self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_parse_lexicon_data_parses_lexemes():
    # Create a minimal Nayiri lexicon structure
    data = {
        "metadata": {"version": "1.0", "license": "CC-BY-4.0"},
        "inflections": [{"inflectionId": "inf1", "form": "-s"}],
        "lexemes": [
            {
                "lexemeId": "lx1",
                "lemmas": [
                    {
                        "lemmaId": "lm1",
                        "lemmaString": "շատ",
                        "partOfSpeech": "noun",
                        "wordForms": [{"s": "շատ", "i": "inf1"}],
                        "definitions": "many",
                    }
                ],
            }
        ],
    }

    client = FakeClient()

    inserted = parse_lexicon_data(data, client)

    coll = client.db.get_collection("nayiri_entries")
    # Expect one upserted entry
    assert inserted == 1
    # Verify headword stored
    assert any(doc.get("headword") == "շատ" for doc in coll.docs.values())


def test_parse_corpus_member_parses_datastore():
    authors_map = {"a1": "Author A"}
    pubs_map = {"p1": "Publication P1"}
    raw = "author=a1\npublication=p1\nBEGIN_DOCUMENT_CONTENT\n[[token]] sample content"

    client = FakeClient()

    ok = parse_corpus_member("data-store/doc1.txt", raw, authors_map, pubs_map, client)
    assert ok is True
    assert len(client.inserted) == 1
    doc = client.inserted[0]
    assert doc["title"] == "doc1.txt"
    assert isinstance(doc["text"], str) and "sample content" in doc["text"]
    assert doc["metadata"] and "nayiri" in doc["metadata"]
