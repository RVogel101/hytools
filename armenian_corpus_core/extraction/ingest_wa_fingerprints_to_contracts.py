#!/usr/bin/env python3
"""Convert WesternArmenianLLM fingerprint CSV into DocumentRecord JSONL."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from armenian_corpus_core.extraction.mappers import wa_fingerprint_row_to_document_record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest WA fingerprint CSV and export canonical DocumentRecord JSONL"
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path(r"C:\Users\litni\WesternArmenianLLM\migration_exports\corpus_fingerprints.csv"),
        help="Path to WesternArmenianLLM corpus_fingerprints.csv",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=Path("08-data/wa_fingerprint_document_records.jsonl"),
        help="Output JSONL path for canonical DocumentRecord rows",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional row limit (0 = all rows)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.input_csv.exists():
        print(f"Input CSV not found: {args.input_csv}")
        return 1

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    exported = 0
    skipped = 0

    with args.input_csv.open("r", encoding="utf-8") as in_f, args.output_jsonl.open("w", encoding="utf-8") as out_f:
        reader = csv.DictReader(in_f)
        for i, row in enumerate(reader):
            if args.limit > 0 and i >= args.limit:
                break

            # Skip explicit truncation marker row from source exporter.
            marker = (row.get("source") or "").strip()
            if marker == "__TRUNCATION_NOTICE__":
                skipped += 1
                continue

            record = wa_fingerprint_row_to_document_record(row)
            out_f.write(json.dumps(record.__dict__, ensure_ascii=False) + "\n")
            exported += 1

    print(f"Exported WA fingerprint DocumentRecord rows: {exported}")
    if skipped:
        print(f"Skipped marker rows: {skipped}")
    print(f"Output: {args.output_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
