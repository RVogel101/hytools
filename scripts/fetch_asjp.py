#!/usr/bin/env python
"""Simple downloader for ASJP resources.

This script downloads a provided ASJP file (zip/tsv/csv) and writes it to
`analysis/external/asjp/`. The ASJP website: https://asjp.clld.org/

Usage:
  python scripts/fetch_asjp.py --url <download_url>
"""
from __future__ import annotations

import argparse
import os
import shutil
import zipfile
from pathlib import Path

try:
    import requests
except Exception:
    requests = None

from io import BytesIO
import sys
from pathlib import Path as _Path
_scripts_dir = str(_Path(__file__).resolve().parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
from external_db import insert_external_record


def download_to_bytes(url: str) -> bytes:
    if requests is None:
        raise RuntimeError("requests required; pip install requests")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content


def extract_zip_bytes(content: bytes) -> dict:
    out = {}
    with zipfile.ZipFile(BytesIO(content)) as z:
        for name in z.namelist():
            try:
                data = z.read(name)
                try:
                    text = data.decode("utf-8")
                except Exception:
                    text = data.decode("latin-1", errors="ignore")
                out[name] = text
            except Exception:
                continue
    return out


def main():
    parser = argparse.ArgumentParser(description="Download ASJP file and save under analysis/external/asjp")
    parser.add_argument("--url", required=True, help="Download URL for ASJP resource (zip or csv/tsv)")
    parser.add_argument("--outdir", default="analysis/external/asjp", help="Output directory")
    args = parser.parse_args()

    filename = Path(args.url).name or "asjp_download"
    try:
        print("Downloading", args.url)
        data = download_to_bytes(args.url)
        # if zip, extract and insert each member
        try:
            z = zipfile.ZipFile(BytesIO(data))
            members = extract_zip_bytes(data)
            for name, txt in members.items():
                sid = f"{filename}:{name}"
                try:
                    insert_external_record("ext:asjp", sid, "asjp_zip_member", txt, metadata={"member_name": name, "source_url": args.url}, config_path="config/settings.yaml")
                    print("Inserted", sid)
                except Exception as exc:
                    print("Failed to insert member", name, exc)
        except zipfile.BadZipFile:
            # treat as single text file
            try:
                text = data.decode("utf-8")
            except Exception:
                text = data.decode("latin-1", errors="ignore")
            try:
                insert_external_record("ext:asjp", filename, "asjp_file", text, metadata={"source_url": args.url}, config_path="config/settings.yaml")
                print("Inserted asjp file", filename)
            except Exception as exc:
                print("Failed to insert ASJP file:", exc)
    except Exception as exc:
        print("Failed to download or process ASJP resource:", exc)


if __name__ == "__main__":
    main()
