"""Canonical insert-time schema for all corpus scrapers.

Every scraper builds a ``ScrapedDocument`` before calling
``insert_or_skip()``.  This bridges the gap between raw scrape output
and the ``core_contracts.DocumentRecord`` contract.

Standard quantitative linguistic metrics are auto-computed by
``compute_standard_linguistics()`` (called automatically in
``insert_or_skip``).  All classification tag fields are present on
every document — scrapers set what they know, the rest stay ``None``.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Known ISO 639-3 / internal language codes accepted by the corpus.
KNOWN_SOURCE_LANGUAGE_CODES = frozenset({"hyw", "hye", "hy", "xcl", "en"})
KNOWN_INTERNAL_LANGUAGE_CODES = frozenset({"hy", "eng"})
KNOWN_INTERNAL_LANGUAGE_BRANCHES = frozenset({"hye-w", "hye-e", "eng"})

# Known dialect labels emitted by the branch_dialect_classifier.
KNOWN_DIALECT_LABELS = frozenset({
    "likely_western", "likely_eastern", "likely_classical", "inconclusive",
})

# Known top-level dialect tags (from metadata.Dialect enum).
KNOWN_DIALECTS = frozenset({
    "western_armenian", "eastern_armenian", "classical_armenian", "mixed", "unknown",
})

# Known source types (from metadata.SourceType enum).
KNOWN_SOURCE_TYPES = frozenset({
    "encyclopedia", "literature", "newspaper", "news_agency", "blog",
    "social_media", "archive", "library", "academic", "historical_collection",
    "website",
})

# Known content types (from metadata.ContentType enum).
KNOWN_CONTENT_TYPES = frozenset({
    "article", "literature", "academic", "transcription", "legal",
    "poem", "prose", "historical", "religious", "mixed",
})

# Known writing categories (from metadata.WritingCategory enum).
KNOWN_WRITING_CATEGORIES = frozenset({
    "book", "manuscript", "scientific_paper", "liturgical", "fiction",
    "non_fiction", "history", "politics", "news", "academic",
    "literature", "article", "unknown",
})

# Armenian sentence-end delimiters.
_SENTENCE_RE = re.compile(r"[։?!:]+")

# Armenian Unicode letter range.
_ARMENIAN_LETTER_RE = re.compile(r"[\u0531-\u0587]")


@dataclass
class ScrapedDocument:
    """Canonical schema that every scraper must produce before insert.

    Fields are grouped into *required*, *identity*, *language*,
    *provenance*, *classification tags*, *quantitative linguistics*,
    and *extensible metadata*.  Every field that ANY document could
    carry is declared here so the schema is uniform across all sources.
    """

    # ── Required ──────────────────────────────────────────────────
    source_family: str          # e.g. "archive_org", "agos", "wiki"
    text: str                   # full text content

    # ── Identity ──────────────────────────────────────────────────
    title: Optional[str] = None
    source_url: Optional[str] = None
    author: Optional[str] = None
    author_origin: Optional[str] = None   # author's geographic origin
    content_hash: Optional[str] = None    # computed by insert helper if None

    # ── Language classification ────────────────────────────────────
    source_language_code: Optional[str] = None     # ISO 639-3 (hyw/hye/en)
    internal_language_code: Optional[str] = None   # computed: hy / eng
    internal_language_branch: Optional[str] = None # computed: hye-w / hye-e
    wa_score: Optional[float] = None               # WA confidence [0, 1]

    # ── Provenance ────────────────────────────────────────────────
    publication_date: Optional[str] = None   # ISO 8601 string
    original_date: Optional[str] = None      # historical document date (pre-extraction)
    extraction_date: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    catalog_id: Optional[str] = None         # archive.org ID, LCCN, HTID, ark, etc.
    source_name: Optional[str] = None        # human-readable source name
    collection: Optional[str] = None         # corpus collection name

    # ── Classification tags ───────────────────────────────────────
    source_type: Optional[str] = None         # e.g. "encyclopedia", "news"
    content_type: Optional[str] = None        # e.g. "article", "book"
    writing_category: Optional[str] = None    # e.g. "literature", "academic"
    dialect: Optional[str] = None             # "western_armenian", "eastern_armenian", etc.
    dialect_subcategory: Optional[str] = None # fine-grained region/register
    region: Optional[str] = None              # geographic origin
    confidence_region: Optional[float] = None # region assignment confidence [0, 1]

    # ── Dialect classification detail ─────────────────────────────
    dialect_label: Optional[str] = None       # "likely_western" / "likely_eastern" / …
    dialect_confidence: Optional[float] = None
    western_score: Optional[float] = None
    eastern_score: Optional[float] = None
    classical_score: Optional[float] = None

    # ── Quantitative linguistic metrics (auto-computed) ───────────
    #    Populated by ``compute_standard_linguistics()``.
    char_count: Optional[int] = None
    word_count: Optional[int] = None
    sentence_count: Optional[int] = None

    # Lexical diversity
    ttr: Optional[float] = None               # Type-Token Ratio
    sttr: Optional[float] = None              # Standardized TTR (100-word windows)
    yule_k: Optional[float] = None            # Yule's K (repetitiveness)
    unique_words: Optional[int] = None

    # Syntactic complexity
    avg_sentence_length: Optional[float] = None
    flesch_kincaid_grade: Optional[float] = None

    # Semantic
    entropy: Optional[float] = None           # Shannon entropy of word dist

    # Orthographic (classical vs reformed)
    classical_markers_count: Optional[int] = None
    reformed_markers_count: Optional[int] = None
    classical_to_reformed_ratio: Optional[float] = None

    # Contamination / dialect quality
    code_switching_index: Optional[float] = None   # EA verbal marker ratio [0, 1]
    dialect_purity_score: Optional[float] = None   # WA purity [0, 1]

    # ── Extensible metadata ───────────────────────────────────────
    extra: Dict[str, Any] = field(default_factory=dict)

    # ─── Serialisation ────────────────────────────────────────────

    def to_insert_dict(self) -> dict:
        """Convert to the dict shape expected by ``MongoDBCorpusClient.insert_document``.

        Returns a flat dict with ``source``, ``title``, ``text``,
        ``url``, ``author`` at the top level plus a ``metadata`` sub-dict
        that merges classification / provenance / linguistic fields with
        ``extra``.
        """
        metadata: Dict[str, Any] = dict(self.extra)

        # Promote all structured fields into the metadata sub-dict.
        _METADATA_KEYS = (
            # Language classification
            "source_language_code",
            "internal_language_code",
            "internal_language_branch",
            "wa_score",
            # Provenance
            "catalog_id",
            "source_name",
            "collection",
            "publication_date",
            "original_date",
            "extraction_date",
            # Classification tags
            "source_type",
            "content_type",
            "writing_category",
            "dialect",
            "dialect_subcategory",
            "region",
            "author_origin",
            "confidence_region",
            # Dialect classification detail
            "dialect_label",
            "dialect_confidence",
            "western_score",
            "eastern_score",
            "classical_score",
            # Quantitative linguistic metrics
            "char_count",
            "word_count",
            "sentence_count",
            "ttr",
            "sttr",
            "yule_k",
            "unique_words",
            "avg_sentence_length",
            "flesch_kincaid_grade",
            "entropy",
            "classical_markers_count",
            "reformed_markers_count",
            "classical_to_reformed_ratio",
            "code_switching_index",
            "dialect_purity_score",
        )
        for key in _METADATA_KEYS:
            val = getattr(self, key, None)
            if val is not None:
                metadata[key] = val

        return {
            "source": self.source_family,
            "title": self.title,
            "text": self.text,
            "url": self.source_url,
            "author": self.author,
            "metadata": metadata,
        }

    def to_document_record(self) -> "DocumentRecord":  # noqa: F821
        """Upcast to ``core_contracts.DocumentRecord``."""
        from hytools.core_contracts.types import DocumentRecord

        return DocumentRecord(
            document_id=self.content_hash or "",
            source_family=self.source_family,
            text=self.text,
            title=self.title,
            source_url=self.source_url,
            content_hash=self.content_hash,
            char_count=self.char_count or (len(self.text) if self.text else 0),
            internal_language_code=self.internal_language_code,
            internal_language_branch=self.internal_language_branch,
            metadata=self.extra,
        )

    # ─── Quantitative linguistic metrics ──────────────────────────

    def compute_standard_linguistics(self) -> None:
        """Populate quantitative linguistic metrics from ``self.text``.

        This fills basic counts, lexical diversity, syntactic complexity,
        semantic entropy, orthographic markers, contamination indices,
        and dialect classification from the branch dialect classifier.

        Called automatically by ``insert_or_skip()`` when the metrics
        are still ``None``.  Scrapers may also call it explicitly if
        they need the values earlier.
        """
        text = self.text or ""
        if not text.strip():
            return

        # ── Basic counts ──────────────────────────────────────────
        self.char_count = len(text)

        # Use Armenian-aware tokenizer if available; fall back to whitespace.
        words: List[str] = []
        try:
            from hytools.cleaning.armenian_tokenizer import extract_words
            words = extract_words(text, min_length=2)
        except ImportError:
            pass
        # If Armenian tokenizer returned nothing (e.g. non-Armenian text),
        # fall back to generic whitespace tokenisation so that metrics are
        # still computed for English-language documents.
        if not words:
            words = [w for w in text.split() if len(w) >= 2]
        self.word_count = len(words)

        sentences = [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]
        self.sentence_count = len(sentences)

        if not words:
            return

        # ── Lexical diversity ─────────────────────────────────────
        total = len(words)
        unique = len(set(words))
        self.unique_words = unique
        self.ttr = round(unique / total, 4) if total else 0.0
        self.sttr = self._compute_sttr(words)
        self.yule_k = self._compute_yule_k(words)

        # ── Syntactic complexity ──────────────────────────────────
        if sentences:
            self.avg_sentence_length = round(total / len(sentences), 2)
            avg_syl = self._estimate_avg_syllables(words)
            self.flesch_kincaid_grade = round(
                0.39 * (total / len(sentences)) + 11.8 * avg_syl - 15.59, 2,
            )

        # ── Semantic: Shannon entropy ─────────────────────────────
        freq = Counter(words)
        probs = [c / total for c in freq.values()]
        self.entropy = round(
            -sum(p * math.log2(p) for p in probs if p > 0), 4,
        )

        # ── Orthographic: classical vs reformed markers ───────────
        self._compute_orthographic_markers(text)

        # ── Contamination: code-switching index ───────────────────
        self._compute_contamination(words)

        # ── Dialect classification ────────────────────────────────
        self._compute_dialect_classification(text)

    # ── Helper: Standardized TTR ──────────────────────────────────

    @staticmethod
    def _compute_sttr(words: List[str], window: int = 100) -> float:
        if len(words) < window:
            return round(len(set(words)) / len(words), 4) if words else 0.0
        values = []
        for i in range(0, len(words) - window + 1, window):
            w = words[i : i + window]
            values.append(len(set(w)) / len(w))
        return round(sum(values) / len(values), 4) if values else 0.0

    # ── Helper: Yule's K ─────────────────────────────────────────

    @staticmethod
    def _compute_yule_k(words: List[str]) -> float:
        if not words:
            return 0.0
        freq = Counter(words)
        N = len(words)
        sum_f2 = sum(f * f for f in freq.values())
        denom = N * N
        if denom == 0:
            return 0.0
        return round(10_000 * (sum_f2 - N) / denom, 2)

    # ── Helper: average syllables per word ────────────────────────

    @staticmethod
    def _estimate_avg_syllables(words: List[str]) -> float:
        """Estimate average syllable count per word for Armenian text.

        Uses Armenian vowel characters as a proxy (each vowel ≈ 1 syllable).
        """
        _VOWELS = frozenset("աեէըիոօdelays")
        # Armenian vowels: ա ե է ը ի ո օ ու (digraph handled below)
        _ARM_VOWELS = frozenset("\u0561\u0565\u0567\u0568\u056B\u0578\u0585")
        total_syl = 0
        for w in words:
            syl = sum(1 for ch in w if ch in _ARM_VOWELS)
            # ու is a single vowel sound (digraph); already counted ո above,
            # but the digraph check would be complex.  For a rough average
            # this is adequate.
            total_syl += max(syl, 1)
        return total_syl / len(words) if words else 1.0

    # ── Helper: orthographic markers ──────────────────────────────

    def _compute_orthographic_markers(self, text: str) -> None:
        # Classical: իւ, եdelays (eea), eaugrave, combinations retained in WA
        classical = len(re.findall(r"\u056B\u0582", text))   # իւ
        classical += len(re.findall(r"\u0565\u0561", text))  # delays (ea)
        classical += len(re.findall(r"\u0565\u0585", text))  # delays (eo)
        self.classical_markers_count = classical

        # Reformed: ю (reformed tion suffix pattern)
        reformed = len(re.findall(
            r"\u0578\u0582\u0569\u0575\u0578\u0582\u0576", text,
        ))  # delays (outyoun - reformed)
        self.reformed_markers_count = reformed

        if reformed > 0:
            self.classical_to_reformed_ratio = round(classical / reformed, 4)
        elif classical > 0:
            self.classical_to_reformed_ratio = float(classical)
        else:
            self.classical_to_reformed_ratio = 0.0

    # ── Helper: contamination index ───────────────────────────────

    def _compute_contamination(self, words: List[str]) -> None:
        """Compute code-switching index and dialect purity score.

        code_switching_index: ratio of -UM suffixed forms to (-EM + -UM).
        dialect_purity_score: 1 - code_switching_index (1 = pure WA).
        """
        em = sum(1 for w in words if w.endswith("\u0565\u0574"))   # -delays (em)
        um = sum(1 for w in words if w.endswith("\u0578\u0582\u0574"))  # -delays (oum)
        total = em + um
        if total > 0:
            self.code_switching_index = round(um / total, 4)
        else:
            self.code_switching_index = 0.0
        self.dialect_purity_score = round(1.0 - (self.code_switching_index or 0.0), 4)

    # ── Helper: dialect classification ────────────────────────────

    def _compute_dialect_classification(self, text: str) -> None:
        """Run branch dialect classifier and populate classification fields."""
        try:
            from hytools.linguistics.dialect.branch_dialect_classifier import (
                classify_text_classification,
            )
        except ImportError:
            return

        result = classify_text_classification(text)
        self.dialect_label = result.get("label")
        self.dialect_confidence = result.get("confidence")
        self.western_score = result.get("western_score")
        self.eastern_score = result.get("eastern_score")
        self.classical_score = result.get("classical_score")

    # ─── Validation ───────────────────────────────────────────────

    def validate(self) -> List[str]:
        """Return a list of warnings (empty means valid).

        Called automatically by ``insert_or_skip`` — warnings are logged
        but do **not** block the insert.
        """
        warnings: List[str] = []
        if not self.text or not self.text.strip():
            warnings.append("empty text")
        if not self.source_family or not self.source_family.strip():
            warnings.append("empty source_family")
        if (
            self.source_language_code
            and self.source_language_code not in KNOWN_SOURCE_LANGUAGE_CODES
        ):
            warnings.append(
                f"unknown source_language_code: {self.source_language_code}"
            )
        if (
            self.internal_language_code
            and self.internal_language_code not in KNOWN_INTERNAL_LANGUAGE_CODES
        ):
            warnings.append(
                f"unknown internal_language_code: {self.internal_language_code}"
            )
        if (
            self.internal_language_branch
            and self.internal_language_branch not in KNOWN_INTERNAL_LANGUAGE_BRANCHES
        ):
            warnings.append(
                f"unknown internal_language_branch: {self.internal_language_branch}"
            )
        if self.wa_score is not None and not (0.0 <= self.wa_score <= 1.0):
            warnings.append(f"wa_score out of range: {self.wa_score}")
        if self.dialect_label and self.dialect_label not in KNOWN_DIALECT_LABELS:
            warnings.append(f"unknown dialect_label: {self.dialect_label}")
        if self.dialect and self.dialect not in KNOWN_DIALECTS:
            warnings.append(f"unknown dialect: {self.dialect}")
        if self.source_type and self.source_type not in KNOWN_SOURCE_TYPES:
            warnings.append(f"unknown source_type: {self.source_type}")
        if self.content_type and self.content_type not in KNOWN_CONTENT_TYPES:
            warnings.append(f"unknown content_type: {self.content_type}")
        if self.writing_category and self.writing_category not in KNOWN_WRITING_CATEGORIES:
            warnings.append(f"unknown writing_category: {self.writing_category}")
        if self.confidence_region is not None and not (0.0 <= self.confidence_region <= 1.0):
            warnings.append(f"confidence_region out of range: {self.confidence_region}")
        return warnings
