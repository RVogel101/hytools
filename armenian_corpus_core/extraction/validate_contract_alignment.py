#!/usr/bin/env python3
"""Validate lousardzag contract exports against WesternArmenianLLM migration artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ValidationResult:
    name: str
    passed: bool
    detail: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate cross-project contract alignment")
    parser.add_argument(
        "--lexicon-jsonl",
        type=Path,
        default=Path("08-data/export_lexicon_entries.jsonl"),
        help="Path to LexiconEntry JSONL exported from lousardzag",
    )
    parser.add_argument(
        "--documents-jsonl",
        type=Path,
        default=Path("08-data/export_document_records.jsonl"),
        help="Path to DocumentRecord JSONL exported from lousardzag",
    )
    parser.add_argument(
        "--wa-exports-dir",
        type=Path,
        default=Path(r"C:\Users\litni\WesternArmenianLLM\migration_exports"),
        help="Path to WesternArmenianLLM migration_exports directory",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("08-data/contract_alignment_report.json"),
        help="Validation report JSON output path",
    )
    parser.add_argument(
        "--jsonl-max-rows",
        type=int,
        default=0,
        help="Max rows to sample from local JSONL exports (0 = all rows)",
    )
    parser.add_argument(
        "--fingerprint-limit",
        type=int,
        default=0,
        help="Max rows to sample from WA fingerprint CSV (0 = all rows)",
    )
    return parser.parse_args()


def _load_jsonl(path: Path, max_rows: int = 0) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if max_rows > 0 and i >= max_rows:
                break
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _load_sqlite_schema(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_fingerprints(path: Path, limit: int = 0) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if limit > 0 and i >= limit:
                break
            rows.append(row)
    return rows


def validate(args: argparse.Namespace) -> dict[str, Any]:
    results: list[ValidationResult] = []

    required_wa_files = [
        args.wa_exports_dir / "sqlite_schema.json",
        args.wa_exports_dir / "corpus_fingerprints.csv",
        args.wa_exports_dir / "phonetics_test_results.json",
    ]
    missing = [str(p) for p in required_wa_files if not p.exists()]
    results.append(
        ValidationResult(
            "wa_exports_available",
            len(missing) == 0,
            "all required WA export files found" if not missing else f"missing: {missing}",
        )
    )

    if not args.lexicon_jsonl.exists() or not args.documents_jsonl.exists():
        results.append(
            ValidationResult(
                "lousardzag_exports_available",
                False,
                "missing exported JSONL files; run export_core_contracts_jsonl.py first",
            )
        )
        return _to_report(results, {})

    lexicon = _load_jsonl(args.lexicon_jsonl, max_rows=args.jsonl_max_rows)
    documents = _load_jsonl(args.documents_jsonl, max_rows=args.jsonl_max_rows)

    results.append(
        ValidationResult(
            "lousardzag_exports_non_empty",
            len(lexicon) > 0 and len(documents) > 0,
            f"lexicon_rows={len(lexicon)}, document_rows={len(documents)}",
        )
    )

    lexicon_required = {"lemma", "dialect_tag", "metadata"}
    doc_required = {"document_id", "source_family", "text", "dialect_tag", "content_hash"}

    missing_lex = sorted(lexicon_required - set(lexicon[0].keys())) if lexicon else sorted(lexicon_required)
    missing_doc = sorted(doc_required - set(documents[0].keys())) if documents else sorted(doc_required)

    results.append(
        ValidationResult(
            "lexicon_required_fields",
            not missing_lex,
            "ok" if not missing_lex else f"missing fields: {missing_lex}",
        )
    )
    results.append(
        ValidationResult(
            "document_required_fields",
            not missing_doc,
            "ok" if not missing_doc else f"missing fields: {missing_doc}",
        )
    )

    allowed_dialects = {"western_armenian", "eastern_armenian", "mixed", "unknown"}
    lex_dialects = {str(r.get("dialect_tag", "")) for r in lexicon[:500]}
    doc_dialects = {str(r.get("dialect_tag", "")) for r in documents[:500]}
    bad_dialects = sorted((lex_dialects | doc_dialects) - allowed_dialects)

    results.append(
        ValidationResult(
            "dialect_tag_values",
            not bad_dialects,
            "ok" if not bad_dialects else f"unexpected dialect tags: {bad_dialects}",
        )
    )

    extra: dict[str, Any] = {}

    sqlite_schema_path = args.wa_exports_dir / "sqlite_schema.json"
    if sqlite_schema_path.exists():
        schema = _load_sqlite_schema(sqlite_schema_path)
        dbs = schema.get("databases", [])
        table_names: set[str] = set()
        for db in dbs:
            for t in db.get("tables", []):
                name = t.get("name")
                if isinstance(name, str):
                    table_names.add(name)
        expected_source_tables = {
            "wikipedia_articles",
            "newspaper_articles",
            "archive_org_texts",
            "wikisource_texts",
            "loc_texts",
            "hathitrust_texts",
            "nayiri_entries",
        }
        found = sorted(expected_source_tables & table_names)
        missing_tables = sorted(expected_source_tables - table_names)
        results.append(
            ValidationResult(
                "wa_source_tables_detected",
                len(found) >= 4,
                f"found={found}; missing={missing_tables}",
            )
        )
        extra["wa_detected_source_tables"] = found

    fingerprints_path = args.wa_exports_dir / "corpus_fingerprints.csv"
    if fingerprints_path.exists():
        fp_rows = _load_fingerprints(fingerprints_path, limit=args.fingerprint_limit)
        has_expected_cols = bool(fp_rows) and all(
            key in fp_rows[0]
            for key in ["source", "id/path", "title", "sha256(text_normalized)", "char_count", "dialect_tag"]
        )
        results.append(
            ValidationResult(
                "wa_fingerprint_columns",
                has_expected_cols,
                "ok" if has_expected_cols else "fingerprint CSV columns mismatch",
            )
        )
        extra["wa_fingerprint_sample_rows"] = len(fp_rows)

    summary = {
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "total": len(results),
    }

    return _to_report(results, {"summary": summary, **extra})


def _to_report(results: list[ValidationResult], extra: dict[str, Any]) -> dict[str, Any]:
    return {
        "checks": [
            {"name": r.name, "passed": r.passed, "detail": r.detail}
            for r in results
        ],
        **extra,
    }


def main() -> int:
    args = parse_args()
    report = validate(args)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    checks = report.get("checks", [])
    failed = [c for c in checks if not c.get("passed")]
    print(f"Contract alignment checks: {len(checks) - len(failed)}/{len(checks)} passed")
    print(f"Report: {args.output_json}")
    for item in checks:
        status = "PASS" if item.get("passed") else "FAIL"
        print(f"[{status}] {item.get('name')}: {item.get('detail')}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
