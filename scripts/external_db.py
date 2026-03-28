#!/usr/bin/env python
"""Helper utilities to store and retrieve external dataset content in MongoDB.

This module reads `config/settings.yaml` (or environment variables) to
connect to the MongoDB instance and provides small helpers used by fetchers
and the pairwise runner.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except Exception:
    yaml = None

from pymongo import MongoClient


def _require_pymongo_suggestion():
    raise RuntimeError(
        "pymongo is required to use the MongoDB helpers.\n"
        "Install it in your environment: `pip install pymongo` or `pip install -r requirements.txt`."
    )


def _load_config(path: str = "config/settings.yaml") -> Dict[str, Any]:
    cfg = {}
    if yaml is not None and Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    # allow environment override
    cfg.setdefault("mongodb_uri", os.environ.get("MONGODB_URI") )
    cfg.setdefault("mongodb_database", os.environ.get("MONGODB_DATABASE"))
    return cfg


def get_db(path: str = "config/settings.yaml"):
    if MongoClient is None:
        _require_pymongo_suggestion()
    cfg = _load_config(path)
    uri = cfg.get("mongodb_uri")
    dbname = cfg.get("mongodb_database")
    if not uri or not dbname:
        raise RuntimeError("MongoDB URI or database not found in config or environment")
    client = MongoClient(uri)
    return client[dbname]


def ensure_indexes_and_validation(config_path: str = "config/settings.yaml") -> None:
    """Create recommended indexes and a simple schema validator for `external_datasets`.

    Indexes:
      - tag (asc)
      - source_type (asc)
      - fetched_at (desc)

    Validation: ensure required fields and types for provenance tracking.
    """
    if MongoClient is None:
        _require_pymongo_suggestion()
    db = get_db(config_path)
    coll_name = "external_datasets"
    coll = db.get_collection(coll_name)

    # Create indexes
    coll.create_index([("tag", 1)], name="idx_tag")
    coll.create_index([("source_type", 1)], name="idx_source_type")
    coll.create_index([("fetched_at", -1)], name="idx_fetched_at")

    # Simple JSON schema validator (MongoDB 3.6+ supports validator option)
    validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["tag", "source_id", "source_type", "content", "fetched_at"],
            "properties": {
                "tag": {"bsonType": "string"},
                "source_id": {"bsonType": "string"},
                "source_type": {"bsonType": "string"},
                "content": {"bsonType": "string"},
                "metadata": {"bsonType": ["object", "null"]},
                "fetched_at": {"bsonType": ["double", "date", "int"]},
            },
        }
    }

    try:
        db.command({
            "collMod": coll_name,
            "validator": validator,
            "validationLevel": "moderate",
        })
    except Exception:
        # If collMod fails (collection may not exist), create collection with validator
        try:
            db.create_collection(coll_name, validator=validator)
        except Exception:
            # Some MongoDB deployments (Atlas free tier etc.) may not allow collMod/create with validator.
            # In that case, create indexes and continue.
            pass


def insert_external_record(tag: str, source_id: str, source_type: str, content: str, metadata: Optional[Dict[str, Any]] = None, config_path: str = "config/settings.yaml") -> str:
    db = get_db(config_path)
    coll = db.get_collection("external_datasets")
    doc = {
        "tag": tag,
        "source_id": source_id,
        "source_type": source_type,
        "content": content,
        "metadata": metadata or {},
        "fetched_at": time.time(),
    }
    res = coll.insert_one(doc)
    return str(res.inserted_id)


def fetch_external_tag(tag: str, limit: int = 100, config_path: str = "config/settings.yaml") -> List[Dict[str, Any]]:
    db = get_db(config_path)
    coll = db.get_collection("external_datasets")
    cursor = coll.find({"tag": tag}).limit(limit)
    return list(cursor)
