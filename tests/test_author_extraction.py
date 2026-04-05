from __future__ import annotations

import json
from pathlib import Path

from hytools.ingestion.discovery.author_extraction import AuthorExtractor, ExtractedAuthor, extract_authors_from_corpus


def test_extract_from_corpus_metadata_skips_malformed_jsonl_lines(tmp_path: Path):
    metadata_path = tmp_path / "authors.jsonl"
    metadata_path.write_text(
        "\n".join(
            [
                json.dumps({"author": "Author One", "title": "Doc 1"}, ensure_ascii=False),
                "{bad json",
                json.dumps({"creator": {"name": "Author Two"}, "title": "Doc 2"}, ensure_ascii=False),
            ]
        ),
        encoding="utf-8",
    )

    extractor = AuthorExtractor()
    extracted = extractor.extract_from_corpus_metadata(metadata_path)

    assert [author.name for author in extracted] == ["Author One", "Author Two"]


def test_extract_from_text_patterns_handles_match_group_access_safely():
    extractor = AuthorExtractor()

    extracted = extractor.extract_from_text_patterns("Հեղինակ՝ Արամ Հայկ", source_name="sample.txt")

    assert extracted
    assert extracted[0].name == "Արամ Հայկ"


def test_extract_from_text_patterns_rejects_common_ocr_false_positive():
    extractor = AuthorExtractor()

    extracted = extractor.extract_from_text_patterns("Յ. Շատ եկաւ տուն", source_name="sample.txt")

    assert extracted == []


def test_extract_from_text_patterns_keeps_initial_surname_when_explicitly_labeled():
    extractor = AuthorExtractor()

    extracted = extractor.extract_from_text_patterns("Գրած՝ Օ. Թունեան", source_name="sample.txt")

    assert [author.name for author in extracted] == ["Օ. Թունեան"]


def test_extract_authors_from_corpus_uses_default_inventory_path_even_without_jsonl(monkeypatch, tmp_path: Path):
    calls: list[str] = []

    class DummyInventoryManager:
        def __init__(self, inventory_file: str):
            calls.append(inventory_file)
            self.books = []

    def fake_extract_from_book_inventory(self, inventory_manager):
        return [ExtractedAuthor(name="Օ. Թունեան", source="book_inventory:test", confidence=0.95, context="ctx")]

    monkeypatch.setattr(
        "hytools.ingestion.discovery.author_extraction.BookInventoryManager",
        DummyInventoryManager,
    )
    monkeypatch.setattr(AuthorExtractor, "extract_from_book_inventory", fake_extract_from_book_inventory)

    extracted = extract_authors_from_corpus(
        corpus_dir=tmp_path,
        inventory_file=tmp_path / "book_inventory.jsonl",
        metadata_patterns=[],
        exclude_dirs=[],
    )

    assert calls
    assert [author.name for author in extracted] == ["Օ. Թունեան"]


def test_extract_from_corpus_metadata_rejects_mixed_script_corruption(tmp_path: Path):
    metadata_path = tmp_path / "authors.jsonl"
    metadata_path.write_text(
        json.dumps({"author": "Ե. Մէ询առնց", "title": "Doc 1"}, ensure_ascii=False),
        encoding="utf-8",
    )

    extractor = AuthorExtractor()
    extracted = extractor.extract_from_corpus_metadata(metadata_path)

    assert extracted == []