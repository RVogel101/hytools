#!/usr/bin/env python3
"""Materialize dialect-specific views from unified records (Batch 6, Option C Hybrid).

This tool creates canonical materialized views for Western Armenian, Eastern Armenian,
and Mixed dialect tags. This enables:
- WA-specific training datasets (direct to model)
- EA reference data (for comparison/contrast)
- Mixed dialect research datasets

Dialect mapping:
- western_armenian → wa_documents.jsonl
- eastern_armenian → ea_documents.jsonl
- mixed → mixed_documents.jsonl

Default input:
- unified: 08-data/unified_document_records.jsonl

Optional input:
- content-only: 08-data/unified_document_records_content_only.jsonl (if --content-only)

Outputs:
- WA: 08-data/materialized_wa_documents.jsonl
- EA: 08-data/materialized_ea_documents.jsonl
- MIXED: 08-data/materialized_mixed_documents.jsonl
- stats: 08-data/dialect_materialization_stats.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MaterializationStats:
    total_in: int = 0
    wa_out: int = 0
    ea_out: int = 0
    mixed_out: int = 0
    unknown_out: int = 0
    by_source_family: dict[str, int] = field(default_factory=dict)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize dialect-specific document views")
    parser.add_argument(
        "--unified-jsonl",
        type=Path,
        default=Path("08-data/unified_document_records.jsonl"),
        help="Unified DocumentRecord JSONL input",
    )
    parser.add_argument(
        "--content-only",
        action="store_true",
        help="Use content-only version if available",
    )
    parser.add_argument(
        "--wa-jsonl",
        type=Path,
        default=Path("08-data/materialized_wa_documents.jsonl"),
        help="Western Armenian materialized output",
    )
    parser.add_argument(
        "--ea-jsonl",
        type=Path,
        default=Path("08-data/materialized_ea_documents.jsonl"),
        help="Eastern Armenian materialized output",
    )
    parser.add_argument(
        "--mixed-jsonl",
        type=Path,
        default=Path("08-data/materialized_mixed_documents.jsonl"),
        help="Mixed dialect materialized output",
    )
    parser.add_argument(
        "--stats-json",
        type=Path,
        default=Path("08-data/dialect_materialization_stats.json"),
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


def _materialize_by_dialect(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], MaterializationStats]:
    """Partition records by dialect_tag."""
    stats = MaterializationStats()
    stats.total_in = len(rows)

    wa_records = []
    ea_records = []
    mixed_records = []
    unknown_records = []

    for record in rows:
        dialect_tag = record.get("dialect_tag", "unknown")
        source_family = record.get("source_family", "unknown")

        # Track source family distribution
        stats.by_source_family[source_family] = stats.by_source_family.get(source_family, 0) + 1

        if dialect_tag == "western_armenian":
            wa_records.append(record)
            stats.wa_out += 1
        elif dialect_tag == "eastern_armenian":
            ea_records.append(record)
            stats.ea_out += 1
        elif dialect_tag == "mixed":
            mixed_records.append(record)
            stats.mixed_out += 1
        else:
            unknown_records.append(record)
            stats.unknown_out += 1

    return wa_records, ea_records, mixed_records, unknown_records, stats


def main() -> int:
    args = parse_args()

    # Determine input file
    input_path = args.unified_jsonl
    if args.content_only:
        content_only_path = Path("08-data/unified_document_records_content_only.jsonl")
        if content_only_path.exists():
            input_path = content_only_path
            print(f"Using content-only variant: {content_only_path}")

    if not input_path.exists():
        print(f"Input JSONL not found: {input_path}")
        return 1

    unified_rows = _load_jsonl(input_path)
    wa_rows, ea_rows, mixed_rows, unknown_rows, stats = _materialize_by_dialect(unified_rows)

    # Write Western Armenian
    args.wa_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.wa_jsonl.open("w", encoding="utf-8") as f:
        for row in wa_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Write Eastern Armenian
    args.ea_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.ea_jsonl.open("w", encoding="utf-8") as f:
        for row in ea_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Write Mixed
    args.mixed_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.mixed_jsonl.open("w", encoding="utf-8") as f:
        for row in mixed_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Write stats
    stats_payload = {
        "total_in": stats.total_in,
        "wa_out": stats.wa_out,
        "ea_out": stats.ea_out,
        "mixed_out": stats.mixed_out,
        "unknown_out": stats.unknown_out,
        "wa_pct": (stats.wa_out / stats.total_in * 100) if stats.total_in else 0,
        "ea_pct": (stats.ea_out / stats.total_in * 100) if stats.total_in else 0,
        "mixed_pct": (stats.mixed_out / stats.total_in * 100) if stats.total_in else 0,
        "by_source_family": stats.by_source_family,
        "wa_jsonl": str(args.wa_jsonl),
        "ea_jsonl": str(args.ea_jsonl),
        "mixed_jsonl": str(args.mixed_jsonl),
    }

    args.stats_json.write_text(json.dumps(stats_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Dialect materialization complete")
    print(f"  total_in: {stats.total_in}")
    print(f"  wa_out: {stats.wa_out} ({stats_payload['wa_pct']:.1f}%)")
    print(f"  ea_out: {stats.ea_out} ({stats_payload['ea_pct']:.1f}%)")
    print(f"  mixed_out: {stats.mixed_out} ({stats_payload['mixed_pct']:.1f}%)")
    if stats.unknown_out:
        print(f"  unknown_out: {stats.unknown_out}")
    print(f"  wa_jsonl: {args.wa_jsonl}")
    print(f"  ea_jsonl: {args.ea_jsonl}")
    print(f"  mixed_jsonl: {args.mixed_jsonl}")
    print(f"  stats_json: {args.stats_json}")

    return 0


if __name__ == "__main__":
    exit(main())
