"""Language detection and filtering for Western Armenian text.

Uses compute_wa_score and is_western_armenian from hytool.ingestion._shared.helpers (single
source of truth). Provides filter_directory for file-based cleaning and
detect_dialect_mixing_with_author for author-aware dialect checks.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml  # type: ignore[reportMissingModuleSource]

from hytool.ingestion._shared.helpers import (
    WA_SCORE_THRESHOLD,
    compute_wa_score,
    is_armenian,
    is_western_armenian,
)

from .author_database import (
    Dialect,
    detect_author_from_text,
)

logger = logging.getLogger(__name__)

_SETTINGS_PATH = Path(__file__).parents[2] / "config" / "settings.yaml"


def detect_dialect_mixing_with_author(text: str) -> dict:
    """Detect potential dialect mixing based on author context.

    Checks if a known author is mentioned in the text, and if so,
    verifies that their dialect tradition matches the detected text dialect.
    This catches cases where an Eastern Armenian author attempts to write
    in Western Armenian without complete mastery.

    Parameters
    ----------
    text:
        Input document text to analyze

    Returns
    -------
    dict with keys:
        - author_detected: (AuthorRecord or None)
        - author_name: (str or None)
        - author_dialect: (str or None, e.g., "western", "eastern")
        - text_dialect: (str, "western" or "eastern" or "unknown")
        - dialect_mismatch: (bool, True if author dialect != text dialect)
        - confidence: (float, 0-1 indicating confidence in WA classification)
        - recommendation: (str, "ACCEPT", "FLAG", or "REJECT")
    """
    author_record, author_name = detect_author_from_text(text)

    # Compute text dialect with confidence score
    wa_score = compute_wa_score(text)
    is_wa = wa_score >= WA_SCORE_THRESHOLD
    text_dialect = "western" if is_wa else "eastern" if wa_score < 0 else "unknown"
    confidence = min(abs(wa_score) / 10.0, 1.0)  # Normalize to 0-1

    # Check for dialect mismatch with author
    dialect_mismatch = False
    recommendation = "ACCEPT"

    if author_record:
        dialect = author_record.dialect
        author_dialect = dialect.value if dialect is not None else None
        if dialect is not None and is_wa and dialect == Dialect.EASTERN_ARMENIAN:
            # EA author writing Western Armenian → potential issue
            dialect_mismatch = True
            recommendation = "FLAG" if confidence < 0.8 else "ACCEPT"
        elif dialect is not None and not is_wa and dialect == Dialect.WESTERN_ARMENIAN:
            # WA author but text reads as EA → contamination or misclassification
            dialect_mismatch = True
            recommendation = "FLAG"
    else:
        author_dialect = None

    return {
        "author_detected": author_record,
        "author_name": author_name,
        "author_dialect": author_dialect,
        "text_dialect": text_dialect,
        "dialect_mismatch": dialect_mismatch,
        "confidence": confidence,
        "wa_score": wa_score,
        "recommendation": recommendation,
    }


def filter_directory(
    input_dir: Path,
    output_dir: Path,
    require_western: bool = False,
    min_chars: int = 100,
) -> tuple[int, int]:
    """Copy Armenian (optionally Western-only) documents to *output_dir*.

    Parameters
    ----------
    input_dir:
        Directory of ``.txt`` files to filter.
    output_dir:
        Destination for passing documents.
    require_western:
        If True, only keep documents detected as Western Armenian.
    min_chars:
        Minimum character count; shorter documents are discarded.

    Returns
    -------
    tuple[int, int]
        ``(total, kept)``.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(input_dir.rglob("*.txt"))
    total = len(files)
    kept = 0

    for txt_file in files:
        text = txt_file.read_text(encoding="utf-8")
        if len(text) < min_chars:
            continue
        if not is_armenian(text):
            logger.debug("Non-Armenian, skipping: %s", txt_file.name)
            continue
        if require_western and not is_western_armenian(text):
            score = compute_wa_score(text)
            logger.debug(
                "Not Western Armenian (score=%.1f), skipping: %s",
                score, txt_file.name,
            )
            continue

        rel = txt_file.relative_to(input_dir)
        out = output_dir / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        kept += 1

    logger.info("Language filter: %d / %d documents kept", kept, total)
    return total, kept


def run(config: dict | None = None) -> None:
    """Entry-point: filter the deduplicated corpus to Western Armenian only."""
    cfg = config or _load_config()
    dedup_dir = Path(cfg["paths"]["cleaned_dir"]).parent / "deduped"
    filtered_dir = Path(cfg["paths"]["cleaned_dir"]).parent / "filtered"
    min_chars: int = cfg["cleaning"]["min_chars_per_doc"]

    filter_directory(dedup_dir, filtered_dir, require_western=True, min_chars=min_chars)


def _load_config() -> dict:
    with open(_SETTINGS_PATH) as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()

