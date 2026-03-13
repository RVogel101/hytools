"""
Word difficulty component analysis for Armenian vocabulary progression.

Scores word complexity based on morphological and phonological factors:
  - Syllable count (including hidden vowels in certain grammatical contexts)
  - Declension class regularity (noun)
  - Verb conjugation class (weak/irregular)
  - Affix stacking (number of morpheme boundaries)
  - Phonological complexity (rare consonant clusters, fricatives)

The difficulty_score() function returns a composite score (1.0–10.0) where
higher = more difficult. This is used to supplement frequency-based ordering
when present, ensuring learners encounter simpler morphological patterns first.
"""

from dataclasses import dataclass
from typing import Optional





from .core import ARM, ARM_UPPER, VOWELS, count_syllables, is_armenian

# ─── Schwa Epenthesis Constants ──────────────────────────────────
# In Western Armenian, illegal consonant clusters are "repaired" with schwa (ə/ը)
# Based on phonotactic constraints: initial CC → C@C, medial/final violations → epenthesis
HIDDEN_VOWEL = ARM["y_schwa"]  # ը

# Sonority hierarchy for detecting epenthesis
# Lower number = lower sonority (obstruent); Higher = higher sonority (sonorant)
_SONORITY_MAP = {
    ARM["p"]: 1, ARM["b"]: 1, ARM["t"]: 1, ARM["d"]: 1,
    ARM["k"]: 1, ARM["g"]: 1,  # Stops
    ARM["ts"]: 2, ARM["dz"]: 2, ARM["ch"]: 2, ARM["j"]: 2,  # Affricates (single units)
    ARM["s"]: 2.5, ARM["z"]: 2.5, ARM["sh"]: 2.5, ARM["zh"]: 2.5,
    ARM["kh"]: 2.5, ARM["gh"]: 2.5, ARM["f"]: 2.5, ARM["v"]: 2.5,  # Fricatives
    ARM["m"]: 3, ARM["n"]: 3,  # Nasals
    ARM["l"]: 3.5, ARM["r"]: 3.5, ARM["rr"]: 3.5,  # Liquids
    ARM["y"]: 4,  # Glides/approximants
}

# Single-unit consonants (affricates/aspirates) don't form clusters
_SINGLE_CONSONANT_UNITS = {
    ARM["ts"], ARM["dz"], ARM["ch"], ARM["j"],  # Affricates
    ARM["t_asp"], ARM["p_asp"], ARM["k_asp"],   # Aspirates
    ARM["c_asp"], ARM["ch_asp"],                 # Compound aspirates
}


def _get_consonant_clusters(word: str) -> list:
    """Extract consonant clusters from word.
    
    Returns:
        List of tuples: (start_index, end_index, cluster_string, position_type)
    """
    consonants = (set(ARM.values()) | set(ARM_UPPER.values())) - VOWELS - {HIDDEN_VOWEL}
    clusters = []
    i = 0
    
    while i < len(word):
        if word[i] in consonants:
            cluster_start = i
            while i < len(word) and word[i] in consonants:
                i += 1
            cluster_end = i
            cluster = word[cluster_start:cluster_end]
            
            if len(cluster) >= 2:
                pos_type = "initial" if cluster_start == 0 else (
                    "final" if cluster_end == len(word) else "medial"
                )
                clusters.append((cluster_start, cluster_end, cluster, pos_type))
        else:
            i += 1
    
    return clusters


def _requires_epenthesis(cluster: str, position: str) -> bool:
    """Check if cluster requires schwa epenthesis based on phonotactics.
    
    Args:
        cluster: Consonant sequence
        position: "initial", "medial", or "final"
    
    Returns:
        True if epenthesis would occur
    """
    # All-single-units don't need epenthesis (e.g., two affricates)
    if all(c in _SINGLE_CONSONANT_UNITS for c in cluster):
        return False
    
    if position == "initial":
        # Initial CC/CCC with non-single-unit elements requires epenthesis
        for char in cluster:
            if char not in _SINGLE_CONSONANT_UNITS:
                return True
        return False
    
    elif position == "medial":
        # Rising sonority (sonority increases from c1 to c2) needs epenthesis
        # Codas require falling or level sonority (c1_son >= c2_son)
        # So if c1_son < c2_son (rising), epenthesis is needed
        if len(cluster) >= 2:
            c1_son = _SONORITY_MAP.get(cluster[0], 2.0)
            c2_son = _SONORITY_MAP.get(cluster[1], 2.0)
            if c1_son < c2_son:  # Rising sonority = epenthesis needed
                return True
        return False
    
    elif position == "final":
        # Final clusters with rising sonority need epenthesis
        # Codas need falling/level sonority
        for i in range(len(cluster) - 1):
            c1_son = _SONORITY_MAP.get(cluster[i], 2.0)
            c2_son = _SONORITY_MAP.get(cluster[i + 1], 2.0)
            if c1_son < c2_son:  # Rising sonority = epenthesis needed
                return True
        return False
    
    return False


def count_syllables_with_context(
    word: str,
    with_epenthesis: bool = False,
) -> int:
    """Count syllables, optionally including epenthetic schwa insertions.
    
    When with_epenthesis=True, counts extra syllables from schwa insertion
    in illegal consonant clusters (following Western Armenian phonotactics).
    
    Args:
        word: Armenian word
        with_epenthesis: If True, add syllables for epenthetic schwas
    
    Returns:
        Syllable count
    """
    if not word:
        return 0

    base_count = count_syllables(word)
    
    if not with_epenthesis:
        return base_count

    # Count epenthetic schwas
    clusters = _get_consonant_clusters(word)
    epenthesis_count = 0
    
    for _, _, cluster, position in clusters:
        if _requires_epenthesis(cluster, position):
            epenthesis_count += 1

    return base_count + epenthesis_count

# ─── Phonological Complexity Scoring ──────────────────────────────────

def _score_rare_phonemes(word: str) -> float:
    """Score presence of rare/difficult consonants (fricatives, affricates).

    Rare phonemes that are harder to pronounce:
      - ժ (zh) — voiced fricative
      - ծ (ts) / ց (ts') — affricates
      - ձ (dz) — affricate
      - Clusters with aspirates (թ, փ, կ', ց')
    """
    score = 0.0
    rare_phones = {
        ARM["zh"]: 0.3,      # ժ
        ARM["ts"]: 0.2,      # ծ
        ARM["c_asp"]: 0.2,   # ծ' (ts')
        ARM["dz"]: 0.2,      # ձ
        ARM["ch_asp"]: 0.15, # ճ' (ch')
        ARM["t_asp"]: 0.15,  # թ
        ARM["p_asp"]: 0.15,  # փ
        ARM["k_asp"]: 0.15,  # կ'
    }
    for char in word:
        if char in rare_phones:
            score += rare_phones[char]
    return min(score, 2.0)  # Cap at 2.0


def _score_consonant_clusters(word: str) -> float:
    """Score presence of complex consonant clusters.

    Clusters with 3+ consonants in sequence, or rare cluster combinations,
    increase difficulty.
    """
    score = 0.0
    consonants = set(ARM.values()) - VOWELS - {HIDDEN_VOWEL}

    cluster_length = 0
    for i, char in enumerate(word):
        if char in consonants:
            cluster_length += 1
        else:
            if cluster_length >= 2:
                score += 0.1 * cluster_length  # More consonants = harder
            cluster_length = 0

    return min(score, 1.5)


# ─── Morphological Complexity Scoring ──────────────────────────────────

def _score_affix_count(word: str) -> float:
    """Estimate the number of affixes by counting morpheme boundaries.

    Heuristic: Sharp changes in phoneme type (vowel→consonant,
    rare phoneme appearance near word end) suggest affixes.
    """
    # Simple heuristic: check for suffix patterns
    # Suffixes like -ական, -ity are common
    _ner = ARM["n"] + ARM["ye"] + ARM["r"]  # -ներ (plural)
    suffix_patterns = [
        ARM["a"] + ARM["k"] + ARM["a"] + ARM["n"],  # -ական (noun former)
        ARM["i"],                                     # -ի (genitive)
        ARM["e"],                                     # -է (ablative)
        _ner,                                         # -ներ (plural)
    ]

    score = 0.0
    for suffix in suffix_patterns:
        if word.endswith(suffix) and len(word) > len(suffix):
            score += 0.3
    return score


# ─── Declension / Conjugation Class Scoring ──────────────────────────

def score_noun_difficulty(
    word: str,
    declension_class: Optional[str] = None,
) -> float:
    """Score difficulty of a noun based on declension class and form.

    Args:
        word: Armenian noun
        declension_class: One of "i_class", "u_class", "o_class", etc.
                         If None, score by orthographic form only.

    Returns:
        Difficulty score (0.0–10.0)
    """
    base_score = 1.0  # Base score

    # Syllable component (1–3 points)
    syl_count = count_syllables(word)
    syl_score = min(syl_count * 0.8, 3.0)

    # Declension class regularity
    # i_class is most productive; others are less regular
    class_score = 0.0
    if declension_class:
        irregular_classes = {"o_class", "u_class", "a_class"}
        if declension_class in irregular_classes:
            class_score = 1.0  # Less regular = +1.0
        elif declension_class == "i_class":
            class_score = 0.0  # Most regular = no penalty

    # Phonological components
    phoneme_score = _score_rare_phonemes(word)
    cluster_score = _score_consonant_clusters(word)

    return base_score + syl_score + class_score + (phoneme_score * 0.5) + (cluster_score * 0.5)


def score_verb_difficulty(
    word: str,
    verb_class: Optional[str] = None,
) -> float:
    """Score difficulty of a verb based on conjugation class and form.

    Args:
        word: Armenian infinitive (verb stem)
        verb_class: One of "weak", "irregular", "borrowed", etc.
                   If None, score by orthographic form only.

    Returns:
        Difficulty score (0.0–10.0)
    """
    base_score = 1.0

    # Syllable component
    syl_count = count_syllables(word)
    syl_score = min(syl_count * 0.8, 3.0)

    # Conjugation class irregularity
    class_score = 0.0
    if verb_class:
        if verb_class == "irregular":
            class_score = 2.0  # Highly irregular
        elif verb_class == "weak":
            class_score = 0.5  # Slightly irregular
        elif verb_class in ("borrowed", "loanword"):
            class_score = 0.8

    # Phonological complexity
    phoneme_score = _score_rare_phonemes(word)
    cluster_score = _score_consonant_clusters(word)

    return base_score + syl_score + class_score + (phoneme_score * 0.5) + (cluster_score * 0.5)


def score_word_difficulty(
    word: str,
    pos: str,
    declension_class: Optional[str] = None,
    verb_class: Optional[str] = None,
) -> float:
    """Composite difficulty score for any Armenian word.

    Args:
        word: Armenian word
        pos: Part of speech ("noun", "verb", "adjective", etc.)
        declension_class: For nouns (optional)
        verb_class: For verbs (optional)

    Returns:
        Difficulty score (0.0–10.0), higher = more difficult
    """
    if pos == "noun":
        return score_noun_difficulty(word, declension_class)
    elif pos == "verb":
        return score_verb_difficulty(word, verb_class)
    else:
        # Generic scoring for adjectives, adverbs, etc.
        base_score = 1.0
        syl_score = min(count_syllables(word) * 0.8, 2.5)
        phoneme_score = _score_rare_phonemes(word) * 0.5
        cluster_score = _score_consonant_clusters(word) * 0.5
        affix_score = _score_affix_count(word) * 0.8
        return base_score + syl_score + phoneme_score + cluster_score + affix_score


# ─── Component Analysis Data Class ──────────────────────────────────

@dataclass
class WordDifficultyAnalysis:
    """Complete morphological and phonological analysis for a word."""
    word: str
    pos: str
    syllables_base: int
    syllables_with_grammar: int
    phonological_score: float
    cluster_score: float
    affix_count: float
    declension_class: Optional[str] = None
    verb_class: Optional[str] = None
    overall_difficulty: float = 0.0

    def __post_init__(self):
        """Compute overall difficulty on construction."""
        if self.pos == "noun":
            self.overall_difficulty = score_noun_difficulty(
                self.word, self.declension_class
            )
        elif self.pos == "verb":
            self.overall_difficulty = score_verb_difficulty(
                self.word, self.verb_class
            )
        else:
            self.overall_difficulty = score_word_difficulty(
                self.word, self.pos, self.declension_class, self.verb_class
            )

    def summary(self) -> str:
        """Return a human-readable difficulty report."""
        return (
            f"{self.word:20} │ {self.pos:6} │ "
            f"syl={self.syllables_base}/{self.syllables_with_grammar} │ "
            f"phon={self.phonological_score:.2f} │ "
            f"clust={self.cluster_score:.2f} │ "
            f"difficulty={self.overall_difficulty:.2f}"
        )


def analyze_word(
    word: str,
    pos: str,
    declension_class: Optional[str] = None,
    verb_class: Optional[str] = None,
) -> WordDifficultyAnalysis:
    """Create a full difficulty analysis for a word."""
    syl_base = count_syllables(word)
    syl_with_grammar = count_syllables_with_context(word, with_epenthesis=True)
    phon_score = _score_rare_phonemes(word)
    cluster_score = _score_consonant_clusters(word)
    affix_count = _score_affix_count(word)

    return WordDifficultyAnalysis(
        word=word,
        pos=pos,
        syllables_base=syl_base,
        syllables_with_grammar=syl_with_grammar,
        phonological_score=phon_score,
        cluster_score=cluster_score,
        affix_count=affix_count,
        declension_class=declension_class,
        verb_class=verb_class,
    )
