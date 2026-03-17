"""Bilingual document detection and splitting for Armenian text.

Detects multilingual documents (Armenian + another language), splits them
into separate per-language content, and provides a linking ID so the pair
can be used for future translation model training.

Typical sources of bilingual documents:
- Diaspora newspapers (Armenian / English / French / Turkish)
- Parallel translations on Archive.org or Gallica
- OCR output that mixes headers or footnotes in a different language
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Armenian-specific punctuation (not shared with Latin scripts).
_ARMENIAN_PUNCT = frozenset("\u0589\u055D\u055E\u055C\u055A\u058A\u00AB\u00BB")


# ─────────────────────────────────────────────────────────────────────────────
#  Character classification
# ─────────────────────────────────────────────────────────────────────────────

def _classify_characters(text: str) -> dict[str, int]:
    """Classify non-whitespace characters in *text* into script categories."""
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


def _armenian_ratio(text: str) -> float:
    """Fraction of non-whitespace chars that are Armenian (letters + punct)."""
    counts = _classify_characters(text)
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return (counts["armenian_letters"] + counts["armenian_punct"]) / total


def _latin_ratio(text: str) -> float:
    """Fraction of non-whitespace chars that are Latin letters."""
    counts = _classify_characters(text)
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return counts["latin"] / total


def _line_is_armenian(line: str, threshold: float = 0.5) -> bool:
    """True if *line* is predominantly Armenian.  Blank lines are neutral."""
    stripped = line.strip()
    if not stripped:
        return True
    return _armenian_ratio(stripped) >= threshold


# ─────────────────────────────────────────────────────────────────────────────
#  Result dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BilingualSplitResult:
    """Result of splitting a bilingual document."""

    is_bilingual: bool
    """True if the document was determined to contain two languages."""

    armenian_text: str | None = None
    """Extracted Armenian content (or None if not enough remained)."""

    other_text: str | None = None
    """Extracted non-Armenian content (or None if not bilingual)."""

    split_method: str = "none"
    """How the split was performed: 'half_split', 'line_filter', or 'none'."""

    armenian_ratio: float = 0.0
    """Armenian character ratio of the *original* document."""

    linking_id: str = ""
    """Deterministic ID linking the Armenian and non-Armenian halves."""

    stats: dict = field(default_factory=dict)
    """Extra stats: original_chars, armenian_chars, other_chars, etc."""


# ─────────────────────────────────────────────────────────────────────────────
#  Core splitter
# ─────────────────────────────────────────────────────────────────────────────

_STRONG_ARM = 0.50
_WEAK_ARM = 0.20


def _linking_id(text: str) -> str:
    """Deterministic ID from a SHA-256 prefix of the original text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def split_bilingual(text: str, *, min_chars: int = 100) -> BilingualSplitResult:
    """Detect and split a bilingual Armenian document.

    Strategy (applied in order):

    1. **Half-split detection** — many diaspora documents are parallel
       translations: one half Armenian, one half English/French/Turkish.
       Split at the midpoint and check each half independently.
    2. **Line-level filtering** — remove individual non-Armenian lines
       (English headers, Latin paragraphs).
    3. **Final validation** — reject if the Armenian portion is too short
       or still too mixed.

    Parameters
    ----------
    text
        Raw document text.
    min_chars
        Minimum character count for each extracted half.

    Returns
    -------
    BilingualSplitResult
    """
    overall_ratio = _armenian_ratio(text)
    lid = _linking_id(text)

    lines = text.splitlines()
    if not lines:
        return BilingualSplitResult(
            is_bilingual=False, armenian_ratio=overall_ratio, linking_id=lid,
        )

    # ── Phase 1: half-split ──────────────────────────────────────────
    mid = len(lines) // 2
    first_half = "\n".join(lines[:mid])
    second_half = "\n".join(lines[mid:])
    r_first = _armenian_ratio(first_half)
    r_second = _armenian_ratio(second_half)

    arm_text: str | None = None
    other_text: str | None = None
    method = "none"

    if r_first >= _STRONG_ARM and r_second < _WEAK_ARM:
        arm_text = first_half.strip()
        other_text = second_half.strip()
        method = "half_split"
    elif r_second >= _STRONG_ARM and r_first < _WEAK_ARM:
        arm_text = second_half.strip()
        other_text = first_half.strip()
        method = "half_split"

    if method == "half_split":
        # Only bilingual if BOTH halves have meaningful content
        has_arm = arm_text and len(arm_text) >= min_chars and _armenian_ratio(arm_text) >= 0.35
        has_other = other_text and len(other_text) >= min_chars
        if has_arm and has_other:
            return BilingualSplitResult(
                is_bilingual=True,
                armenian_text=arm_text,
                other_text=other_text,
                split_method=method,
                armenian_ratio=overall_ratio,
                linking_id=lid,
                stats={
                    "original_chars": len(text),
                    "armenian_chars": len(arm_text or ""),
                    "other_chars": len(other_text or ""),
                },
            )
        if has_arm:
            # One half Armenian, other half empty/too short → not bilingual
            return BilingualSplitResult(
                is_bilingual=False,
                armenian_text=arm_text,
                split_method=method,
                armenian_ratio=overall_ratio,
                linking_id=lid,
                stats={"original_chars": len(text), "armenian_chars": len(arm_text or "")},
            )
        # half-split didn't yield enough Armenian; fall through

    # ── Phase 2: line-level filtering ────────────────────────────────
    arm_lines: list[str] = []
    other_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            arm_lines.append(line)
            other_lines.append(line)
        elif _line_is_armenian(line):
            arm_lines.append(line)
        else:
            other_lines.append(line)

    # Trim trailing blanks
    while arm_lines and not arm_lines[-1].strip():
        arm_lines.pop()
    while other_lines and not other_lines[-1].strip():
        other_lines.pop()

    arm_result = "\n".join(arm_lines).strip()
    other_result = "\n".join(other_lines).strip()

    # Decide if this is genuinely bilingual
    has_arm = len(arm_result) >= min_chars and _armenian_ratio(arm_result) >= 0.35
    has_other = len(other_result) >= min_chars and _latin_ratio(other_result) >= 0.30

    if has_arm and has_other:
        return BilingualSplitResult(
            is_bilingual=True,
            armenian_text=arm_result,
            other_text=other_result,
            split_method="line_filter",
            armenian_ratio=overall_ratio,
            linking_id=lid,
            stats={
                "original_chars": len(text),
                "armenian_chars": len(arm_result),
                "other_chars": len(other_result),
            },
        )

    if has_arm:
        return BilingualSplitResult(
            is_bilingual=False,
            armenian_text=arm_result,
            split_method="line_filter" if arm_result != text.strip() else "none",
            armenian_ratio=overall_ratio,
            linking_id=lid,
            stats={"original_chars": len(text), "armenian_chars": len(arm_result)},
        )

    # Not enough Armenian content
    return BilingualSplitResult(
        is_bilingual=False,
        armenian_ratio=overall_ratio,
        linking_id=lid,
        stats={"original_chars": len(text)},
    )


def extract_armenian_content(text: str, *, min_chars: int = 100) -> str | None:
    """Convenience wrapper: return only the Armenian text, or None."""
    result = split_bilingual(text, min_chars=min_chars)
    return result.armenian_text
