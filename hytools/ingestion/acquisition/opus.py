"""OPUS Armenian corpus downloader.

Downloads Armenian text from the OPUS parallel corpus repository
(object.pouta.csc.fi) and inserts into MongoDB.  Both Western and Eastern
Armenian are ingested and labelled by the WA classifier.

Corpora downloaded:
  - CCAligned    (en-hy):  Web-crawled parallel data, mixed WA/EA
  - NLLB         (en-hy):  Meta NLLB translation data, large
  - MultiCCAligned (en-hy): Extended CCAligned, mixed WA/EA
  - TED2020      (en-hy):  TED talk transcripts (high quality)
  - OpenSubtitles (en-hy): Movie/TV subtitles
  - QED          (en-hy):  Educational video subtitles
  - Tatoeba      (en-hy):  Community sentence pairs
  - bible-uedin  (en-hy):  Bible translations
  - wikimedia    (en-hy):  Wikipedia/Wikimedia translations
  - wikimedia    (en-hyw): Wikipedia Western Armenian
  - GNOME        (en-hy):  Software localization strings
  - KDE4         (en-hy):  Software localization strings
  - Ubuntu       (en-hy):  Software localization strings

Every chunk is classified by compute_wa_score regardless of the OPUS language
tag — metadata.language_code is derived from the actual text content.

Files are downloaded into a Python tempfile.TemporaryDirectory() and are
deleted automatically when the context exits. No intermediate files are
written to the permanent data directory.

Entry point: run(config)
"""

from __future__ import annotations

import io
import logging
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_REQUEST_DELAY = 1.0       # seconds between download retries / post-chunk sleeps
_MIN_LINE_CHARS = 30       # discard lines shorter than this (lowered from 50 to keep more parallel sentences)
_CHUNK_LINES = 20          # number of lines grouped into one MongoDB document
_PROGRESS_EVERY = 50_000   # log progress every N lines

_HEADERS = {
    "User-Agent": (
        "Python/armenian-corpus-core OPUS-downloader "
        "(research; western-armenian-llm)"
    )
}


@dataclass
class _OpusCorpus:
    """Metadata for one downloadable OPUS corpus."""
    name: str
    download_url: str
    armenian_lang: str    # IETF tag used in this corpus ("hyw", "hy")
    armenian_file: str    # filename inside the ZIP containing the Armenian text lines
    source_tag: str       # value written to MongoDB documents.source
    description: str = ""


# All corpora to fetch — ordered largest-first within priority tiers.
# There are NO hyw-specific pairs for CCAligned or NLLB on OPUS;
# only en-hy exists — text is classified WA/EA by compute_wa_score.
_CORPORA: list[_OpusCorpus] = [
    # --- Tier 1: large corpora (>10 MB) ---
    _OpusCorpus(
        name="CCAligned_hy",
        download_url="https://object.pouta.csc.fi/OPUS-CCAligned/v1/moses/en-hy.txt.zip",
        armenian_lang="hy",
        armenian_file="CCAligned.en-hy.hy",
        source_tag="opus_ccaligned_hy",
        description="CCAligned Armenian–English parallel corpus (105 MB, mixed WA/EA)",
    ),
    _OpusCorpus(
        name="NLLB_hy",
        download_url="https://object.pouta.csc.fi/OPUS-NLLB/v1/moses/en-hy.txt.zip",
        armenian_lang="hy",
        armenian_file="NLLB.en-hy.hy",
        source_tag="opus_nllb_hy",
        description="NLLB Armenian translation data (952 MB, mixed WA/EA)",
    ),
    _OpusCorpus(
        name="MultiCCAligned_hy",
        download_url="https://object.pouta.csc.fi/OPUS-MultiCCAligned/v1/moses/en-hy.txt.zip",
        armenian_lang="hy",
        armenian_file="MultiCCAligned.en-hy.hy",
        source_tag="opus_multiccaligned_hy",
        description="MultiCCAligned extended CCAligned (108 MB, mixed WA/EA)",
    ),
    # --- Tier 2: medium corpora (1-10 MB) ---
    _OpusCorpus(
        name="TED2020_hy",
        download_url="https://object.pouta.csc.fi/OPUS-TED2020/v1/moses/en-hy.txt.zip",
        armenian_lang="hy",
        armenian_file="TED2020.en-hy.hy",
        source_tag="opus_ted2020_hy",
        description="TED talk transcripts (2.8 MB, high-quality spoken Armenian)",
    ),
    _OpusCorpus(
        name="QED_hy",
        download_url="https://object.pouta.csc.fi/OPUS-QED/v2.0a/moses/en-hy.txt.zip",
        armenian_lang="hy",
        armenian_file="QED.en-hy.hy",
        source_tag="opus_qed_hy",
        description="QED educational video subtitles (2.7 MB)",
    ),
    _OpusCorpus(
        name="wikimedia_hy",
        download_url="https://object.pouta.csc.fi/OPUS-wikimedia/v20230407/moses/en-hy.txt.zip",
        armenian_lang="hy",
        armenian_file="wikimedia.en-hy.hy",
        source_tag="opus_wikimedia_hy",
        description="Wikipedia/Wikimedia translations (5.3 MB)",
    ),
    _OpusCorpus(
        name="bible_hy",
        download_url="https://object.pouta.csc.fi/OPUS-bible-uedin/v1/moses/en-hy.txt.zip",
        armenian_lang="hy",
        armenian_file="bible-uedin.en-hy.hy",
        source_tag="opus_bible_hy",
        description="Bible translations (1.2 MB, classical/formal Armenian)",
    ),
    # --- Tier 3: small corpora (<1 MB) ---
    _OpusCorpus(
        name="OpenSubtitles_hy",
        download_url="https://object.pouta.csc.fi/OPUS-OpenSubtitles/v2024/moses/en-hy.txt.zip",
        armenian_lang="hy",
        armenian_file="OpenSubtitles.en-hy.hy",
        source_tag="opus_opensubtitles_hy",
        description="Movie/TV subtitles (0.3 MB, colloquial Armenian)",
    ),
    _OpusCorpus(
        name="wikimedia_hyw",
        download_url="https://object.pouta.csc.fi/OPUS-wikimedia/v20230407/moses/en-hyw.txt.zip",
        armenian_lang="hyw",
        armenian_file="wikimedia.en-hyw.hyw",
        source_tag="opus_wikimedia_hyw",
        description="Wikipedia Western Armenian (0.1 MB, explicitly hyw-tagged)",
    ),
    _OpusCorpus(
        name="Tatoeba_hy",
        download_url="https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/moses/en-hy.txt.zip",
        armenian_lang="hy",
        armenian_file="Tatoeba.en-hy.hy",
        source_tag="opus_tatoeba_hy",
        description="Tatoeba community sentences (0.1 MB)",
    ),
    _OpusCorpus(
        name="GNOME_hy",
        download_url="https://object.pouta.csc.fi/OPUS-GNOME/v1/moses/en-hy.txt.zip",
        armenian_lang="hy",
        armenian_file="GNOME.en-hy.hy",
        source_tag="opus_gnome_hy",
        description="GNOME UI localization strings (6 KB)",
    ),
    _OpusCorpus(
        name="KDE4_hy",
        download_url="https://object.pouta.csc.fi/OPUS-KDE4/v2/moses/en-hy.txt.zip",
        armenian_lang="hy",
        armenian_file="KDE4.en-hy.hy",
        source_tag="opus_kde4_hy",
        description="KDE4 UI localization strings (24 KB)",
    ),
    _OpusCorpus(
        name="Ubuntu_hy",
        download_url="https://object.pouta.csc.fi/OPUS-Ubuntu/v14.10/moses/en-hy.txt.zip",
        armenian_lang="hy",
        armenian_file="Ubuntu.en-hy.hy",
        source_tag="opus_ubuntu_hy",
        description="Ubuntu UI localization strings (22 KB)",
    ),
]


def _download(url: str, dest: Path, timeout: int = 600) -> bool:
    """Stream-download a file from url to dest. Returns True on success."""
    try:
        resp = requests.get(url, stream=True, timeout=timeout, headers=_HEADERS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("OPUS download failed %s: %s", url, exc)
        return False

    total = 0
    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=1 << 20):  # 1 MB chunks
            fh.write(chunk)
            total += len(chunk)

    logger.info("Downloaded %.1f MB from %s", total / 1e6, url)
    return True


def _classify(text: str) -> tuple[str, float]:
    """Classify text dialect. Returns (language_code, wa_score).

    language_code is 'hyw' if score meets WA threshold, 'hye' otherwise.
    """
    try:
        from hytools.ingestion._shared.helpers import compute_wa_score, WA_SCORE_THRESHOLD
        score = compute_wa_score(text[:4000])
        lc = "hyw" if score >= WA_SCORE_THRESHOLD else "hye"
        return lc, score
    except ImportError:
        return "hyw", 0.0


def _find_armenian_file(zf: zipfile.ZipFile, corpus: _OpusCorpus) -> Optional[str]:
    """Locate the Armenian side text file inside the zip archive."""
    names = zf.namelist()

    # Exact filename match (ignoring any directory prefix)
    for name in names:
        if name.endswith(corpus.armenian_file) or Path(name).name == corpus.armenian_file:
            return name

    # Fallback: any file ending with the armenian_lang extension
    ext = f".{corpus.armenian_lang}"
    for name in names:
        if name.endswith(ext):
            return name

    logger.warning(
        "OPUS %s: Armenian file '%s' not found in zip (available: %s)",
        corpus.name, corpus.armenian_file, names[:10],
    )
    return None


def _ingest_corpus(corpus: _OpusCorpus, zip_path: Path, client, config: dict) -> dict:
    """Extract Armenian lines from zip, group into chunks, classify, and insert into MongoDB.

    Returns stats dict.
    """
    from hytools.ingestion._shared.helpers import insert_or_skip

    stats = {"lines": 0, "inserted": 0, "skipped": 0, "wa": 0, "ea": 0}

    try:
        zf = zipfile.ZipFile(zip_path, "r")
    except zipfile.BadZipFile as exc:
        logger.error("OPUS %s: bad zip file: %s", corpus.name, exc)
        return stats

    arm_file = _find_armenian_file(zf, corpus)
    if arm_file is None:
        zf.close()
        return stats

    logger.info("OPUS %s: processing %s", corpus.name, arm_file)

    chunk_lines: list[str] = []
    chunk_index = 0

    def _flush() -> None:
        nonlocal chunk_index
        if not chunk_lines:
            return

        text = "\n".join(chunk_lines)
        detected_lc, wa_score = _classify(text)

        if detected_lc == "hyw":
            stats["wa"] += 1
        else:
            stats["ea"] += 1

        meta = {
            "source_type": "dataset",
            "source_language_code": detected_lc,
            "source_language_codes": [detected_lc],
            "wa_score": round(wa_score, 2),
            "opus_corpus": corpus.name,
            "opus_lang": corpus.armenian_lang,
            "content_type": "parallel_corpus",
            "writing_category": "web",
        }

        if insert_or_skip(
            client,
            source=corpus.source_tag,
            title=f"{corpus.name} chunk {chunk_index}",
            text=text,
            url=None,
            metadata=meta,
            config=config,
        ):
            stats["inserted"] += 1

        chunk_index += 1
        chunk_lines.clear()

    with zf.open(arm_file) as raw:
        reader = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
        for line in reader:
            line = line.rstrip("\n\r")
            if len(line) < _MIN_LINE_CHARS:
                stats["skipped"] += 1
                continue

            stats["lines"] += 1
            chunk_lines.append(line)

            if len(chunk_lines) >= _CHUNK_LINES:
                _flush()

            if stats["lines"] % _PROGRESS_EVERY == 0:
                logger.info(
                    "OPUS %s: %d lines processed, %d inserted (WA=%d EA=%d)",
                    corpus.name, stats["lines"], stats["inserted"], stats["wa"], stats["ea"],
                )

    _flush()  # remaining lines
    zf.close()

    logger.info(
        "OPUS %s complete: lines=%d inserted=%d skipped=%d wa=%d ea=%d",
        corpus.name, stats["lines"], stats["inserted"], stats["skipped"],
        stats["wa"], stats["ea"],
    )
    return stats


def run(config: dict) -> None:
    """Entry point: download and ingest OPUS Armenian corpora into MongoDB.

    Config keys (under scraping.opus):
      corpora (list[str] | null, default null): corpus names to process.
        null = all corpora.  Example: ["CCAligned_hyw", "NLLB_hyw"]
    """
    from hytools.ingestion._shared.helpers import open_mongodb_client

    opus_cfg = (config.get("scraping") or {}).get("opus") or {}
    enabled: Optional[list[str]] = opus_cfg.get("corpora")  # None → all

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB client required for OPUS downloader")

        for corpus in _CORPORA:
            if enabled is not None and corpus.name not in enabled:
                logger.info("OPUS: skipping %s (not in enabled corpora list)", corpus.name)
                continue

            logger.info("=== OPUS: %s ===", corpus.name)
            logger.info("  %s", corpus.description)
            logger.info("  URL: %s", corpus.download_url)

            # Use a temp directory — contents deleted automatically on context exit
            with tempfile.TemporaryDirectory(prefix="opus_") as tmpdir:
                zip_path = Path(tmpdir) / f"{corpus.name}.zip"

                if not _download(corpus.download_url, zip_path):
                    logger.error("OPUS: download failed for %s, skipping", corpus.name)
                    continue

                time.sleep(_REQUEST_DELAY)
                stats = _ingest_corpus(corpus, zip_path, client, config)
                logger.info("OPUS %s stats: %s", corpus.name, stats)
                # zip_path is deleted when tmpdir context exits above
