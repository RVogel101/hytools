"""Rule-based Eastern/Western Armenian classifier.

IMPORTANT:
- This classifier uses only project-internal documented rules.
- It intentionally returns "inconclusive" when no documented marker appears.
- It does not use statistical guesses or external linguistic assumptions.

Primary sources used for rules:
- 01-docs/references/CLASSICAL_ORTHOGRAPHY_GUIDE.md
- 01-docs/references/ARMENIAN_QUICK_REFERENCE.md
- 02-src/lousardzag/morphology/articles.py
- 02-src/lousardzag/morphology/verbs.py
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import re
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class DialectRule:
    """Single evidence rule used by the classifier."""

    rule_id: str
    dialect: str  # "western" or "eastern"
    weight: float
    pattern: str
    source: str
    note: str


@dataclass
class EvidenceHit:
    """One matched rule occurrence in input text."""

    rule_id: str
    dialect: str
    weight: float
    matched_text: str
    source: str
    note: str


@dataclass
class DialectClassification:
    """Classifier output for one text item."""

    text: str
    label: str
    confidence: float
    western_score: float
    eastern_score: float
    evidence: List[EvidenceHit]

    def to_dict(self) -> dict:
        """Serialize classification result to plain dict."""
        return {
            "text": self.text,
            "label": self.label,
            "confidence": self.confidence,
            "western_score": self.western_score,
            "eastern_score": self.eastern_score,
            "evidence": [asdict(hit) for hit in self.evidence],
        }


# NOTE: All rule content below is copied from internal docs/code references only.
_RULES: List[DialectRule] = [
    # Western markers
    DialectRule(
        rule_id="WA_CLASSICAL_IYWN_DIGRAPH",
        dialect="western",
        weight=3.0,
        pattern=r"իւ",
        source="01-docs/references/CLASSICAL_ORTHOGRAPHY_GUIDE.md",
        note="Classical orthography keeps 'իւ' distinct from reformed 'յու'/'ու'.",
    ),
    DialectRule(
        rule_id="WA_INDEF_ARTICLE_MEH",
        dialect="western",
        weight=2.5,
        pattern=r"(^|\s)մը($|\s|[\.,;:!?])",
        source="02-src/lousardzag/morphology/articles.py",
        note="Western Armenian indefinite article is postposed 'մը'.",
    ),
    DialectRule(
        rule_id="WA_PRESENT_PARTICLE_GUH",
        dialect="western",
        weight=2.5,
        pattern=r"(^|\s)կը($|\s|[\.,;:!?])",
        source="02-src/lousardzag/morphology/verbs.py",
        note="Western present tense preverbal particle 'կը'.",
    ),
    DialectRule(
        rule_id="WA_FUTURE_PARTICLE_BIDI",
        dialect="western",
        weight=2.5,
        pattern=r"(^|\s)պիտի($|\s|[\.,;:!?])",
        source="02-src/lousardzag/morphology/verbs.py",
        note="Western future preverbal particle 'պիտի'.",
    ),
    DialectRule(
        rule_id="WA_NEG_PARTICLE_CHEH",
        dialect="western",
        weight=2.0,
        pattern=r"(^|\s)չը($|\s|[\.,;:!?])",
        source="02-src/lousardzag/morphology/verbs.py",
        note="Western negative particle documented as 'չը'.",
    ),
    # Eastern/reformed markers (explicitly listed as non-classical in internal docs)
    DialectRule(
        rule_id="EA_REFORMED_YUGH",
        dialect="eastern",
        weight=3.0,
        pattern=r"(^|\s)յուղ($|\s|[\.,;:!?])",
        source="01-docs/references/CLASSICAL_ORTHOGRAPHY_GUIDE.md",
        note="Guide marks 'յուղ' as reformed spelling where classical is 'իւղ'.",
    ),
    DialectRule(
        rule_id="EA_REFORMED_GYUGH",
        dialect="eastern",
        weight=3.0,
        pattern=r"(^|\s)գյուղ($|\s|[\.,;:!?])",
        source="01-docs/references/CLASSICAL_ORTHOGRAPHY_GUIDE.md",
        note="Guide marks 'գյուղ' as reformed spelling where classical is 'գիւղ'.",
    ),
    DialectRule(
        rule_id="EA_REFORMED_CHYUGH",
        dialect="eastern",
        weight=3.0,
        pattern=r"(^|\s)ճյուղ($|\s|[\.,;:!?])",
        source="01-docs/references/CLASSICAL_ORTHOGRAPHY_GUIDE.md",
        note="Guide marks 'ճյուղ' as reformed spelling where classical is 'ճիւղ'.",
    ),
    DialectRule(
        rule_id="EA_REFORMED_ZAMBYUGH",
        dialect="eastern",
        weight=3.0,
        pattern=r"(^|\s)զամբյուղ($|\s|[\.,;:!?])",
        source="01-docs/references/CLASSICAL_ORTHOGRAPHY_GUIDE.md",
        note="Guide marks 'զամբյուղ' as reformed spelling where classical is 'զամբիւղ'.",
    ),
    DialectRule(
        rule_id="EA_REFORMED_URACHYUR",
        dialect="eastern",
        weight=3.0,
        pattern=r"(^|\s)ուրաքանչյուր($|\s|[\.,;:!?])",
        source="01-docs/references/CLASSICAL_ORTHOGRAPHY_GUIDE.md",
        note="Guide marks 'ուրաքանչյուր' as reformed spelling where classical is 'իւրաքանչիւր'.",
    ),
    # Internal quick-reference "wrong output" transliteration cues.
    DialectRule(
        rule_id="EA_TRANSLIT_PETIK",
        dialect="eastern",
        weight=2.0,
        pattern=r"\bpetik\b",
        source="01-docs/references/ARMENIAN_QUICK_REFERENCE.md",
        note="Quick reference lists 'petik' under Eastern/wrong output for WA target.",
    ),
    DialectRule(
        rule_id="EA_TRANSLIT_JAYUR",
        dialect="eastern",
        weight=2.0,
        pattern=r"\bjayur\b",
        source="01-docs/references/ARMENIAN_QUICK_REFERENCE.md",
        note="Quick reference lists 'jayur' under Eastern/wrong output for WA target.",
    ),
]


_COMPILED_RULES = [
    (rule, re.compile(rule.pattern, flags=re.IGNORECASE))
    for rule in _RULES
]


def _classify_scores(western_score: float, eastern_score: float) -> tuple[str, float]:
    """Convert score totals to label and confidence."""
    total = western_score + eastern_score
    if total == 0:
        return "inconclusive", 0.0

    if western_score == eastern_score:
        return "inconclusive", 0.5

    if western_score > eastern_score:
        confidence = round((western_score - eastern_score) / total, 3)
        return "likely_western", confidence

    confidence = round((eastern_score - western_score) / total, 3)
    return "likely_eastern", confidence


def classify_text_dialect(text: str) -> DialectClassification:
    """Classify a single word/phrase/sentence as likely Western or Eastern.

    This function is intentionally conservative:
    - It only uses documented markers from internal project sources.
    - It returns "inconclusive" when no marker is found.
    """
    normalized = (text or "").strip()

    western_score = 0.0
    eastern_score = 0.0
    evidence: List[EvidenceHit] = []

    for rule, pattern in _COMPILED_RULES:
        for match in pattern.finditer(normalized):
            matched_text = match.group(0)
            evidence.append(
                EvidenceHit(
                    rule_id=rule.rule_id,
                    dialect=rule.dialect,
                    weight=rule.weight,
                    matched_text=matched_text,
                    source=rule.source,
                    note=rule.note,
                )
            )
            if rule.dialect == "western":
                western_score += rule.weight
            else:
                eastern_score += rule.weight

    label, confidence = _classify_scores(western_score, eastern_score)

    return DialectClassification(
        text=normalized,
        label=label,
        confidence=confidence,
        western_score=round(western_score, 3),
        eastern_score=round(eastern_score, 3),
        evidence=evidence,
    )


def classify_batch_texts(texts: Iterable[str]) -> List[DialectClassification]:
    """Classify an iterable of text items."""
    return [classify_text_dialect(text) for text in texts]


def classify_vocab_and_sentences(
    vocab: Sequence[str],
    sentences: Sequence[str],
) -> dict:
    """Classify vocabulary and sentences in one call.

    Returns per-item results and aggregate counts.
    """
    vocab_results = classify_batch_texts(vocab)
    sentence_results = classify_batch_texts(sentences)

    all_results = vocab_results + sentence_results
    counts = {
        "likely_western": sum(1 for r in all_results if r.label == "likely_western"),
        "likely_eastern": sum(1 for r in all_results if r.label == "likely_eastern"),
        "inconclusive": sum(1 for r in all_results if r.label == "inconclusive"),
    }

    return {
        "vocab": [result.to_dict() for result in vocab_results],
        "sentences": [result.to_dict() for result in sentence_results],
        "summary": {
            "total_items": len(all_results),
            "counts": counts,
        },
    }


__all__ = [
    "DialectClassification",
    "classify_text_dialect",
    "classify_batch_texts",
    "classify_vocab_and_sentences",
]
