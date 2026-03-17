#!/usr/bin/env python3
"""Validate corpus data integrity in MongoDB.

Checks document counts, required fields, dialect tag validity,
source distribution, and content hash completeness.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    name: str
    passed: bool
    detail: str


def _validate(client) -> dict[str, Any]:
    docs = client.documents
    results: list[ValidationResult] = []
    extra: dict[str, Any] = {}

    total = docs.count_documents({})
    results.append(ValidationResult(
        "documents_exist",
        total > 0,
        f"total_documents={total}",
    ))

    non_empty = docs.count_documents({"text": {"$exists": True, "$ne": ""}})
    results.append(ValidationResult(
        "non_empty_text",
        non_empty > 0,
        f"documents_with_text={non_empty}/{total}",
    ))

    sample = list(docs.find().limit(100))
    required_fields = {"source", "title", "text", "content_hash"}
    if sample:
        first_keys = set(sample[0].keys())
        missing = sorted(required_fields - first_keys)
        results.append(ValidationResult(
            "required_fields_present",
            not missing,
            "ok" if not missing else f"missing: {missing}",
        ))
    else:
        results.append(ValidationResult(
            "required_fields_present", False, "no documents to check",
        ))

    allowed_language_codes = {"hyw", "hye", "hy", "hyc", "eng", "und"}
    # Check both old (language_code) and new (source_language_code) field names.
    lang_values_old = docs.distinct("metadata.language_code")
    lang_values_new = docs.distinct("metadata.source_language_code")
    lang_values = list(set(lang_values_old + lang_values_new))
    bad_lc = sorted(set(str(lc) for lc in lang_values if lc) - allowed_language_codes - {None})
    results.append(ValidationResult(
        "language_code_values",
        not bad_lc,
        "ok" if not bad_lc else f"unexpected language_code values: {bad_lc}",
    ))
    extra["language_codes"] = [str(lc) for lc in lang_values]

    pipeline = [
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    source_dist = {r["_id"]: r["count"] for r in docs.aggregate(pipeline)}
    results.append(ValidationResult(
        "multiple_sources",
        len(source_dist) >= 2,
        f"sources={len(source_dist)}: {source_dist}",
    ))
    extra["source_distribution"] = source_dist

    with_hash = docs.count_documents({"content_hash": {"$exists": True, "$ne": ""}})
    results.append(ValidationResult(
        "content_hashes_present",
        with_hash == total,
        f"with_hash={with_hash}/{total}",
    ))

    with_norm_hash = docs.count_documents({"normalized_content_hash": {"$exists": True, "$ne": ""}})
    results.append(ValidationResult(
        "normalized_hashes_present",
        with_norm_hash == total,
        f"with_normalized_hash={with_norm_hash}/{total}",
    ))
    extra["normalized_hash_count"] = with_norm_hash

    summary = {
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "total": len(results),
    }

    return {
        "checks": [{"name": r.name, "passed": r.passed, "detail": r.detail} for r in results],
        "summary": summary,
        **extra,
    }


def run(config: dict) -> None:
    from ingestion._shared.helpers import open_mongodb_client

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for validation")

        report = _validate(client)

        client.metadata.replace_one(
            {"stage": "validate_contract_alignment"},
            {
                "stage": "validate_contract_alignment",
                "timestamp": datetime.now(timezone.utc),
                "report": report,
            },
            upsert=True,
        )

        checks = report.get("checks", [])
        failed = [c for c in checks if not c.get("passed")]
        print(f"Validation: {len(checks) - len(failed)}/{len(checks)} passed")
        for item in checks:
            status = "PASS" if item["passed"] else "FAIL"
            print(f"  [{status}] {item['name']}: {item['detail']}")

        if failed:
            raise RuntimeError(f"Validation failed: {len(failed)} checks")


def _load_config(config_path: str | None) -> dict:
    if not config_path:
        return {}
    from pathlib import Path
    p = Path(config_path)
    if not p.exists():
        return {}
    import yaml
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main() -> int:
    import argparse
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Validate corpus data integrity in MongoDB")
    parser.add_argument("--config", type=str, default=None, help="Path to YAML config (database.*)")
    args = parser.parse_args()
    config = _load_config(args.config)
    try:
        run(config)
        return 0
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
