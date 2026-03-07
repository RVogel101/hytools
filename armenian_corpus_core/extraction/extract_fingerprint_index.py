#!/usr/bin/env python3
"""Extract fingerprint-only records into a separate index (Batch 6, Option B).

This tool separates fingerprint-only records (empty text) from content-bearing
records in the unified document set. This enables:
- Content-aware training pipelines (skip fingerprints)
- Fingerprint metadata queries (separate index)
- Clear separation for mixed-mode applications

Default inputs:
- unified: 08-data/unified_document_records.jsonl

Outputs:
- content-only: 08-data/unified_document_records_content_only.jsonl
- fingerprint-only: 08-data/unified_document_records_fingerprint_index.jsonl
- stats: 08-data/fingerprint_extraction_stats.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ExtractionStats:
    total_in: int = 0
    content_only_out: int = 0
    fingerprint_only_out: int = 0
    uncategorized_out: int = 0  # empty text but some metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract fingerprint-only records into separate index")
    parser.add_argument(
        "--unified-jsonl",
        type=Path,
        default=Path("08-data/unified_document_records.jsonl"),
        help="Unified DocumentRecord JSONL input",
    )
    parser.add_argument(
        "--content-only-jsonl",
        type=Path,
        default=Path("08-data/unified_document_records_content_only.jsonl"),
        help="Content-bearing records output",
    )
    parser.add_argument(
        "--fingerprint-index-jsonl",
        type=Path,
        default=Path("08-data/unified_document_records_fingerprint_index.jsonl"),
        help="Fingerprint-only records (metadata index)",
    )
    parser.add_argument(
        "--stats-json",
        type=Path,
        default=Path("08-data/fingerprint_extraction_stats.json"),
        help="Stats output JSON",
    )
    return parser.parse_args()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _is_content_bearing(record: dict[str, Any]) -> bool:
    """Check if record has non-empty text content."""
    text = record.get("text")
    if isinstance(text, str):
        return bool(text.strip())
    return False


def _extract_records(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], ExtractionStats]:
    """Separate content-bearing from fingerprint-only records."""
    stats = ExtractionStats()
    stats.total_in = len(rows)

    content_only = []
    fingerprint_only = []

    for record in rows:
        if _is_content_bearing(record):
            content_only.append(record)
            stats.content_only_out += 1
        else:
            fingerprint_only.append(record)
            stats.fingerprint_only_out += 1

    return content_only, fingerprint_only, stats


def main() -> int:
    args = parse_args()

    if not args.unified_jsonl.exists():
        print(f"Unified JSONL not found: {args.unified_jsonl}")
        return 1

    unified_rows = _load_jsonl(args.unified_jsonl)
    content_rows, fingerprint_rows, stats = _extract_records(unified_rows)

    # Write content-only
    args.content_only_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.content_only_jsonl.open("w", encoding="utf-8") as f:
        for row in content_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Write fingerprint index
    args.fingerprint_index_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.fingerprint_index_jsonl.open("w", encoding="utf-8") as f:
        for row in fingerprint_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Write stats
    stats_payload = {
        "total_in": stats.total_in,
        "content_only_out": stats.content_only_out,
        "fingerprint_only_out": stats.fingerprint_only_out,
        "content_only_pct": (stats.content_only_out / stats.total_in * 100) if stats.total_in else 0,
        "fingerprint_only_pct": (stats.fingerprint_only_out / stats.total_in * 100) if stats.total_in else 0,
        "content_only_jsonl": str(args.content_only_jsonl),
        "fingerprint_index_jsonl": str(args.fingerprint_index_jsonl),
    }

    args.stats_json.write_text(json.dumps(stats_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Fingerprint index extraction complete")
    print(f"  total_in: {stats.total_in}")
    print(f"  content_only_out: {stats.content_only_out} ({stats_payload['content_only_pct']:.1f}%)")
    print(f"  fingerprint_only_out: {stats.fingerprint_only_out} ({stats_payload['fingerprint_only_pct']:.1f}%)")
    print(f"  content_only_jsonl: {args.content_only_jsonl}")
    print(f"  fingerprint_index_jsonl: {args.fingerprint_index_jsonl}")
    print(f"  stats_json: {args.stats_json}")

    return 0


if __name__ == "__main__":
    exit(main())
