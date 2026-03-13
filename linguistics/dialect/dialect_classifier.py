"""Rule-based Eastern/Western Armenian classifier.

IMPORTANT:
- This classifier uses only project-internal documented rules.
- It intentionally returns "inconclusive" when no documented marker appears.
- It does not use statistical guesses or external linguistic assumptions.

Primary sources used for rules:
- Western Armenian morphology (articles, verb particles)
- Classical vs. reformed orthography markers
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import re
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class DialectRule:
    """Single evidence rule used by the classifier."""

    rule_id: str
    dialect: str  # "western", "eastern", or "classical"
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
    classical_score: float
    evidence: List[EvidenceHit]

    def to_dict(self) -> dict:
        """Serialize classification result to plain dict."""
        return {
            "text": self.text,
            "label": self.label,
            "confidence": self.confidence,
            "western_score": self.western_score,
            "eastern_score": self.eastern_score,
            "classical_score": self.classical_score,
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
        source="morphology/articles",
        note="Western Armenian indefinite article is postposed 'մը'.",
    ),
    DialectRule(
        rule_id="WA_PRESENT_PARTICLE_GUH",
        dialect="western",
        weight=2.5,
        pattern=r"(^|\s)կը($|\s|[\.,;:!?])",
        source="morphology/verbs",
        note="Western present tense preverbal particle 'կը'.",
    ),
    DialectRule(
        rule_id="WA_FUTURE_PARTICLE_BIDI",
        dialect="western",
        weight=2.5,
        pattern=r"(^|\s)պիտի($|\s|[\.,;:!?])",
        source="morphology/verbs",
        note="Western future preverbal particle 'պիտի'.",
    ),
    DialectRule(
        rule_id="WA_NEG_PARTICLE_CHEH",
        dialect="western",
        weight=2.0,
        pattern=r"(^|\s)չը($|\s|[\.,;:!?])",
        source="morphology/verbs",
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
    # EA indefinite article: մի (mi) BEFORE noun
    DialectRule(
        rule_id="EA_INDEF_ARTICLE_MI",
        dialect="eastern",
        weight=2.5,
        pattern=r"\u0574\u056b\s",  # մի + space
        source="WA_EA_LINGUISTIC_DISTINCTIONS.md",
        note="Eastern Armenian indefinite article 'մի' appears before the noun.",
    ),
    # EA vocabulary: egg
    DialectRule(
        rule_id="EA_VOCAB_DZU",
        dialect="eastern",
        weight=2.5,
        pattern=r"\u0571\u0578\u0582",  # ձու (dzu, egg)
        source="WA_EA_LINGUISTIC_DISTINCTIONS.md",
        note="Eastern Armenian 'ձու' (egg); Western uses հավկիթ.",
    ),
    # WA vocabulary: egg
    DialectRule(
        rule_id="WA_VOCAB_HAVKIT",
        dialect="western",
        weight=2.5,
        pattern=r"\u0570\u0561\u057e\u056f\u056b\u0569",  # հավկիթ (egg)
        source="WA_EA_LINGUISTIC_DISTINCTIONS.md",
        note="Western Armenian 'հավկիթ' (egg); Eastern uses ձու.",
    ),
    # Classical Armenian (Grabar) markers — see docs/CLASSICAL_ARMENIAN_IDENTIFICATION.md
    DialectRule(
        rule_id="CL_ACCUSATIVE_Z",
        dialect="classical",
        weight=2.0,
        pattern=r"\u0566[\u0531-\u058F]",  # զ + letter (definite accusative prefix)
        source="CLASSICAL_ARMENIAN_IDENTIFICATION.md",
        note="Grabar definite accusative prefix զ-.",
    ),
    DialectRule(
        rule_id="CL_LITURGICAL_TER",
        dialect="classical",
        weight=3.0,
        pattern=r"\u054f\u0567\u0580\s\u0578\u0572\u0580\u0574\u0575\u0561",  # Տէր ողորմյա
        source="CLASSICAL_ARMENIAN_IDENTIFICATION.md",
        note="Liturgical phrase 'Lord have mercy'.",
    ),
    DialectRule(
        rule_id="CL_ARCHAIC_VERB_EAL",
        dialect="classical",
        weight=1.5,
        pattern=r"\u0565\u0561\u056C\b",  # -եալ (archaic participle)
        source="CLASSICAL_ARMENIAN_IDENTIFICATION.md",
        note="Archaic verb participle ending -եալ.",
    ),
]


_COMPILED_RULES = [
    (rule, re.compile(rule.pattern, flags=re.IGNORECASE))
    for rule in _RULES
]


def _classify_scores(
    western_score: float, eastern_score: float, classical_score: float
) -> tuple[str, float]:
    """Convert score totals to label and confidence. Classical wins if it dominates."""
    total = western_score + eastern_score + classical_score
    if total == 0:
        return "inconclusive", 0.0

    # Classical (Grabar): require at least 3.0 and higher than both WA and EA
    if classical_score >= 3.0 and classical_score >= western_score and classical_score >= eastern_score:
        confidence = round(classical_score / total, 3)
        return "likely_classical", min(confidence, 0.99)

    total_modern = western_score + eastern_score
    if total_modern == 0:
        return "inconclusive", 0.5

    if western_score == eastern_score:
        return "inconclusive", 0.5

    if western_score > eastern_score:
        confidence = round((western_score - eastern_score) / total_modern, 3)
        return "likely_western", confidence

    confidence = round((eastern_score - western_score) / total_modern, 3)
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
    classical_score = 0.0
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
            elif rule.dialect == "eastern":
                eastern_score += rule.weight
            else:
                classical_score += rule.weight

    label, confidence = _classify_scores(western_score, eastern_score, classical_score)

    return DialectClassification(
        text=normalized,
        label=label,
        confidence=confidence,
        western_score=round(western_score, 3),
        eastern_score=round(eastern_score, 3),
        classical_score=round(classical_score, 3),
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
        "likely_classical": sum(1 for r in all_results if r.label == "likely_classical"),
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
