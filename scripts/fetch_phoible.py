#!/usr/bin/env python
"""Downloader for PHOIBLE inventories (requires a download URL).

PHOIBLE provides inventories and can be downloaded from https://phoible.org/
Use this script with the PHOIBLE download URL to save CSV/zip into
`analysis/external/phoible/`.
"""
from __future__ import annotations

import argparse
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


def fetch_to_bytes(url: str) -> bytes:
    if requests is None:
        raise RuntimeError("requests required; pip install requests")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


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
    parser = argparse.ArgumentParser(description="Download PHOIBLE resources to analysis/external/phoible")
    parser.add_argument("--url", required=True, help="Download URL for PHOIBLE resource (zip/csv)")
    parser.add_argument("--outdir", default="analysis/external/phoible", help="Output directory")
    args = parser.parse_args()

    filename = Path(args.url).name or "phoible_download"
    try:
        print("Fetching", args.url)
        data = fetch_to_bytes(args.url)
        # try to extract zip members
        try:
            members = extract_zip_bytes(data)
            for name, txt in members.items():
                sid = f"{filename}:{name}"
                try:
                    insert_external_record("ext:phoible", sid, "phoible_zip_member", txt, metadata={"member_name": name, "source_url": args.url}, config_path="config/settings.yaml")
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
                insert_external_record("ext:phoible", filename, "phoible_file", text, metadata={"source_url": args.url}, config_path="config/settings.yaml")
                print("Inserted phoible file", filename)
            except Exception as exc:
                print("Failed to insert PHOIBLE file:", exc)
    except Exception as exc:
        print("Failed to fetch PHOIBLE resource:", exc)


if __name__ == "__main__":
    main()
