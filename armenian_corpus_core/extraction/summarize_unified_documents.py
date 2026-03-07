#!/usr/bin/env python3
"""Summarize unified DocumentRecord JSONL by source and dialect."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize unified DocumentRecord JSONL")
    parser.add_argument(
        "--input-jsonl",
        type=Path,
        default=Path("08-data/unified_document_records.jsonl"),
        help="Path to unified document records JSONL",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("08-data/unified_document_records_summary.json"),
        help="Summary JSON output path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input_jsonl.exists():
        print(f"Input file not found: {args.input_jsonl}")
        return 1

    source_counter: Counter[str] = Counter()
    dialect_counter: Counter[str] = Counter()
    empty_text = 0
    with_hash = 0
    total = 0

    with args.input_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            row: dict[str, Any] = json.loads(line)
            source_counter[str(row.get("source_family", "unknown"))] += 1
            dialect_counter[str(row.get("dialect_tag", "unknown"))] += 1
            if row.get("content_hash"):
                with_hash += 1
            text = row.get("text")
            if not isinstance(text, str) or not text.strip():
                empty_text += 1

    payload = {
        "total_records": total,
        "with_content_hash": with_hash,
        "without_content_hash": total - with_hash,
        "empty_text_records": empty_text,
        "non_empty_text_records": total - empty_text,
        "by_source_family": dict(source_counter.most_common()),
        "by_dialect_tag": dict(dialect_counter.most_common()),
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Summary written: {args.output_json}")
    print(f"total_records={total}")
    print(f"empty_text_records={empty_text}")
    print(f"sources={len(source_counter)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
