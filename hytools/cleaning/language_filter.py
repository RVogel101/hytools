"""Language filtering wrapper for WesternArmenianLLM.

This module delegates WA/EA classification and filtering behavior to
hytools implementation (`hytools.ingestion._shared.helpers` and
`hytools.cleaning.language_filter`), acting as a thin interface for this
project.

The logic in this module avoids local duplication and author-based heuristics
and sources the rules from hytools as the canonical source of truth.
"""

from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml
from tqdm import tqdm

_DEFAULT_WORKERS = max(4, min((os.cpu_count() or 4) - 2, 16))

from hytools.cleaning.author_database import (
    detect_author_from_text,
    get_authors_by_dialect,
)
from hytools.ingestion._shared.metadata import Dialect
from hytools.ingestion._shared.helpers import (
    get_classical_markers,
    get_lexical_markers,
    get_wa_vocabulary_markers,
    get_eastern_markers,
    get_wa_standalone_patterns,
    get_wa_suffix_patterns,
    get_ea_regex_patterns,
    get_word_internal_e_long_re,
    get_word_ending_ay_re,
    get_word_ending_oy_re,
    get_wa_authors,
    get_wa_publication_cities,
    get_wa_score_threshold,
    _ARM_WB_L,
    _ARM_WB_R,
    _ARM_PRECEDED,
    _ARMENIAN_PUNCT,
    _REFORMED_SUFFIX_RE,
    _CLASSICAL_SUFFIX_RE,
    _WA_PUBLICATION_CITIES,
    _EAST_ARMENIAN_AUTHORS,
)

logger = logging.getLogger(__name__)

_SETTINGS_PATH = Path(__file__).parents[2] / "config" / "settings.yaml"

# Rule sets (WA/EA markers, authors, and regex signals) are now imported
# from hytools.ingestion._shared.helpers to avoid duplication.
# See hytools.ingestion._shared.helpers for authoritative definitions and
# migration strategy.

# (The remaining code in this module computes scoring from these constants.)

# == 2d. Known East Armenian authors (Soviet/Yerevan literary figures) =========
#
# PLANNED FUTURE FEATURE: Track Eastern Armenian authors to detect when
# they are writing in Western Armenian incorrectly (mixing dialects).
# This helps catch documents with code-switching or incorrect WA usage.
#
# Examples of well-known EA authors (for future reference):
# - Հովհաննես Թուման (Hovhannes Tumanyan)
# - Առաբա (Arawba/Zardaryan)
# - Վահան Թերյան (Vahan Teryan)
# - Ծեղين Դավտյան (Tseghin Davtyan)
# - Գրիգոր Նաբար (Grigor Nebar)
#
# ACTION ITEMS:
# 1. Build a database of EA authors and their works (from Soviet Armenian literary canon)
# 2. When an EA author is detected, flag mixed-dialect usage more aggressively
# 3. Use author lexical fingerprints (EA-specific vocabulary they use frequently)


# Publication city matching is now handled via get_wa_publication_cities() from helpers.

# == Regex for word-internal long-e ============================================
# In classical orthography, long-e appears word-internally.
# The Soviet reform changed many word-internal long-e to short-e.
# Word-internal and word-final patterns are now sourced via helper getters
# get_word_internal_e_long_re(), get_word_ending_ay_re(), and get_word_ending_oy_re().

# Word-boundary-aware markers and EA regex markers are sourced from helpers.
# WA score threshold and Armenian punctuation are provided by helpers.

# Armenian-specific punctuation and symbols (not shared with Latin) are handled via _ARMENIAN_PUNCT from helpers.


def _classify_characters(text: str) -> dict[str, int]:
    """Classify characters in *text* into categories.

    Whitespace is excluded entirely.  Returns counts for:
    - armenian_letters: Armenian Unicode block (U+0531–U+0587)
    - armenian_punct: Armenian-specific punctuation
    - latin: Basic + Extended Latin (A-Z, a-z, À-ž)
    - digits: 0-9
    - common_punct: Punctuation shared across scripts (.,;:!?-"'()[] etc.)
    - other: everything else (Cyrillic, Arabic, CJK, misc symbols)
    """
    counts: dict[str, int] = {
        "armenian_letters": 0,
        "armenian_punct": 0,
        "latin": 0,
        "digits": 0,
        "common_punct": 0,
        "other": 0,
    }
    for ch in text:
        if ch.isspace():
            continue
        if "\u0531" <= ch <= "\u0587":
            counts["armenian_letters"] += 1
        elif ch in _ARMENIAN_PUNCT:
            counts["armenian_punct"] += 1
        elif ("\u0041" <= ch <= "\u005A") or ("\u0061" <= ch <= "\u007A") or ("\u00C0" <= ch <= "\u024F"):
            counts["latin"] += 1
        elif ch.isdigit():
            counts["digits"] += 1
        elif ch in ".,;:!?-\"'()[]{}/@#$%^&*+=~`|\\_<>":
            counts["common_punct"] += 1
        else:
            counts["other"] += 1
    return counts


def _has_armenian_script(text: str, threshold: float = 0.35) -> bool:
    """Return True if Armenian characters dominate the non-whitespace text.

    Counts Armenian letters + Armenian-specific punctuation as "Armenian".
    Whitespace is excluded from the denominator so formatting doesn't
    dilute the ratio.  Default threshold is 35%.
    """
    if not text:
        return False
    counts = _classify_characters(text)
    total_non_ws = sum(counts.values())
    if total_non_ws == 0:
        return False
    armenian_total = counts["armenian_letters"] + counts["armenian_punct"]
    return armenian_total / total_non_ws >= threshold


# NOTE: `is_armenian` removed — language/dialect determination is centralized.
# See `WesternArmenianLLM` and `hytools` integration points for canonical
# classifier usage. Retained internal helpers (e.g. `_has_armenian_script`) for
# inspection and migration support.


# ---------------------------------------------------------------------------
# Bilingual-split detection & line-level Armenian extraction
# ---------------------------------------------------------------------------

def _armenian_ratio(text: str) -> float:
    """Return fraction of non-whitespace chars that are Armenian (letters + punct)."""
    counts = _classify_characters(text)
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return (counts["armenian_letters"] + counts["armenian_punct"]) / total


def _line_is_armenian(line: str, threshold: float = 0.5) -> bool:
    """Return True if a single line is predominantly Armenian.

    Empty / whitespace-only lines are considered neutral (True) so they
    don't cause gaps in otherwise-Armenian text.
    """
    stripped = line.strip()
    if not stripped:
        return True  # blank lines are neutral
    return _armenian_ratio(stripped) >= threshold


def extract_armenian_content(text: str, min_chars: int = 100) -> str | None:
    """Extract Armenian-only content from potentially bilingual text.

    Strategy (applied in order):

    1. **Half-split detection**: If the document looks like a parallel
       translation (one half Armenian, one half not), keep only the
       Armenian half.
    2. **Line-level filtering**: Remove individual non-Armenian lines
       (Latin paragraphs, English headers, etc.).
    3. **Final check**: If the cleaned text is too short or still has
       too much non-Armenian content, return None.

    Parameters
    ----------
    text:
        Raw document text.
    min_chars:
        Minimum character count for the result to be accepted.

    Returns
    -------
    str or None
        Cleaned Armenian-only text, or None if not enough Armenian
        content remains after extraction.
    """
    lines = text.splitlines()
    if not lines:
        return None

    # ── Phase 1: Half-split detection ────────────────────────────────
    # Many diaspora documents are parallel translations: first half is
    # Armenian, second half is English/French (or vice versa).
    # Split at the midpoint and check each half independently.
    mid = len(lines) // 2
    first_half = "\n".join(lines[:mid])
    second_half = "\n".join(lines[mid:])

    r_first = _armenian_ratio(first_half)
    r_second = _armenian_ratio(second_half)

    # One half is clearly Armenian (≥50%) and the other is clearly not (<20%)
    STRONG_ARM = 0.50
    WEAK_ARM = 0.20

    if r_first >= STRONG_ARM and r_second < WEAK_ARM:
        # First half is Armenian, second half is the translation
        text = first_half
        lines = text.splitlines()
    elif r_second >= STRONG_ARM and r_first < WEAK_ARM:
        # Second half is Armenian, first half is the translation
        text = second_half
        lines = text.splitlines()
    # else: both halves are mixed or both Armenian — proceed to line filtering

    # ── Phase 2: Line-level filtering ────────────────────────────────
    # Remove individual lines that are predominantly non-Armenian.
    # Keep blank lines only if they're between Armenian lines (don't
    # accumulate trailing blanks).
    armenian_lines: list[str] = []
    for line in lines:
        if _line_is_armenian(line):
            armenian_lines.append(line)
        # else: drop this non-Armenian line

    # Strip trailing blank lines that were between Armenian and non-Armenian
    while armenian_lines and not armenian_lines[-1].strip():
        armenian_lines.pop()

    result = "\n".join(armenian_lines).strip()

    # ── Phase 3: Final validation ────────────────────────────────────
    if len(result) < min_chars:
        return None
    # After all cleaning, Armenian should dominate
    if _armenian_ratio(result) < 0.35:
        return None

    return result


def compute_wa_score(text: str) -> float:
    """Compute a weighted Western Armenian score for *text*.

    The score is the sum of per-occurrence weights across all signal
    categories.  A higher score means stronger WA signal.
    
    Includes both positive (WA markers) and negative (EA reform markers)
    signals to improve accuracy.
    """
    if not text:
        return 0.0

    score = 0.0

    # 1. Classical orthographic markers (POSITIVE: WA signal)
    for marker, weight in get_classical_markers():
        count = text.count(marker)
        if count:
            score += weight * min(count, 10)

    # 2. Lexical / grammatical markers (POSITIVE: WA signal)
    for marker, weight in get_lexical_markers():
        count = text.count(marker)
        if count:
            score += weight * min(count, 10)

    # 2a-i. WA standalone words via regex (word-boundary-safe)
    for pattern, weight in get_wa_standalone_patterns():
        hits = len(pattern.findall(text))
        if hits:
            score += weight * min(hits, 10)

    # 2a-ii. WA suffixes via regex (word-boundary-safe)
    for pattern, weight in get_wa_suffix_patterns():
        hits = len(pattern.findall(text))
        if hits:
            score += weight * min(hits, 10)

    # 2b. WA-specific vocabulary (POSITIVE: WA signal)
    for marker, weight in get_wa_vocabulary_markers():
        count = text.count(marker)
        if count:
            score += weight * min(count, 10)

    # 2c. Eastern Armenian reform markers — substring (NEGATIVE: EA signal)
    for marker, weight in get_eastern_markers():
        # get_eastern_markers includes EA reform + EA vocab patterns
        count = text.count(marker)
        if count:
            score -= weight * min(count, 10)

    # 2d. Eastern Armenian markers — regex (NEGATIVE: EA signal)
    for pattern, weight in get_ea_regex_patterns():
        hits = len(pattern.findall(text))
        if hits:
            score -= weight * min(hits, 10)

    # 3. Word-internal long-e (POSITIVE: classical orthography = WA signal)
    internal_hits = len(get_word_internal_e_long_re().findall(text))
    if internal_hits:
        score += 1.0 * min(internal_hits, 20)

    # 3b. Word-final diphthongs -ay and -oy (POSITIVE: classical orthography)
    ay_hits = len(get_word_ending_ay_re().findall(text))
    oy_hits = len(get_word_ending_oy_re().findall(text))
    if ay_hits:
        score += 1.5 * min(ay_hits, 15)
    if oy_hits:
        score += 2.0 * min(oy_hits, 15)

    # 4. Author names
    # Positive: WA authors boost score
    for name, weight in get_wa_authors():
        if name in text:
            score += weight
    
    # Negative: EA authors reduce score (for future implementation)
    for name, weight in _EAST_ARMENIAN_AUTHORS:
        if name in text:
            score += weight  # weight is already negative

    # 5. Publication cities
    for city, weight in _WA_PUBLICATION_CITIES:
        if city in text:
            score += weight

    return score


def is_western_armenian(text: str, threshold: float = None) -> bool:
    """Return True for texts that surpass the WA score threshold."""
    if threshold is None:
        threshold = get_wa_score_threshold()
    return compute_wa_score(text) >= threshold


# NOTE: `is_western_armenian` removed — use the canonical classifier instead.
# This file retains scoring utilities (e.g. `compute_wa_score`) for compatibility
# and migration, but callers should route through the central classifier that
# emits standardized branch identifiers (e.g. `hye-w`, `hye-e`).


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
    is_wa = wa_score >= get_wa_score_threshold()
    text_dialect = "western" if is_wa else "eastern" if wa_score < 0 else "unknown"
    confidence = min(abs(wa_score) / 10.0, 1.0)  # Normalize to 0-1
    
    # Check for dialect mismatch with author
    dialect_mismatch = False
    recommendation = "ACCEPT"
    
    if author_record and author_record.dialect is not None:
        author_dialect = author_record.dialect.value
        if is_wa and author_record.dialect == Dialect.EASTERN:
            # EA author writing Western Armenian → potential issue
            dialect_mismatch = True
            recommendation = "FLAG" if confidence < 0.8 else "ACCEPT"
        elif not is_wa and author_record.dialect == Dialect.WESTERN:
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
    *,
    workers: int | None = None,
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
    workers:
        Thread-pool size for parallel read/classify/write.

    Returns
    -------
    tuple[int, int]
        ``(total, kept)``.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(input_dir.rglob("*.txt"))
    total = len(files)
    workers = workers or _DEFAULT_WORKERS

    logger.info(
        "Filtering %d files (%d workers): require_western=%s, min_chars=%d → %s",
        total, workers, require_western, min_chars, output_dir,
    )

    # Pre-create subdirectories so threads don't race on mkdir
    subdirs = {(output_dir / f.relative_to(input_dir)).parent for f in files}
    for d in subdirs:
        d.mkdir(parents=True, exist_ok=True)

    import threading
    kept_count = [0]
    _lock = threading.Lock()
    skipped_short = [0]
    skipped_non_arm = [0]
    skipped_non_wa = [0]
    bilingual_splits = [0]
    lines_cleaned = [0]
    file_stats: list[dict] = []

    def _process(txt_file: Path) -> bool:
        """Read, extract Armenian content, classify, and write one file."""
        text = txt_file.read_text(encoding="utf-8")
        rel = str(txt_file.relative_to(input_dir))
        raw_len = len(text)
        raw_chars = _classify_characters(text)
        raw_arm_ratio = (
            (raw_chars["armenian_letters"] + raw_chars["armenian_punct"])
            / max(sum(raw_chars.values()), 1)
        )

        # Build stat record (filled progressively)
        stat: dict = {
            "file": rel,
            "raw_chars": raw_len,
            "raw_armenian_ratio": round(raw_arm_ratio, 4),
            "raw_latin_ratio": round(raw_chars["latin"] / max(sum(raw_chars.values()), 1), 4),
            "raw_char_counts": raw_chars,
        }

        if raw_len < min_chars:
            stat.update(outcome="short", cleaned_chars=0, wa_score=0.0)
            with _lock:
                skipped_short[0] += 1
                file_stats.append(stat)
            return False

        # Extract Armenian content (handles bilingual splits + line filtering)
        cleaned = extract_armenian_content(text, min_chars=min_chars)
        if cleaned is None:
            stat.update(outcome="non_armenian", cleaned_chars=0, wa_score=0.0)
            with _lock:
                skipped_non_arm[0] += 1
                file_stats.append(stat)
            return False

        cleaned_len = len(cleaned)
        cleaned_chars = _classify_characters(cleaned)
        cleaned_arm_ratio = (
            (cleaned_chars["armenian_letters"] + cleaned_chars["armenian_punct"])
            / max(sum(cleaned_chars.values()), 1)
        )
        extraction_ratio = cleaned_len / max(raw_len, 1)

        stat.update(
            cleaned_chars=cleaned_len,
            cleaned_armenian_ratio=round(cleaned_arm_ratio, 4),
            extraction_ratio=round(extraction_ratio, 4),
        )

        # Track if extraction actually changed the text
        if cleaned_len < raw_len * 0.95:
            with _lock:
                if cleaned_len < raw_len * 0.6:
                    bilingual_splits[0] += 1  # major split detected
                    stat["extraction_type"] = "bilingual_split"
                else:
                    lines_cleaned[0] += 1  # minor line removal
                    stat["extraction_type"] = "line_removal"
        else:
            stat["extraction_type"] = "none"

        wa_score = compute_wa_score(cleaned)
        stat["wa_score"] = round(wa_score, 2)

        if require_western and wa_score < get_wa_score_threshold():
            stat["outcome"] = "non_western"
            with _lock:
                skipped_non_wa[0] += 1
                file_stats.append(stat)
            return False

        stat["outcome"] = "kept"
        out = output_dir / rel
        out.write_text(cleaned, encoding="utf-8")
        with _lock:
            kept_count[0] += 1
            file_stats.append(stat)
        return True

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_process, f): f for f in files}
        bar = tqdm(as_completed(futures), total=total, desc="WA filter", unit="file")
        for fut in bar:
            fut.result()  # raises on error
            bar.set_postfix(
                kept=kept_count[0],
                short=skipped_short[0],
                non_arm=skipped_non_arm[0],
                non_wa=skipped_non_wa[0],
                splits=bilingual_splits[0],
                cleaned=lines_cleaned[0],
            )

    kept = kept_count[0]
    logger.info(
        "Language filter complete: %d / %d kept (%.1f%%) | "
        "skipped: %d short, %d non-Armenian, %d non-WA | "
        "cleaned: %d bilingual splits, %d line removals",
        kept, total, 100.0 * kept / total if total else 0,
        skipped_short[0], skipped_non_arm[0], skipped_non_wa[0],
        bilingual_splits[0], lines_cleaned[0],
    )

    # ── Write per-file stats JSONL for EDA ────────────────────────────
    stats_dir = output_dir.parent / "logs"
    stats_dir.mkdir(parents=True, exist_ok=True)
    stats_path = stats_dir / "filter_stats.jsonl"
    with open(stats_path, "w", encoding="utf-8") as fh:
        for s in file_stats:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    logger.info("Per-file statistics written → %s (%d records)", stats_path, len(file_stats))

    # ── Aggregate summary ─────────────────────────────────────────────
    if file_stats:
        arm_ratios = [s["raw_armenian_ratio"] for s in file_stats]
        wa_scores = [s["wa_score"] for s in file_stats if s.get("wa_score")]
        raw_sizes = [s["raw_chars"] for s in file_stats]

        def _percentiles(vals: list[float]) -> dict:
            sv = sorted(vals)
            n = len(sv)
            return {
                "min": sv[0],
                "p25": sv[n // 4],
                "median": sv[n // 2],
                "p75": sv[3 * n // 4],
                "max": sv[-1],
                "mean": round(sum(sv) / n, 4),
            }

        summary = {
            "total": total,
            "kept": kept,
            "skipped_short": skipped_short[0],
            "skipped_non_armenian": skipped_non_arm[0],
            "skipped_non_western": skipped_non_wa[0],
            "bilingual_splits": bilingual_splits[0],
            "lines_cleaned": lines_cleaned[0],
            "raw_armenian_ratio": _percentiles(arm_ratios),
            "wa_score": _percentiles(wa_scores) if wa_scores else {},
            "raw_doc_size_chars": _percentiles(raw_sizes),
        }
        summary_path = stats_dir / "filter_summary.json"
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Aggregate summary written → %s", summary_path)
        logger.info(
            "  Armenian ratio: min=%.2f  p25=%.2f  median=%.2f  p75=%.2f  max=%.2f",
            summary["raw_armenian_ratio"]["min"],
            summary["raw_armenian_ratio"]["p25"],
            summary["raw_armenian_ratio"]["median"],
            summary["raw_armenian_ratio"]["p75"],
            summary["raw_armenian_ratio"]["max"],
        )
        if wa_scores:
            logger.info(
                "  WA score:       min=%.1f  p25=%.1f  median=%.1f  p75=%.1f  max=%.1f",
                summary["wa_score"]["min"],
                summary["wa_score"]["p25"],
                summary["wa_score"]["median"],
                summary["wa_score"]["p75"],
                summary["wa_score"]["max"],
            )
        logger.info(
            "  Doc size:       min=%d  median=%d  max=%d",
            summary["raw_doc_size_chars"]["min"],
            summary["raw_doc_size_chars"]["median"],
            summary["raw_doc_size_chars"]["max"],
        )

    return total, kept


def run(config: dict | None = None) -> None:
    """Entry-point: filter the deduplicated corpus to Western Armenian only."""
    cfg = config or _load_config()
    paths = cfg["paths"]
    dedup_dir = Path(paths["cleaned_dir"]).parent / "deduped"
    filtered_dir = Path(paths.get("filtered_dir", str(Path(paths["cleaned_dir"]).parent / "filtered")))
    min_chars: int = cfg["cleaning"]["min_chars_per_doc"]

    filter_directory(dedup_dir, filtered_dir, require_western=True, min_chars=min_chars)


# ── Segment-level dialect analysis ───────────────────────────────────────────

# EA/WA suffix regex constants are sourced from helpers (_REFORMED_SUFFIX_RE, _CLASSICAL_SUFFIX_RE).


class SegmentTag:
    """Classification result for a single text segment."""

    __slots__ = ("text", "dialect", "wa_score", "reformed_count", "classical_count")

    def __init__(
        self,
        text: str,
        dialect: str,
        wa_score: float,
        reformed_count: int = 0,
        classical_count: int = 0,
    ) -> None:
        self.text = text
        self.dialect = dialect          # "western", "eastern", "ambiguous", "non-armenian"
        self.wa_score = wa_score
        self.reformed_count = reformed_count
        self.classical_count = classical_count

    def __repr__(self) -> str:
        preview = self.text[:60].replace("\n", " ")
        return f"SegmentTag({self.dialect!r}, wa={self.wa_score:.1f}, '{preview}…')"


def _classify_segment(
    text: str,
    wa_threshold: float = 3.0,
    ea_threshold: float = -1.0,
) -> SegmentTag:
    """Classify a single text segment (paragraph) as WA, EA, or ambiguous.

    For shorter segments the WA scoring function returns fewer points (fewer
    marker hits), so we use a *lower* threshold than document-level.

    Parameters
    ----------
    text:
        The segment text (typically one paragraph).
    wa_threshold:
        Minimum ``compute_wa_score`` for the segment to count as **western**.
        Lower than document-level because individual paragraphs have fewer
        markers.
    ea_threshold:
        Score at or below which the segment is classified as **eastern**.
        Scores between *ea_threshold* and *wa_threshold* are **ambiguous**.
    """
    if not _has_armenian_script(text, threshold=0.15):
        return SegmentTag(text, "non-armenian", 0.0)

    score = compute_wa_score(text)
    reformed = len(_REFORMED_SUFFIX_RE.findall(text))
    classical = len(_CLASSICAL_SUFFIX_RE.findall(text))

    # Strong reformed signal overrides WA score — Soviet-era spelling is a
    # definitive EA marker regardless of how many WA lexical items appear.
    if reformed >= 3 and classical == 0:
        dialect = "eastern"
    elif classical > 0 and reformed / classical > 1.5:
        dialect = "eastern"
    elif score >= wa_threshold:
        dialect = "western"
    elif score <= ea_threshold:
        dialect = "eastern"
    else:
        dialect = "ambiguous"

    return SegmentTag(text, dialect, score, reformed, classical)


def tag_segments(
    text: str,
    min_segment_len: int = 60,
    wa_threshold: float = 3.0,
    ea_threshold: float = -1.0,
) -> list[SegmentTag]:
    """Split *text* into paragraphs and classify each one.

    Parameters
    ----------
    text:
        Full document text.
    min_segment_len:
        Paragraphs shorter than this are merged into the previous segment or
        dropped to avoid noisy classifications on very short strings.
    wa_threshold:
        Paragraph-level WA threshold (lower than document-level).
    ea_threshold:
        Paragraph-level EA threshold.

    Returns
    -------
    list[SegmentTag]
        One tag per qualifying paragraph, in document order.
    """
    raw_paragraphs = re.split(r"\n\s*\n", text)
    paragraphs = [p.strip() for p in raw_paragraphs if len(p.strip()) >= min_segment_len]

    return [
        _classify_segment(p, wa_threshold=wa_threshold, ea_threshold=ea_threshold)
        for p in paragraphs
    ]


def extract_western_segments(
    text: str,
    min_segment_len: int = 60,
    wa_threshold: float = 3.0,
    ea_threshold: float = -1.0,
    include_ambiguous: bool = False,
) -> str:
    """Return only the Western Armenian portions of *text*.

    Splits the document into paragraphs, tags each, and reassembles only the
    paragraphs classified as ``"western"`` (and optionally ``"ambiguous"``).

    Parameters
    ----------
    include_ambiguous:
        If True, paragraphs scored between *ea_threshold* and *wa_threshold*
        are kept.  If False (default), only clear WA paragraphs are kept.

    Returns
    -------
    str
        Filtered text with only WA paragraphs, joined by double newlines.
    """
    tags = tag_segments(text, min_segment_len, wa_threshold, ea_threshold)
    keep_dialects = {"western"}
    if include_ambiguous:
        keep_dialects.add("ambiguous")
    kept = [t.text for t in tags if t.dialect in keep_dialects]
    return "\n\n".join(kept)


class DocumentDialectReport:
    """Summary of paragraph-level dialect distribution for a document."""

    __slots__ = (
        "total_segments", "western_count", "eastern_count",
        "ambiguous_count", "non_armenian_count",
        "western_chars", "eastern_chars", "total_chars",
        "is_mixed", "eastern_ratio",
        "segment_tags",
    )

    def __init__(self, tags: list[SegmentTag]) -> None:
        self.segment_tags = tags
        self.total_segments = len(tags)
        self.western_count = sum(1 for t in tags if t.dialect == "western")
        self.eastern_count = sum(1 for t in tags if t.dialect == "eastern")
        self.ambiguous_count = sum(1 for t in tags if t.dialect == "ambiguous")
        self.non_armenian_count = sum(1 for t in tags if t.dialect == "non-armenian")

        self.western_chars = sum(len(t.text) for t in tags if t.dialect == "western")
        self.eastern_chars = sum(len(t.text) for t in tags if t.dialect == "eastern")
        self.total_chars = sum(len(t.text) for t in tags)

        arm_segments = self.western_count + self.eastern_count + self.ambiguous_count
        self.eastern_ratio = (
            self.eastern_count / arm_segments if arm_segments > 0 else 0.0
        )
        self.is_mixed = self.western_count > 0 and self.eastern_count > 0

    def summary_line(self) -> str:
        return (
            f"segments={self.total_segments} "
            f"WA={self.western_count} EA={self.eastern_count} "
            f"ambig={self.ambiguous_count} non_arm={self.non_armenian_count} "
            f"ea_ratio={self.eastern_ratio:.1%} mixed={self.is_mixed}"
        )


def analyse_document(
    text: str,
    min_segment_len: int = 60,
    wa_threshold: float = 3.0,
    ea_threshold: float = -1.0,
) -> DocumentDialectReport:
    """Produce a full paragraph-level dialect report for *text*."""
    tags = tag_segments(text, min_segment_len, wa_threshold, ea_threshold)
    return DocumentDialectReport(tags)


def _load_config() -> dict:
    with open(_SETTINGS_PATH) as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()