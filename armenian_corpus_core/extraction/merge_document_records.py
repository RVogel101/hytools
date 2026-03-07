#!/usr/bin/env python3
"""Merge canonical DocumentRecord JSONL files and deduplicate.

Default inputs:
- local: 08-data/export_document_records.jsonl
- WA fingerprints: 08-data/wa_fingerprint_document_records.jsonl

Dedup strategy:
1) Primary key: content_hash (if present)
2) Fallback key: document_id

Preference rule on conflicts:
- Prefer records with non-empty text
- Then prefer longer text length
- Then prefer richer metadata (more keys)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class MergeStats:
    local_in: int = 0
    wa_in: int = 0
    total_in: int = 0
    dedup_by_hash_hits: int = 0
    dedup_by_id_hits: int = 0
    replaced_preferred: int = 0
    kept_existing: int = 0
    missing_hash_count: int = 0
    unified_out: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge and deduplicate DocumentRecord JSONL files")
    parser.add_argument(
        "--local-jsonl",
        type=Path,
        default=Path("08-data/export_document_records.jsonl"),
        help="Local DocumentRecord JSONL",
    )
    parser.add_argument(
        "--wa-jsonl",
        type=Path,
        default=Path("08-data/wa_fingerprint_document_records.jsonl"),
        help="WA fingerprint-derived DocumentRecord JSONL",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=Path("08-data/unified_document_records.jsonl"),
        help="Unified deduplicated output JSONL",
    )
    parser.add_argument(
        "--stats-json",
        type=Path,
        default=Path("08-data/unified_document_records_stats.json"),
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


def _record_quality_score(record: dict[str, Any]) -> tuple[int, int, int]:
    """Higher is better for replacement decisions.

    tuple fields:
    1. has_non_empty_text
    2. text_len
    3. metadata_key_count
    """

    text = record.get("text")
    text_s = text.strip() if isinstance(text, str) else ""
    has_text = 1 if text_s else 0
    text_len = len(text_s)
    metadata = record.get("metadata")
    metadata_count = len(metadata.keys()) if isinstance(metadata, dict) else 0
    return (has_text, text_len, metadata_count)


def _merge_records(local_rows: list[dict[str, Any]], wa_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], MergeStats]:
    stats = MergeStats()
    stats.local_in = len(local_rows)
    stats.wa_in = len(wa_rows)
    stats.total_in = stats.local_in + stats.wa_in

    by_hash: dict[str, dict[str, Any]] = {}
    by_id: dict[str, dict[str, Any]] = {}

    def upsert_record(record: dict[str, Any], source_tag: str) -> None:
        nonlocal stats
        record.setdefault("metadata", {})
        if isinstance(record.get("metadata"), dict):
            record["metadata"].setdefault("merge_source", source_tag)

        content_hash = record.get("content_hash")
        document_id = str(record.get("document_id", "")).strip()

        if not content_hash:
            stats.missing_hash_count += 1

        if content_hash:
            key = str(content_hash)
            existing = by_hash.get(key)
            if existing is None:
                by_hash[key] = record
                if document_id:
                    by_id[document_id] = by_hash[key]
                return

            stats.dedup_by_hash_hits += 1
            if _record_quality_score(record) > _record_quality_score(existing):
                stats.replaced_preferred += 1
                by_hash[key] = record
                if document_id:
                    by_id[document_id] = by_hash[key]
            else:
                stats.kept_existing += 1
            return

        # No hash: fallback dedup by document_id.
        if document_id:
            existing = by_id.get(document_id)
            if existing is None:
                by_id[document_id] = record
                return

            stats.dedup_by_id_hits += 1
            if _record_quality_score(record) > _record_quality_score(existing):
                stats.replaced_preferred += 1
                by_id[document_id] = record
            else:
                stats.kept_existing += 1
            return

        # Worst case: no hash and no document id; keep as synthetic unique ID.
        synthetic_id = f"_synthetic_{id(record)}"
        by_id[synthetic_id] = record

    for row in local_rows:
        upsert_record(row, "lousardzag_local")
    for row in wa_rows:
        upsert_record(row, "westernarmenianllm_fingerprint")

    # Union values from both maps (same object may be present in both maps).
    unified = {id(v): v for v in list(by_hash.values()) + list(by_id.values())}
    rows = list(unified.values())
    rows.sort(key=lambda r: (str(r.get("source_family", "")), str(r.get("document_id", ""))))

    stats.unified_out = len(rows)
    return rows, stats


def main() -> int:
    args = parse_args()

    if not args.local_jsonl.exists():
        print(f"Local JSONL not found: {args.local_jsonl}")
        return 1
    if not args.wa_jsonl.exists():
        print(f"WA JSONL not found: {args.wa_jsonl}")
        return 1

    local_rows = _load_jsonl(args.local_jsonl)
    wa_rows = _load_jsonl(args.wa_jsonl)

    unified_rows, stats = _merge_records(local_rows, wa_rows)

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as f:
        for row in unified_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    stats_payload = {
        "local_in": stats.local_in,
        "wa_in": stats.wa_in,
        "total_in": stats.total_in,
        "dedup_by_hash_hits": stats.dedup_by_hash_hits,
        "dedup_by_id_hits": stats.dedup_by_id_hits,
        "replaced_preferred": stats.replaced_preferred,
        "kept_existing": stats.kept_existing,
        "missing_hash_count": stats.missing_hash_count,
        "unified_out": stats.unified_out,
        "output_jsonl": str(args.output_jsonl),
    }

    args.stats_json.write_text(json.dumps(stats_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Unified document merge complete")
    print(f"  local_in: {stats.local_in}")
    print(f"  wa_in: {stats.wa_in}")
    print(f"  total_in: {stats.total_in}")
    print(f"  dedup_by_hash_hits: {stats.dedup_by_hash_hits}")
    print(f"  dedup_by_id_hits: {stats.dedup_by_id_hits}")
    print(f"  replaced_preferred: {stats.replaced_preferred}")
    print(f"  kept_existing: {stats.kept_existing}")
    print(f"  unified_out: {stats.unified_out}")
    print(f"  output_jsonl: {args.output_jsonl}")
    print(f"  stats_json: {args.stats_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
