#!/usr/bin/env python
"""Fetch external sources listed in a manifest and aggregate them per tag.

Manifest format (JSON array):
[
  {"tag": "ext:english", "id": "study1", "source_type": "url", "path": "https://example.com/text1.txt"},
  {"tag": "ext:spanish", "id": "local1", "source_type": "file", "path": "/data/spanish/sample.txt"}
]

This script writes per-source files under `analysis/external/{tag}/{id}.txt` and
also a concatenated `analysis/external/{tag}.txt` used by the pairwise runner.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import List

try:
    import requests
except Exception:
    requests = None

import sys
from pathlib import Path as _Path
_scripts_dir = str(_Path(__file__).resolve().parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
from external_db import insert_external_record


def strip_html_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def fetch_url(url: str) -> str:
    if requests is None:
        raise RuntimeError("requests library is required to fetch URLs")
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "")
    text = resp.text
    if "html" in content_type:
        text = strip_html_tags(text)
    return text


def read_local(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Local file not found: {path}")
    return p.read_text(encoding="utf-8")


def load_manifest(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Load external sources manifest and save into MongoDB")
    parser.add_argument("--manifest", required=True, help="Path to JSON manifest")
    parser.add_argument("--config", default="config/settings.yaml", help="Path to config YAML for MongoDB")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)

    for entry in manifest:
        tag = entry.get("tag")
        sid = entry.get("id") or entry.get("path")
        stype = entry.get("source_type")
        path = entry.get("path")
        if not tag or not stype or not path:
            print("Skipping invalid manifest entry:", entry)
            continue

        try:
            if stype == "url":
                text = fetch_url(path)
            elif stype == "file":
                text = read_local(path)
            else:
                print("Unsupported source_type", stype, "for entry", entry)
                continue
        except Exception as exc:
            print("Failed to fetch", entry, exc)
            continue

        # insert into MongoDB
        try:
            inserted_id = insert_external_record(tag, sid, stype, text, metadata={"source_path": path}, config_path=args.config)
            print(f"Inserted external record {inserted_id} for tag {tag}")
        except Exception as exc:
            print("Failed to insert into MongoDB:", exc)


if __name__ == "__main__":
    main()
