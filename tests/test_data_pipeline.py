import pytest

from hytools.cleaning import pipeline


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    def delete_many(self, _):
        self.docs = []

    def find(self, query=None):
        query = query or {}
        if not query:
            return list(self.docs)
        if "$ne" in query.get("metadata.internal_language_tag", {}):
            return [d for d in self.docs if d.get("metadata", {}).get("internal_language_tag") != query["metadata.internal_language_tag"]["$ne"]]
        return [d for d in self.docs if d.get("metadata", {}).get("internal_language_tag") == query.get("metadata.internal_language_tag")]

    def insert_one(self, doc):
        self.docs.append(doc)

    def update_one(self, filter_q, update):
        for d in self.docs:
            if d.get("_id") == filter_q.get("_id"):
                if "$set" in update:
                    for key, value in update["$set"].items():
                        if "." in key:
                            fields = key.split(".")
                            tgt = d
                            for f in fields[:-1]:
                                tgt = tgt.setdefault(f, {})
                            tgt[fields[-1]] = value
                        else:
                            d[key] = value
                return

    def count_documents(self, query):
        if "$ne" in query.get("metadata.internal_language_tag", {}):
            return sum(1 for d in self.docs if d.get("metadata", {}).get("internal_language_tag") != query["metadata.internal_language_tag"]["$ne"])
        return sum(1 for d in self.docs if d.get("metadata", {}).get("internal_language_tag") == query.get("metadata.internal_language_tag"))

    def sort(self, fields=None, *args, **kwargs):
        if fields is None:
            return self.docs
        docs = list(self.docs)
        for field, direction in reversed(fields):
            if field == "metadata.normalized_content_hash":
                docs.sort(key=lambda d: d.get("metadata", {}).get("normalized_content_hash", ""))
            elif field == "_id":
                docs.sort(key=lambda d: d.get("_id", 0))
        return docs


class FakeClient:
    def __init__(self, docs):
        self._db = {
            "documents": FakeCollection(docs),
            "documents_cleaned": FakeCollection([]),
        }

    @property
    def db(self):
        return self

    def __getitem__(self, item):
        return self._db[item]


def _fake_open_factory(fake_client):
    class Ctx:
        def __enter__(self_):
            return fake_client

        def __exit__(self_, exc_type, exc_val, exc_tb):
            pass

    return lambda config: Ctx()


def test_extract_from_mongo_strict_filter(monkeypatch):
    docs = [
        {
            "_id": 1,
            "source": "test",
            "title": "doc1",
            "text": "մը եկել էր",
            "metadata": {"internal_language_tag": "hye-w"},
            "processing": {},
        },
        {
            "_id": 2,
            "source": "test",
            "title": "doc2",
            "text": "միայի անց",
            "metadata": {"internal_language_tag": "hye-e"},
            "processing": {},
        },
    ]
    fake_client = FakeClient(docs)
    monkeypatch.setattr(pipeline, "open_mongodb_client", _fake_open_factory(fake_client))

    summary = pipeline.extract_from_mongo(config={})
    assert summary["imported"] == 1
    assert summary["filter_query"] == {"metadata.internal_language_tag": "hye-w"}


def test_apply_language_tagging_and_non_hye_w_count(monkeypatch):
    docs = [
        {
            "_id": 1,
            "source": "test",
            "title": "doc1",
            "text": "մը եկել էր",
            "metadata": {"internal_language_tag": "hye-w"},
            "processing": {},
        },
    ]
    fake_client = FakeClient(docs)
    monkeypatch.setattr(pipeline, "open_mongodb_client", _fake_open_factory(fake_client))

    pipeline.extract_from_mongo(config={})
    result = pipeline.apply_language_tagging(config={})
    assert result["updated"] == 1
    assert "not_hye_w" in result


def test_dedupe_behavior(monkeypatch):
    docs = [
        {
            "_id": 3,
            "source": "test",
            "title": "doc3",
            "text": "մը եկել էր",
            "metadata": {"internal_language_tag": "hye-w"},
            "processing": {},
        },
        {
            "_id": 4,
            "source": "test",
            "title": "doc4",
            "text": "մը եկել էր",
            "metadata": {"internal_language_tag": "hye-w"},
            "processing": {},
        },
    ]
    fake_client = FakeClient(docs)
    monkeypatch.setattr(pipeline, "open_mongodb_client", _fake_open_factory(fake_client))

    pipeline.extract_from_mongo(config={})
    pipeline.apply_language_tagging(config={})
    pipeline.apply_text_cleaning(config={})
    stats = pipeline.dedupe_documents(config={})
    assert stats["duplicates"] >= 1
