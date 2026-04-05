"""
Western Armenian stemming and lemmatization utilities.

Provides functions to extract lemma forms from inflected words:
- Plural nouns → singular stem (կատուներ → կատու)
- Conjugated verbs → infinitive (վազեր → վազել)  
- Case-marked nouns → nominative stem
- All inflected variants for matching
- Monosyllabic root alternants (e.g. գիր/գր, սէր/սիր) from 200 Monosyllabic Words

Uses the morphology module for full declension/conjugation support.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Set, Optional, Dict

logger = logging.getLogger(__name__)

try:
    from . import (
        ARM, 
        detect_noun_class, detect_verb_class,
        decline_noun, conjugate_verb
    )
    MORPHOLOGY_AVAILABLE = True
except ImportError:
    MORPHOLOGY_AVAILABLE = False
    ARM = None  # type: ignore[assignment]
    detect_noun_class = None  # type: ignore[assignment]
    detect_verb_class = None  # type: ignore[assignment]
    decline_noun = None  # type: ignore[assignment]
    conjugate_verb = None  # type: ignore[assignment]


def _load_monosyllabic_roots() -> tuple[Set[str], Dict[str, Set[str]]]:
    """Load data/monosyllabic_roots.json (200 Monosyllabic Words — Fr. Ghevond Ajamian).
    Returns (all_forms_set, form_to_alternants_map). Empty if file missing or invalid.
    """
    root_forms: Set[str] = set()
    alternants: Dict[str, Set[str]] = {}
    try:
        # Project layout places the top-level `data/` next to the package dir.
        # Path(__file__).parent.parent.parent points to hytools/hytools; we need
        # the repository root (hytools/) so go up one more level.
        data_dir = Path(__file__).resolve().parents[3] / "data"
        path = data_dir / "monosyllabic_roots.json"
        if not path.exists():
            return root_forms, alternants
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for entry in data.get("roots", []):
            forms = entry.get("forms") or []
            if not forms:
                continue
            normalized = [f.strip().lower() for f in forms if isinstance(f, str) and f.strip()]
            if not normalized:
                continue
            group = set(normalized)
            root_forms.update(group)
            for form in group:
                alternants[form] = group
    except Exception:
        logger.debug("Failed to load monosyllabic roots from %s", roots_path, exc_info=True)
    return root_forms, alternants


_ROOT_FORMS: Set[str] = set()
_ROOT_ALTERNANTS: Dict[str, Set[str]] = {}


def _ensure_roots_loaded() -> None:
    global _ROOT_FORMS, _ROOT_ALTERNANTS
    if _ROOT_ALTERNANTS:
        return
    _ROOT_FORMS, _ROOT_ALTERNANTS = _load_monosyllabic_roots()


def get_root_alternants(word: str) -> Set[str]:
    """Return all orthographic alternants of the same monosyllabic root, if the word is a known root.
    Source: 200 Monosyllabic Words (Fr. Ghevond Ajamian). E.g. get_root_alternants('գիր') -> {'գիր', 'գր'}.
    """
    _ensure_roots_loaded()
    w = (word or "").strip().lower()
    return set(_ROOT_ALTERNANTS.get(w, ()))

def _get_case_stem_candidates(word: str) -> Set[str]:
    """Return possible nominative stems by stripping common WA case endings.

    Targets endings requested by user and common plural case patterns:
      - sg gen-dat: -ի
      - sg gen-dat definite: -ին
      - sg ablative: -է
      - sg ablative definite: -էն
      - sg instrumental: -ով
      - pl gen-dat: -ների
      - pl gen-dat definite: -ներին
      - pl ablative: -ներէ
      - pl ablative definite: -ներէն
      - pl instrumental: -ներով
    """
    if not MORPHOLOGY_AVAILABLE:
        return set()
    if ARM is None:
        return set()

    candidates: Set[str] = set()
    w = word.lower()

    try:
        i = ARM["i"]
        e = ARM["e"]
        n = ARM["n"]
        vo = ARM["vo"]
        v = ARM["v"]
        ye = ARM["ye"]
        r = ARM["r"]
    except Exception:
        logger.debug("ARM dict key lookup failed in _get_case_stem_candidates", exc_info=True)
        return candidates

    # Base pieces
    ner = n + ye + r          # -ներ
    ov = vo + v               # -ով

    # Order matters: longest suffixes first
    suffixes = [
        ner + i + n,          # -ներին
        ner + e + n,          # -ներէն
        ner + ov,             # -ներով
        ner + i,              # -ների
        ner + e,              # -ներէ
        i + n,                # -ին
        e + n,                # -էն
        ov,                   # -ով
        i,                    # -ի
        e,                    # -է
    ]

    for suf in suffixes:
        if w.endswith(suf) and len(w) > len(suf) + 1:
            candidates.add(w[:-len(suf)])

    return candidates


def extract_plural_stem(word: str) -> Optional[str]:
    """Extract singular stem by removing plural suffix -ներ.
    
    Example: կատուներ → կատու
    
    Returns None if no suffix found, otherwise returns singular form.
    """
    if not MORPHOLOGY_AVAILABLE:
        # Fallback: manual -ner removal
        if word.endswith('ներ'):
            return word[:-3]
        return None
    
    if ARM is None:
        return None
    try:
        ner = ARM["n"] + ARM["ye"] + ARM["r"]  # -ner
        if word.endswith(ner):
            return word[:-len(ner)]
    except Exception:
        logger.debug("ARM dict key lookup failed in extract_plural_stem", exc_info=True)
    
    return None


def get_noun_lemmas(word: str) -> Set[str]:
    """Generate all declension forms for a noun.
    
    Includes nominative, accusative, genitive-dative, ablative,
    instrumental cases in both singular and plural.
    
    Returns set of all possible forms.
    """
    lemmas = {word.lower()}  # Always include original as lowercase
    
    if not MORPHOLOGY_AVAILABLE:
        return lemmas
    if detect_noun_class is None or decline_noun is None:
        return lemmas
    try:
        noun_class = detect_noun_class(word)
        decl = decline_noun(word, declension_class=noun_class)
        
        # Collect all accessible forms
        for attr in dir(decl):
            if not attr.startswith('_'):
                value = getattr(decl, attr)
                if isinstance(value, str) and value:
                    lemmas.add(value.lower())
    except Exception as e:
        # If declension fails, just return original
        pass
    
    return lemmas


def get_verb_lemmas(word: str) -> Set[str]:
    """Generate all conjugation forms for a verb.
    
    Includes infinitive and various tenses/moods.
    
    Returns set of all possible forms.
    """
    lemmas = {word.lower()}  # Always include original as lowercase
    
    if not MORPHOLOGY_AVAILABLE:
        return lemmas
    if detect_verb_class is None or conjugate_verb is None:
        return lemmas
    try:
        verb_class = detect_verb_class(word)
        conj = conjugate_verb(word, verb_class=verb_class)
        
        # Collect all accessible forms
        for attr in dir(conj):
            if not attr.startswith('_'):
                value = getattr(conj, attr)
                if isinstance(value, str) and value:
                    lemmas.add(value.lower())
                elif isinstance(value, dict):
                    # Handle subjunctive, indicative, etc. which are dicts
                    for form in value.values():
                        if isinstance(form, str) and form:
                            lemmas.add(form.lower())
    except Exception as e:
        # If conjugation fails, just return original
        pass
    
    return lemmas


def get_all_lemmas(word: str) -> Set[str]:
    """Get all possible lemma forms for a word.
    
    Returns a set of all inflected/declined variants that could match
    the word in different morphological contexts.
    
    Includes:
    - Original word (lowercased)
    - Noun declension forms (all cases, singular & plural)
    - Verb conjugation forms (all tenses & moods)
    - Manual plural removal fallback
    
    Args:
        word: Armenian word (any case)
    
    Returns:
        Set of lowercase lemma forms
    """
    lemmas = {word.lower()}  # Always include original
    
    # Try noun declension
    noun_lemmas = get_noun_lemmas(word)
    lemmas.update(noun_lemmas)
    
    # Try verb conjugation
    verb_lemmas = get_verb_lemmas(word)
    lemmas.update(verb_lemmas)
    
    # Manual plural stem extraction (fallback)
    plural_stem = extract_plural_stem(word)
    if plural_stem:
        lemmas.add(plural_stem.lower())

    # Reverse case-ending stripping (critical for -ի/-ին/-է/-էն/-ով forms)
    lemmas.update(_get_case_stem_candidates(word))

    # Monosyllabic root alternants: if word is a known root (e.g. գիր, գր), add all alternants
    _ensure_roots_loaded()
    w_lower = word.strip().lower()
    if w_lower in _ROOT_FORMS:
        lemmas.update(_ROOT_ALTERNANTS.get(w_lower, set()))
    
    return lemmas


def match_word_with_stemming(vocab_word: str, corpus_words: Set[str]) -> tuple[bool, str]:
    """Match a vocabulary word to corpus using stemming/lemmatization.
    
    First tries exact match, then falls back to lemma-based matching.
    
    Args:
        vocab_word: A vocabulary word (any case)
        corpus_words: Set of corpus words (lowercased)
    
    Returns:
        (matched: bool, match_type: str) where:
          - matched: True if found in corpus (exact or lemma)
          - match_type: "exact", "lemma", or "no_match"
    
    Examples:
        >>> corpus = {"կատու", "վազել"}
        >>> match_word_with_stemming("կատուներ", corpus)
        (True, "lemma")  # Found կատու via singular lemma
        
        >>> match_word_with_stemming("կատու", corpus)
        (True, "exact")  # Direct match
    """
    word_lower = vocab_word.lower()
    
    # Check 1: Exact match
    if word_lower in corpus_words:
        return True, "exact"
    
    # Check 2: Lemma-based match
    lemmas = get_all_lemmas(vocab_word)
    for lemma_form in lemmas:
        if lemma_form != word_lower and lemma_form in corpus_words:
            # Found a matching lemma form (inflection of this word)
            return True, "lemma"
    
    return False, "no_match"


def get_lemmatization_stats(vocab_word: str, corpus_words: Set[str]) -> dict:
    """Detailed breakdown of lemmatization attempt for a word.
    
    Returns a dict with:
    - word: original word
    - exact_match: bool
    - lemma_count: how many lemmas were generated
    - matching_lemmas: list of which lemmas matched corpus
    - match_type: "exact", "lemma", or "no_match"
    
    Useful for debugging and understanding stemming decisions.
    """
    word_lower = vocab_word.lower()
    
    result = {
        'word': vocab_word,
        'word_lower': word_lower,
        'exact_match': word_lower in corpus_words,
        'lemmas_generated': list(get_all_lemmas(vocab_word)),
        'matching_lemmas': [],
        'match_type': 'no_match'
    }
    
    if result['exact_match']:
        result['match_type'] = 'exact'
    else:
        # Check which lemmas match
        for lemma in result['lemmas_generated']:
            if lemma != word_lower and lemma in corpus_words:
                result['matching_lemmas'].append(lemma)
        
        if result['matching_lemmas']:
            result['match_type'] = 'lemma'
    
    return result
