"""Near-duplicate document removal using MinHash LSH.

Uses the ``datasketch`` library to build a MinHash signature for each
document and remove near-duplicates above a configurable Jaccard
similarity threshold.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path

import yaml  # type: ignore[reportMissingModuleSource]

try:
    from datasketch import MinHash, MinHashLSH  # type: ignore[reportMissingModuleSource]
except ImportError:  # pragma: no cover - optional dependency
    MinHash = None  # type: ignore
    MinHashLSH = None  # type: ignore
    _DATASKETCH_AVAILABLE = False
else:
    _DATASKETCH_AVAILABLE = True


logger = logging.getLogger(__name__)

_SETTINGS_PATH = Path(__file__).parents[2] / "config" / "settings.yaml"


def _load_config() -> dict:
    with open(_SETTINGS_PATH) as f:
        return yaml.safe_load(f)


def _sha256_text(text: str) -> str:
    """Return SHA256 hash for a piece of text."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _sha256_file(txt_file: Path) -> str:
    text = txt_file.read_text(encoding="utf-8")
    return _sha256_text(text)


def _shingles(text: str, k: int = 5) -> set[bytes]:
    """Return the set of k-character shingles for *text*, encoded as bytes."""
    if len(text) < k:
        return {text.encode("utf-8")} if text else set()
    return {text[i : i + k].encode("utf-8") for i in range(len(text) - k + 1)}


def build_minhash(text: str, num_perm: int = 128):
    """Build a MinHash signature for *text*."""
    if MinHash is None:
        raise RuntimeError("datasketch is not installed; install with pip install datasketch")
    m = MinHash(num_perm=num_perm)
    for shingle in _shingles(text):
        m.update(shingle)
    return m


def deduplicate_files(
    input_dir: Path,
    output_dir: Path,
    threshold: float = 0.85,
    num_perm: int = 128,
) -> tuple[int, int]:
    """Remove near-duplicate ``.txt`` files.

    Reads all ``.txt`` files from *input_dir*, filters out near-duplicates,
    and writes unique documents to *output_dir*.

    Parameters
    ----------
    input_dir:
        Directory containing cleaned ``.txt`` files.
    output_dir:
        Directory to write deduplicated files.
    threshold:
        Jaccard similarity threshold for considering two documents duplicates.
    num_perm:
        Number of hash permutations for MinHash (higher = more accurate).

    Returns
    -------
    tuple[int, int]
        ``(total, kept)`` — total documents processed and documents kept.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(input_dir.rglob("*.txt"))
    total = len(files)

    # Step 0: exact-hash dedup (fast, exact match)
    t0 = time.perf_counter()
    sha2file: dict[str, Path] = {}
    duplicates = 0
    for txt_file in files:
        doc_hash = _sha256_file(txt_file)
        if doc_hash in sha2file:
            duplicates += 1
            continue
        sha2file[doc_hash] = txt_file

    exact_dedup_duration = time.perf_counter() - t0
    remaining = list(sha2file.values())
    logger.info(
        "Exact dedupe: %d / %d duplicates removed in %.2fs, remaining=%d",
        duplicates, total, exact_dedup_duration, len(remaining),
    )

    if not _DATASKETCH_AVAILABLE:
        logger.warning("datasketch unavailable: skipping MinHash dedup and copying %d files", len(remaining))
        for txt_file in remaining:
            rel = txt_file.relative_to(input_dir)
            out = output_dir / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(txt_file.read_text(encoding="utf-8"), encoding="utf-8")
        return total, len(remaining)

    if MinHashLSH is None:
        raise RuntimeError("datasketch is not installed; install with pip install datasketch")
    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)

    t1 = time.perf_counter()
    logger.info("Phase 1: MinHash indexing and query on %d files", len(remaining))
    kept = 0

    for idx, txt_file in enumerate(remaining):
        text = txt_file.read_text(encoding="utf-8")
        key = hashlib.md5(str(txt_file).encode()).hexdigest()
        mh = build_minhash(text, num_perm=num_perm)

        if lsh.query(mh):
            logger.debug("Duplicate: %s", txt_file.name)
            continue

        lsh.insert(key, mh)
        rel = txt_file.relative_to(input_dir)
        out = output_dir / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        kept += 1

        if (idx + 1) % 500 == 0:
            logger.info("  Processed %d / %d files, kept %d", idx + 1, len(remaining), kept)

    phase1_duration = time.perf_counter() - t1
    logger.info("Phase 1 complete: %d kept %d after MinHash dedup in %.2fs", len(remaining), kept, phase1_duration)

    total_remain = len(remaining)
    logger.info("Deduplication complete: %d / %d documents kept (total input %d, exact duplicates %d)", kept, total_remain, total, duplicates)
    return total, kept


def run(config: dict | None = None) -> None:
    """Entry-point: deduplicate the cleaned corpus."""
    cfg = config or _load_config()
    cleaned_dir = Path(cfg["paths"]["cleaned_dir"])
    dedup_dir = cleaned_dir.parent / "deduped"
    clean_cfg = cfg["cleaning"]

    deduplicate_files(
        cleaned_dir,
        dedup_dir,
        threshold=clean_cfg["minhash_threshold"],
        num_perm=clean_cfg["minhash_num_perm"],
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
