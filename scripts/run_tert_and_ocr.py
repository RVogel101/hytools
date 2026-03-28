"""Run tert_nla scraper then run pipeline stages hamazkayin + ocr_ingest using config/settings.yaml.

Usage: python scripts/run_tert_and_ocr.py
"""
from __future__ import annotations
import sys
import json
import traceback
from pathlib import Path
import yaml

cfg_path = Path('config/settings.yaml')
if not cfg_path.exists():
    print('ERROR: config/settings.yaml not found', file=sys.stderr)
    sys.exit(2)

cfg = yaml.safe_load(cfg_path.read_text(encoding='utf-8'))

# Run tert_nla
try:
    print('RUN_TERT_NLA_START')
    from hytools.ingestion.acquisition import tert_nla
    stats = tert_nla.run(cfg)
    print('TERT_NLA_STATS:' + json.dumps(stats, ensure_ascii=False))
except Exception:
    print('TERT_NLA_ERROR:\n' + traceback.format_exc(), file=sys.stderr)

# Run hamazkayin and ocr_ingest via runner
try:
    print('RUN_PIPELINE_START')
    from hytools.ingestion.runner import run_pipeline
    summary = run_pipeline(cfg, only=['hamazkayin', 'ocr_ingest'])
    print('PIPELINE_SUMMARY:' + json.dumps(summary, ensure_ascii=False))
except Exception:
    print('PIPELINE_ERROR:\n' + traceback.format_exc(), file=sys.stderr)

print('DONE')
