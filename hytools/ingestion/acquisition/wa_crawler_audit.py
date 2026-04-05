"""Quality audit helpers for the web crawler output."""

from __future__ import annotations

import csv
import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)


def _value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _coerce_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    return {
        "url": getattr(result, "url", ""),
        "domain": getattr(result, "domain", ""),
        "title": getattr(result, "title", ""),
        "text": getattr(result, "text", ""),
        "armenian_char_ratio": getattr(result, "armenian_char_ratio", 0.0),
        "wa_score": getattr(result, "wa_score", 0.0),
        "dialect_label": getattr(result, "dialect_label", "inconclusive"),
    }


def build_audit_rows(results: Iterable[Any], profiles: Iterable[Any] | None = None) -> list[dict[str, Any]]:
    """Aggregate crawler output into per-domain audit rows."""

    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "pages": 0,
            "wa_total": 0.0,
            "arm_total": 0.0,
            "text_chars_total": 0,
            "dialects": Counter(),
            "sample_url": "",
        }
    )
    profile_map: dict[str, Any] = {}

    for profile in profiles or []:
        domain = _value(profile, "domain", "") or ""
        if domain:
            profile_map[domain] = profile

    for item in results:
        row = _coerce_result(item)
        domain = row.get("domain") or ""
        if not domain:
            continue
        entry = grouped[domain]
        entry["pages"] += 1
        entry["wa_total"] += float(row.get("wa_score") or 0.0)
        entry["arm_total"] += float(row.get("armenian_char_ratio") or 0.0)
        entry["text_chars_total"] += len((row.get("text") or "").strip())
        entry["dialects"][row.get("dialect_label") or "inconclusive"] += 1
        if not entry["sample_url"]:
            entry["sample_url"] = row.get("url") or ""

    rows: list[dict[str, Any]] = []
    for domain, stats in sorted(grouped.items()):
        profile = profile_map.get(domain)
        pages = max(int(stats["pages"]), 1)
        profile_pages_crawled = int(_value(profile, "pages_crawled", 0) or 0)
        profile_pages_accepted = int(_value(profile, "pages_accepted", 0) or 0)
        crawled = profile_pages_crawled or pages
        accepted = profile_pages_accepted or pages
        noise_ratio = round(1.0 - (accepted / max(crawled, 1)), 4)
        dialect_counter: Counter = stats["dialects"]
        rows.append(
            {
                "domain": domain,
                "pages": pages,
                "pages_crawled": crawled,
                "pages_accepted": accepted,
                "mean_wa_score": round(stats["wa_total"] / pages, 4),
                "mean_armenian_char_ratio": round(stats["arm_total"] / pages, 4),
                "mean_text_chars": round(stats["text_chars_total"] / pages, 1),
                "noise_ratio": noise_ratio,
                "dominant_dialect": dialect_counter.most_common(1)[0][0] if dialect_counter else "inconclusive",
                "dialect_breakdown": dict(dialect_counter),
                "sample_url": stats["sample_url"],
            }
        )

    return rows


def write_audit_reports(rows: Iterable[dict[str, Any]], *, csv_path: str | Path | None = None, json_path: str | Path | None = None) -> None:
    rows = list(rows)
    if csv_path:
        path = Path(csv_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "domain",
                    "pages",
                    "pages_crawled",
                    "pages_accepted",
                    "mean_wa_score",
                    "mean_armenian_char_ratio",
                    "mean_text_chars",
                    "noise_ratio",
                    "dominant_dialect",
                    "sample_url",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key) for key in writer.fieldnames})

    if json_path:
        path = Path(json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def load_crawler_results_from_mongodb(client, *, source: str = "web_crawler") -> list[dict[str, Any]]:
    if client is None:
        return []

    results: list[dict[str, Any]] = []
    try:
        cursor = client.documents.find(
            {"source": source},
            {
                "metadata.url": 1,
                "metadata.domain": 1,
                "metadata.armenian_char_ratio": 1,
                "metadata.wa_score": 1,
                "metadata.dialect_label": 1,
                "title": 1,
                "text": 1,
            },
        )
        for doc in cursor:
            metadata = (doc or {}).get("metadata") or {}
            results.append(
                {
                    "url": metadata.get("url") or "",
                    "domain": metadata.get("domain") or "",
                    "title": (doc or {}).get("title") or "",
                    "text": (doc or {}).get("text") or "",
                    "armenian_char_ratio": metadata.get("armenian_char_ratio") or 0.0,
                    "wa_score": metadata.get("wa_score") or 0.0,
                    "dialect_label": metadata.get("dialect_label") or "inconclusive",
                }
            )
    except Exception as exc:
        logger.warning("Crawler audit: could not load MongoDB results: %s", exc)
    return results