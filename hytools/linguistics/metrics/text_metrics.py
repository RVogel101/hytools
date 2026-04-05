"""
Quantitative linguistic metrics for tracking augmented text quality.

Computes standard metrics from quantitative linguistics research:
- Lexical diversity (TTR, STTR, Yule's K)
- Syntactic complexity (ASL, clause count)
- Morphological patterns (suffix frequencies)
- Orthographic patterns (classical vs reformed)
- Semantic metrics (entropy, KL-divergence)
- Dialect purity (code-switching index, variant ratios)

All metrics stored as JSON "metric cards" for comparative analysis.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.stats import entropy as scipy_entropy

from hytools.cleaning.armenian_tokenizer import extract_words


@dataclass
class LexicalMetrics:
    """Lexical diversity and richness metrics."""
    ttr: float  # Type-Token Ratio
    sttr: float  # Standardized TTR (for length-normalized comparison)
    yule_k: float  # Yule's K (vocabulary repetitiveness)
    unique_words: int
    total_words: int
    unique_word_rate: float  # unique_words / total_words
    vocabulary_breadth: float  # Unique words per 1000 words


@dataclass
class SyntacticMetrics:
    """Syntactic complexity metrics."""
    avg_sentence_length: float
    clauses_per_sentence: float
    flesch_kincaid_grade: float


@dataclass
class MorphologicalMetrics:
    """Armenian-specific morphological pattern metrics.

    Suffixes:
    - -եմ: Western 1st singular present (e.g. բերեմ "I bring")
    - -իմ: Possessive "my" in Western (not verb suffix)
    - -UM: EA verbal inflection (e.g. բERUM EM = "I bring"); also appears in WA in
      verbal nouns and certain lexical roots — NOT a WA present-tense marker, but
      flagging every -UM form as EA contamination would be an over-count.
    - -եան: Classical marker (should not be counted as -ան)
    - -ան: Shared (plural, 3rd person; excluding -եան)
    - -արան, -ական, -ութիւն: common derivational suffixes
    - -ել: Shared infinitive (e.g. գրել)
    - -իլ: Western-only infinitive (e.g. խօսիլ)

    Prefixes (WA markers):
    - կը/կ՚: Present tense (gu/g'); պիտի: future (bidi); word-initial չ: negative
    """
    suffix_em_count: int  # Western: -եմ (1st singular present)
    suffix_em_frequency: float
    suffix_im_count: int  # Possessive "my" (Western); not verb suffix
    suffix_im_frequency: float
    suffix_um_count: int  # Eastern verbal inflection (-UM); also occurs in WA verbal nouns/roots — see class docstring
    suffix_um_frequency: float
    suffix_ean_count: int  # Classical marker -եան (do not count as -ան)
    suffix_ean_frequency: float
    suffix_an_count: int  # -ան (various, excluding -եան)
    suffix_an_frequency: float
    suffix_aran_count: int  # -արան (derivational)
    suffix_aran_frequency: float
    suffix_akan_count: int  # -ական (derivational)
    suffix_akan_frequency: float
    suffix_utyun_count: int  # -ութիւն (derivational)
    suffix_utyun_frequency: float
    suffix_el_count: int  # -ել (infinitive, shared)
    suffix_el_frequency: float
    suffix_il_count: int  # Western-only infinitive (e.g. խօսիլ)
    suffix_il_frequency: float
    prefix_gu_count: int  # WA: կը (present)
    prefix_gu_frequency: float
    prefix_g_elided_count: int  # WA: կ՚
    prefix_g_elided_frequency: float
    prefix_bidi_count: int  # WA: պիտի (future)
    prefix_bidi_frequency: float
    prefix_ch_count: int  # WA: word-initial չ (negative)
    prefix_ch_frequency: float


@dataclass
class OrthographicMetrics:
    """Classical vs Reformed Armenian orthographic patterns."""
    classical_markers_count: int  # ո, ե, իւ, եա retained in Western
    classical_markers_frequency: float
    reformed_markers_count: int  # Removed in Eastern reform
    reformed_markers_frequency: float
    classical_to_reformed_ratio: float


@dataclass
class SemanticMetrics:
    """Semantic diversity and complexity."""
    entropy: float  # Shannon entropy of word frequencies
    pronoun_frequency: float
    avg_word_frequency_in_corpus: float


@dataclass
class ContaminationMetrics:
    """Eastern Armenian contamination detection."""
    code_switching_index: float  # Ratio of "mixed" forms
    eastern_form_ratio: float  # Estimate of Eastern form presence
    variant_ratio_avg: float  # Average variant (Eastern vs Western) ratio


@dataclass
class ComparisonMetrics:
    """Metrics comparing to baseline/original."""
    cosine_similarity_to_original: Optional[float] = None
    kl_divergence_from_wa_baseline: Optional[float] = None
    levenshtein_distance_to_original: Optional[int] = None


@dataclass
class QualityFlags:
    """Quality assessment flags."""
    dialect_purity_score: float  # 0-1 (1 = pure WA)
    baseline_deviation: str  # "within 1 std dev", "outside 2 std dev", etc.
    potential_issues: list[str] = field(default_factory=list)


@dataclass
class TextMetricCard:
    """Complete metric card for a single text."""
    text_id: str
    source: str
    text_length: int
    lexical: LexicalMetrics
    syntactic: SyntacticMetrics
    morphological: MorphologicalMetrics
    orthographic: OrthographicMetrics
    semantic: SemanticMetrics
    contamination: ContaminationMetrics
    comparison: ComparisonMetrics
    quality_flags: QualityFlags


class QuantitativeLinguisticsAnalyzer:
    """Computes quantitative linguistic metrics for Armenian text."""

    def __init__(self, wa_corpus_path: str = "data/raw/wikipedia/extracted"):
        """Initialize analyzer with optional WA corpus baseline.
        
        Args:
            wa_corpus_path: Path to Western Armenian corpus for baseline calculation
        """
        self.wa_corpus_path = wa_corpus_path
        self.wa_baseline_frequencies = None
        self._load_or_compute_baseline()

    def _load_or_compute_baseline(self) -> None:
        """Load or compute baseline metrics from WA corpus."""
        baseline_cache = Path("cache/wa_baseline_frequencies.json")

        if baseline_cache.exists():
            with open(baseline_cache, "r", encoding="utf-8") as f:
                self.wa_baseline_frequencies = json.load(f)
        else:
            # Compute baseline from corpus
            self.wa_baseline_frequencies = self._compute_baseline_from_corpus()

    def _compute_baseline_from_corpus(self) -> dict:
        """Compute baseline word frequencies from WA corpus."""
        freqs = Counter()
        corpus_path = Path(self.wa_corpus_path)

        if not corpus_path.exists():
            return {}

        for txt_file in corpus_path.glob("*.txt"):
            try:
                with open(txt_file, "r", encoding="utf-8") as f:
                    text = f.read()
                    words = extract_words(text, min_length=2)
                    freqs.update(words)
            except Exception:
                logger.debug("Failed to read corpus file %s", txt_file, exc_info=True)
                continue

        # Convert to proportion (frequency/total)
        total = sum(freqs.values())
        if total == 0:
            return {}

        baseline = {word: count / total for word, count in freqs.items()}

        # Cache it
        cache_path = Path("cache/wa_baseline_frequencies.json")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(baseline, f, ensure_ascii=False)

        return baseline

    def analyze_text(
        self,
        text: str,
        text_id: str = "unknown",
        source: str = "unknown",
        original_text: Optional[str] = None,
    ) -> TextMetricCard:
        """Analyze text and compute all metrics.
        
        Args:
            text: Text to analyze
            text_id: Identifier for this text
            source: Source of text
            original_text: Original text (for comparison metrics)
        
        Returns:
            TextMetricCard with all computed metrics
        """
        # Extract words
        words = extract_words(text, min_length=2)
        sentences = self._tokenize_sentences(text)

        # Compute metrics
        lexical = self._compute_lexical_metrics(words)
        syntactic = self._compute_syntactic_metrics(words, sentences)
        morphological = self._compute_morphological_metrics(words)
        orthographic = self._compute_orthographic_metrics(text)
        semantic = self._compute_semantic_metrics(words)
        contamination = self._compute_contamination_metrics(words)

        # Comparison metrics (if original provided)
        comparison = self._compute_comparison_metrics(
            text, original_text, words
        ) if original_text else ComparisonMetrics()

        # Quality flags
        quality_flags = self._compute_quality_flags(
            lexical, morphological, contamination
        )

        return TextMetricCard(
            text_id=text_id,
            source=source,
            text_length=len(text),
            lexical=lexical,
            syntactic=syntactic,
            morphological=morphological,
            orthographic=orthographic,
            semantic=semantic,
            contamination=contamination,
            comparison=comparison,
            quality_flags=quality_flags,
        )

    def _tokenize_sentences(self, text: str) -> list[str]:
        """Tokenize text into sentences.

        Delimiters: ։ (Armenian full stop U+0589), ? ! and : — the colon is
        used as a sentence-final marker in both Western and Eastern Armenian
        prose (e.g. quoting, listing, rhetorical pause that ends a unit).
        """
        sentences = re.split(r'[։?!:]+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _compute_lexical_metrics(self, words: list[str]) -> LexicalMetrics:
        """Compute lexical diversity metrics."""
        total_words = len(words)
        unique_words = len(set(words))

        if total_words == 0:
            return LexicalMetrics(
                ttr=0.0,
                sttr=0.0,
                yule_k=0.0,
                unique_words=0,
                total_words=0,
                unique_word_rate=0.0,
                vocabulary_breadth=0.0,
            )

        # Type-Token Ratio
        ttr = unique_words / total_words

        # Standardized TTR (STTR) - over 100-word windows
        sttr = self._compute_sttr(words)

        # Yule's K
        yule_k = self._compute_yule_k(words)

        # Vocabulary breadth (unique words per 1000 words)
        vocab_breadth = (unique_words / total_words) * 1000 if total_words > 0 else 0
        unique_word_rate = unique_words / total_words if total_words > 0 else 0

        return LexicalMetrics(
            ttr=round(ttr, 4),
            sttr=round(sttr, 4),
            yule_k=round(yule_k, 2),
            unique_words=unique_words,
            total_words=total_words,
            unique_word_rate=round(unique_word_rate, 4),
            vocabulary_breadth=round(vocab_breadth, 2),
        )

    def _compute_sttr(self, words: list[str], window_size: int = 100) -> float:
        """Compute Standardized Type-Token Ratio."""
        if len(words) < window_size:
            return len(set(words)) / len(words) if len(words) > 0 else 0.0

        sttr_values = []
        for i in range(0, len(words) - window_size + 1, window_size):
            window = words[i : i + window_size]
            ttr = len(set(window)) / len(window)
            sttr_values.append(ttr)

        return float(np.mean(sttr_values)) if sttr_values else 0.0

    def _compute_yule_k(self, words: list[str]) -> float:
        """Compute Yule's K (vocabulary repetitiveness).
        
        Higher K = more repetitive vocabulary
        Lower K = more diverse vocabulary
        """
        if len(words) == 0:
            return 0.0

        freqs = Counter(words)
        N = len(words)
        V = len(freqs)

        # K = 10000 * (sum(f^2) - V) / (N^2)
        sum_freq_sq = sum(f ** 2 for f in freqs.values())
        V1 = sum_freq_sq  # sum of (frequency^2)

        if N == 0:
            return 0.0

        K = 10 ** 4 * (V1 - V) / (N ** 2)
        return max(0, K)  # K should be non-negative

    def _compute_syntactic_metrics(
        self, words: list[str], sentences: list[str]
    ) -> SyntacticMetrics:
        """Compute syntactic complexity metrics."""
        num_sentences = len([s for s in sentences if len(extract_words(s)) > 0])
        total_words = len(words)

        if num_sentences == 0:
            num_sentences = 1  # Avoid division by zero

        # Average sentence length
        asl = total_words / num_sentences

        # Clause count — Armenian-specific approach.
        #
        # Methodology: count subordinating conjunctions per sentence.  Each
        # occurrence of a clause-introducing word adds one embedded clause to
        # the sentence count.  This is NOT English-biased: the conjunctions
        # listed below are genuine Armenian subordinators for WA and EA.
        #
        # A more accurate (but heavier) alternative is to count finite verb
        # forms per sentence using WA conjugation markers (կ / կ՚ prefix count
        # + inflected-verb suffixes).  That approach is recorded as a future
        # improvement in FUTURE_IMPROVEMENTS.md.
        #
        # The baseline is 1 clause per sentence (the main clause); each
        # subordinating conjunction adds one more clause.
        _ARMEN_SUBORD = {
            'որ',   # that / which / who
            'ինչ',  # what / whatever (ինչ)
            'ինչ',  # what
            'եթե',  # if (reformed / EA spelling)
            'եթէ',  # if (classical / WA spelling)
            'երբ',  # when
            'ուր',  # where
            'մինչ', # while / until
            'թէ',   # whether / or (WA classical)
            'թե',   # whether / or (reformed)
            'ուստի',# therefore / so (discourse connective)
        }
        total_clause_markers = sum(
            sum(1 for token in re.findall(r'[\u0531-\u0587]+', sentence)
                if token in _ARMEN_SUBORD)
            for sentence in sentences
        )
        # 1 base clause per sentence + 1 extra per embedded subordinate clause.
        clauses_per_sentence = 1.0 + total_clause_markers / max(1, num_sentences)

        # Flesch-Kincaid grade level using per-word Armenian syllable count.
        # Syllables are counted via the internal vowel-nucleus counter
        # (linguistics.morphology.core.count_syllables), which handles the
        # ու digraph (one syllable) and Armenian-only characters correctly —
        # no English syllabification heuristics are used.
        from hytools.linguistics.morphology.core import count_syllables as _count_syl
        total_syllables = sum(_count_syl(w) for w in words)
        avg_syllables_per_word = total_syllables / total_words if total_words > 0 else 2.0
        fk_grade = 0.39 * asl + 11.8 * avg_syllables_per_word - 15.59

        return SyntacticMetrics(
            avg_sentence_length=round(asl, 2),
            clauses_per_sentence=round(clauses_per_sentence, 2),
            flesch_kincaid_grade=round(fk_grade, 2),
        )

    def _compute_morphological_metrics(
        self, words: list[str]
    ) -> MorphologicalMetrics:
        """Compute Armenian morphological pattern metrics.

        Tracks key suffixes and prefixes that differ between Western and Eastern.
        -եմ = WA 1st sg present; -ում = EA imperfective; -իլ = WA-only infinitive.
        """
        total_words = len(words)

        # Suffix counts
        em_count = sum(1 for w in words if w.endswith("եմ"))
        im_count = sum(1 for w in words if w.endswith("իմ"))
        um_count = sum(1 for w in words if w.endswith("ում"))
        ean_count = sum(1 for w in words if w.endswith("եան"))
        an_count = sum(1 for w in words if w.endswith("ան") and not w.endswith("եան"))
        el_count = sum(1 for w in words if w.endswith("ել"))
        il_count = sum(1 for w in words if w.endswith("իլ"))

        aran_count = sum(1 for w in words if w.endswith("արան"))
        akan_count = sum(1 for w in words if w.endswith("ական"))
        utyun_count = sum(1 for w in words if w.endswith("ութիւն"))

        # Prefix counts (WA markers — as separate words or before verb)
        gu_count = sum(1 for w in words if w == "կը")
        g_elided_count = sum(1 for w in words if w == "կ՚")
        bidi_count = sum(1 for w in words if w == "պիտի")
        ch_count = sum(1 for w in words if w.startswith("չ") and len(w) > 1)

        def _freq(n: int) -> float:
            return round(n / total_words, 6) if total_words > 0 else 0

        return MorphologicalMetrics(
            suffix_em_count=em_count,
            suffix_em_frequency=_freq(em_count),
            suffix_im_count=im_count,
            suffix_im_frequency=_freq(im_count),
            suffix_um_count=um_count,
            suffix_um_frequency=_freq(um_count),
            suffix_ean_count=ean_count,
            suffix_ean_frequency=_freq(ean_count),
            suffix_an_count=an_count,
            suffix_an_frequency=_freq(an_count),
            suffix_aran_count=aran_count,
            suffix_aran_frequency=_freq(aran_count),
            suffix_akan_count=akan_count,
            suffix_akan_frequency=_freq(akan_count),
            suffix_utyun_count=utyun_count,
            suffix_utyun_frequency=_freq(utyun_count),
            suffix_el_count=el_count,
            suffix_el_frequency=_freq(el_count),
            suffix_il_count=il_count,
            suffix_il_frequency=_freq(il_count),
            prefix_gu_count=gu_count,
            prefix_gu_frequency=_freq(gu_count),
            prefix_g_elided_count=g_elided_count,
            prefix_g_elided_frequency=_freq(g_elided_count),
            prefix_bidi_count=bidi_count,
            prefix_bidi_frequency=_freq(bidi_count),
            prefix_ch_count=ch_count,
            prefix_ch_frequency=_freq(ch_count),
        )

    def debug_morphological_suffixes(self, words: list[str]) -> dict:
        """Return the words that triggered specific morphological suffix counters."""
        return {
            "suffix_ian_words": [w for w in words if w.endswith("եան")],
            "suffix_an_words": [w for w in words if w.endswith("ան") and not w.endswith("եան")],
            "suffix_aran_words": [w for w in words if w.endswith("արան")],
            "suffix_agan_words": [w for w in words if w.endswith("ական")],
            "suffix_utyun_words": [w for w in words if w.endswith("ութիւն")],
        }

    def _compute_orthographic_metrics(self, text: str) -> OrthographicMetrics:
        """Compute classical vs reformed Armenian orthography metrics.
        
        Classical (Western Armenian): retains ո, ե, իւ, եա
        Reformed (Eastern Armenian): simplified these
        """
        # Classical Armenian markers (Western retains, Eastern removed)
        # The patterns below capture Western classical spellings that Eastern
        # reform removed / simplified.
        classical_patterns = [
            r'ո',   # Starts many Western words
            r'իւ',  # Diphthong retained in Western
            r'եա',  # Retained in Western
            r'եօ',  # Classical diphthong often rewritten in reform
            r'էա',  # Classical use of է + ա
            r'էյ',  # Classical use of է + յ
            r'իա',  # Classical diphthong
            r'ոյ',  # Classical diphthong
            r'այ',  # Classical diphthong
            r'աւ',  # Classical spelling variant
        ]

        # Reformed markers (Eastern orthography)
        # Includes word-final 'ա' and common reformed endings.
        # Note: Python's ``\b`` word boundary does not treat Armenian letters as
        # word characters, so we use an explicit negative lookahead for Armenian
        # letters to detect word-final occurrences.
        armenian_letter = r"[\u0530-\u058F]"
        reformed_patterns = [
            r'ա(?!' + armenian_letter + r')',    # word-final ա (more common in reformed spelling)
            r'թյուն(?!' + armenian_letter + r')',  # reformed spelling (classical: թիւն)
            r'յան(?!' + armenian_letter + r')',   # classical եան vs reformed յան
            r'ե',                                # reformed form usage (broad marker)
        ]

        classical_count = sum(len(re.findall(p, text)) for p in classical_patterns)
        reformed_count = sum(len(re.findall(p, text)) for p in reformed_patterns)

        total = len(text)

        classical_freq = classical_count / total if total > 0 else 0
        reformed_freq = reformed_count / total if total > 0 else 0

        ratio = classical_count / max(1, reformed_count)

        return OrthographicMetrics(
            classical_markers_count=classical_count,
            classical_markers_frequency=round(classical_freq, 6),
            reformed_markers_count=reformed_count,
            reformed_markers_frequency=round(reformed_freq, 6),
            classical_to_reformed_ratio=round(ratio, 2),
        )

    def debug_orthographic_markers(self, text: str) -> dict:
        """Return the exact substrings that triggered classical/reformed markers."""
        classical_patterns = [
            r'ո', r'իւ', r'եա', r'եօ', r'էա', r'էյ', r'իա', r'ոյ', r'այ', r'աւ'
        ]
        # Avoid Python '\b' word boundaries, since they don't treat Armenian
        # letters as word characters reliably. Use an explicit negative lookahead.
        armenian_letter = r"[\u0530-\u058F]"
        reformed_patterns = [
            r'ա(?!' + armenian_letter + r')',
            r'թյուն(?!' + armenian_letter + r')',
            r'յան(?!' + armenian_letter + r')',
            r'ե',
        ]

        def _matches(patterns: list[str]) -> dict:
            out: dict = {}
            for pat in patterns:
                matches = re.findall(pat, text)
                if matches:
                    out[pat] = matches
            return out

        return {
            "classical": _matches(classical_patterns),
            "reformed": _matches(reformed_patterns),
        }

    def _compute_semantic_metrics(self, words: list[str]) -> SemanticMetrics:
        """Compute semantic diversity and complexity metrics."""
        total_words = len(words)

        # Shannon Entropy (unpredictability of vocabulary)
        word_freqs = Counter(words)
        probabilities = [freq / total_words for freq in word_freqs.values()]
        entropy_score = scipy_entropy(probabilities, base=2)

        # Pronoun frequency (both dialects use these; WA also uses ան for he/she/it)
        pronouns = ['ես', 'դու', 'նա', 'ան', 'ինք', 'մենք', 'դուք', 'նրանք', 'այն', 'սա']
        pronoun_count = sum(1 for w in words if w in pronouns)
        pronoun_freq = pronoun_count / total_words if total_words > 0 else 0

        # Average word frequency in corpus (if baseline available)
        avg_freq = 0.0
        if self.wa_baseline_frequencies:
            freqs = [self.wa_baseline_frequencies.get(w, 0) for w in words]
            valid_freqs = [f for f in freqs if f > 0]
            if valid_freqs:
                avg_freq = np.mean(valid_freqs)

        return SemanticMetrics(
            entropy=round(float(entropy_score), 4),
            pronoun_frequency=round(float(pronoun_freq), 6),
            avg_word_frequency_in_corpus=float(round(float(avg_freq), 8)),
        )

    def _compute_contamination_metrics(
        self, words: list[str]
    ) -> ContaminationMetrics:
        """Compute Eastern Armenian contamination metrics.

        -եМ = Western 1st sg present (e.g. բEREM = I bring).
        -UM = Eastern present/imperfective verbal inflection (e.g. բERUM EM).
        -UM also appears in WA in verbal nouns and certain roots, so a high
        -UM ratio is a strong EA *signal* but not a definitive EA *proof*.
        Higher eastern_form_ratio = more likely EA contamination.
        """
        total_words = len(words)

        em_forms = sum(1 for w in words if w.endswith("եմ"))  # WA
        um_forms = sum(1 for w in words if w.endswith("ում"))  # EA

        total_verb_forms = em_forms + um_forms
        # Eastern ratio: um / (em + um); higher = more EA
        eastern_ratio = um_forms / max(1, total_verb_forms)
        # Code-switching: same as eastern ratio (EA forms mixed in)
        code_switching = eastern_ratio

        return ContaminationMetrics(
            code_switching_index=round(code_switching, 6),
            eastern_form_ratio=round(eastern_ratio, 6),
            variant_ratio_avg=round(eastern_ratio, 6),
        )

    def _compute_comparison_metrics(
        self,
        text: str,
        original_text: str,
        words: list[str],
    ) -> ComparisonMetrics:
        """Compute metrics comparing to original/baseline."""
        if not original_text:
            return ComparisonMetrics()

        # Levenshtein distance
        lev_dist = self._levenshtein_distance(original_text, text)

        # Cosine similarity (TF-IDF vectors)
        cosine_sim = self._cosine_similarity(original_text, text)

        # KL-divergence from WA baseline
        kl_div = self._kl_divergence_from_baseline(words) if self.wa_baseline_frequencies else None

        return ComparisonMetrics(
            cosine_similarity_to_original=round(cosine_sim, 4) if cosine_sim is not None else None,
            kl_divergence_from_wa_baseline=round(kl_div, 6) if kl_div is not None else None,
            levenshtein_distance_to_original=lev_dist,
        )

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Compute Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def _cosine_similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity between two texts."""
        words1 = extract_words(text1, min_length=2)
        words2 = extract_words(text2, min_length=2)

        freq1 = Counter(words1)
        freq2 = Counter(words2)

        # Common words
        common = set(freq1.keys()) & set(freq2.keys())

        if not common:
            return 0.0

        dot_product = sum(freq1[w] * freq2[w] for w in common)
        norm1 = math.sqrt(sum(f ** 2 for f in freq1.values()))
        norm2 = math.sqrt(sum(f ** 2 for f in freq2.values()))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _kl_divergence_from_baseline(self, words: list[str]) -> float:
        """Compute KL-divergence from WA baseline distribution."""
        if not self.wa_baseline_frequencies:
            return 0.0

        # Compute empirical distribution of text
        freq = Counter(words)
        total = len(words)
        empirical_dist = {w: f / total for w, f in freq.items()}

        # KL(empirical || baseline)
        kl_div = 0.0
        for word, p in empirical_dist.items():
            q = self.wa_baseline_frequencies.get(word, 1e-10)  # Smoothing
            if p > 0:
                kl_div += p * math.log(p / q)

        return kl_div

    def _compute_quality_flags(
        self,
        lexical: LexicalMetrics,
        morphological: MorphologicalMetrics,
        contamination: ContaminationMetrics,
    ) -> QualityFlags:
        """Compute quality assessment flags."""
        issues = []
        dialect_purity = 1.0

        # -UM as verbal inflection is an EA marker.  Penalise only when there
        # are several -UM forms relative to -EM forms (a couple of occurrences
        # as lexical/verbal-noun roots is not significant).
        if morphological.suffix_um_count > 2:
            issues.append(f"Found {morphological.suffix_um_count} -UM forms (EA verbal marker)")
            dialect_purity -= 0.1 * min(1.0, morphological.suffix_um_count / 10)

        # Check code-switching
        if contamination.code_switching_index > 0.05:
            issues.append(f"Code-switching index: {contamination.code_switching_index:.4f}")
            dialect_purity -= 0.05

        # Check vocabulary diversity
        if lexical.ttr < 0.5:
            issues.append(f"Low vocabulary diversity: TTR={lexical.ttr:.4f}")
            dialect_purity -= 0.05

        dialect_purity = max(0.0, min(1.0, dialect_purity))

        return QualityFlags(
            dialect_purity_score=round(dialect_purity, 4),
            baseline_deviation="within normal range",  # TODO: compute from baseline
            potential_issues=issues,
        )

    def to_json(self, metric_card: TextMetricCard) -> str:
        """Serialize metric card to JSON."""
        return json.dumps(asdict(metric_card), ensure_ascii=False, indent=2)

    def save_metric_card(
        self,
        metric_card: TextMetricCard,
        output_dir: str = "cache/metric_cards",
    ) -> None:
        """Save metric card to JSON file."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        filepath = output_path / f"{metric_card.text_id}_metrics.json"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_json(metric_card))


def compute_orthographic_metrics(text: str) -> OrthographicMetrics:
    """Top-level wrapper to compute orthographic metrics for a text.

    This duplicates the logic in `QuantitativeLinguisticsAnalyzer._compute_orthographic_metrics`
    so callers can import a simple function without instantiating the analyzer.
    """
    # Classical Armenian markers (Western retains, Eastern removed)
    classical_patterns = [
        r'ո',
        r'իւ',
        r'եա',
        r'եօ',
        r'էա',
        r'էյ',
        r'իա',
        r'ոյ',
        r'այ',
        r'աւ',
    ]

    # Reformed markers (Eastern orthography)
    armenian_letter = r"[\u0530-\u058F]"
    reformed_patterns = [
        r'ա(?!' + armenian_letter + r')',
        r'թյուն(?!' + armenian_letter + r')',
        r'յան(?!' + armenian_letter + r')',
        r'ե',
    ]

    classical_count = sum(len(re.findall(p, text)) for p in classical_patterns)
    reformed_count = sum(len(re.findall(p, text)) for p in reformed_patterns)

    total = len(text)
    classical_freq = classical_count / total if total > 0 else 0
    reformed_freq = reformed_count / total if total > 0 else 0
    ratio = classical_count / max(1, reformed_count)

    return OrthographicMetrics(
        classical_markers_count=classical_count,
        classical_markers_frequency=round(classical_freq, 6),
        reformed_markers_count=reformed_count,
        reformed_markers_frequency=round(reformed_freq, 6),
        classical_to_reformed_ratio=round(ratio, 2),
    )


if __name__ == "__main__":
    # Example usage
    analyzer = QuantitativeLinguisticsAnalyzer()

    sample_text = "Սա լավ տուն մը է։ Մենք հաճախ այստեղ կը գանք։"  # WA: noun+մը, կը+verb
    
    metric_card = analyzer.analyze_text(
        text=sample_text,
        text_id="sample_001",
        source="manual_test",
    )

    print(analyzer.to_json(metric_card))
    analyzer.save_metric_card(metric_card)
