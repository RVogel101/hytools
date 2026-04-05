from __future__ import annotations

from hytools.ingestion.discovery.book_inventory import _is_default_inventory_path


def test_default_inventory_path_matches_windows_and_posix_forms():
    assert _is_default_inventory_path("data/book_inventory.jsonl") is True
    assert _is_default_inventory_path("data\\book_inventory.jsonl") is True
    assert _is_default_inventory_path("tmp/book_inventory.jsonl") is False