"""CLI for the unified manual review queue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from hytools.config.settings import load_config
from hytools.ingestion._shared.helpers import open_mongodb_client
from hytools.ingestion._shared.review_queue import get_review_collection


def _coerce_review_doc(doc: dict[str, Any]) -> dict[str, Any]:
    payload = dict(doc)
    payload.pop("_id", None)
    created_at = payload.get("created_at")
    if hasattr(created_at, "isoformat"):
        payload["created_at"] = created_at.isoformat()
    return payload


def list_review_items(
    client: Any,
    *,
    stage: str | None = None,
    queue_source: str | None = None,
    reason: str | None = None,
    include_reviewed: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    collection = get_review_collection(client)
    if collection is None:
        return []

    query: dict[str, Any] = {}
    if stage:
        query["stage"] = stage
    if queue_source:
        query["queue_source"] = queue_source
    if reason:
        query["reason"] = reason
    if not include_reviewed:
        query["reviewed"] = {"$ne": True}

    cursor = collection.find(query).sort([("priority", 1), ("created_at", -1)]).limit(limit)
    return [_coerce_review_doc(doc) for doc in cursor]


def mark_reviewed(client: Any, run_id: str, notes: str = "") -> int:
    collection = get_review_collection(client)
    if collection is None:
        return 0
    result = collection.update_one(
        {"run_id": run_id},
        {"$set": {"reviewed": True, "reviewer_notes": notes}},
    )
    return int(result.modified_count)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m hytools.ingestion.review")
    parser.add_argument("--config", type=Path, default=Path("config/settings.yaml"))
    sub = parser.add_subparsers(dest="command", required=True)

    list_p = sub.add_parser("list", help="List review queue items")
    list_p.add_argument("--stage", default=None)
    list_p.add_argument("--queue-source", default=None)
    list_p.add_argument("--reason", default=None)
    list_p.add_argument("--include-reviewed", action="store_true")
    list_p.add_argument("--limit", type=int, default=50)
    list_p.add_argument("--json", action="store_true")

    mark_p = sub.add_parser("mark-reviewed", help="Mark a review item as handled")
    mark_p.add_argument("run_id")
    mark_p.add_argument("--notes", default="")

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    cfg = load_config(str(args.config)) if args.config and args.config.exists() else {}

    with open_mongodb_client(cfg) as client:
        if client is None:
            print("MongoDB unavailable; review queue command requires a working database connection")
            return 1

        if args.command == "list":
            items = list_review_items(
                client,
                stage=getattr(args, "stage", None),
                queue_source=getattr(args, "queue_source", None),
                reason=getattr(args, "reason", None),
                include_reviewed=bool(getattr(args, "include_reviewed", False)),
                limit=int(getattr(args, "limit", 50)),
            )
            if getattr(args, "json", False):
                print(json.dumps(items, ensure_ascii=False, indent=2))
            else:
                for item in items:
                    print(
                        f"{item.get('priority', '?')} | {item.get('stage', ''):<16} | "
                        f"{item.get('reason', ''):<36} | {item.get('run_id', '')}"
                    )
                print(f"Total review items: {len(items)}")
            return 0

        if args.command == "mark-reviewed":
            updated = mark_reviewed(client, args.run_id, notes=getattr(args, "notes", ""))
            if updated:
                print(f"Marked reviewed: {args.run_id}")
                return 0
            print(f"No review item updated for run_id={args.run_id}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())