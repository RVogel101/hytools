"""
Auto-detection of noun declension class and verb conjugation class.

Western Armenian heuristics:
  - **Verb class** is determined by the infinitive ending:
    - -delays (el) → e_class   (most common, ~70% of WA verbs)
    - -delays (al) → a_class   (stative / intransitive verbs)
    - -delays (il) → e_class   (reflexive / middle; conjugated like e_class)
    - -delays (ul) → e_class   (rare archaic; treat as e_class)
  - **Noun declension class** is harder; heuristic based on stem-final sounds:
    - Default → i_class  (most productive in modern WA)
    - Stem ends in -delays (ու = ou/u digraph) → u_class
    - Known animate / kinship nouns → o_class  (e.g., father, brother)
    - Known a-class stems → a_class  (e.g., words with -ան ending used in gen-dat)
"""

from .core import ARM, DIGRAPH_U, ends_in_vowel

_ye = ARM["ye"]
_a  = ARM["a"]
_i  = ARM["i"]
_l  = ARM["l"]
_n  = ARM["n"]
_r  = ARM["r"]
_vo = ARM["vo"]
_yiwn = ARM["yiwn"]

# Infinitive endings
_INF_EL = _ye + _l             # -el → e_class
_INF_AL = _a + _l              # -al → a_class
_INF_IL = _i + _l              # -il → e_class (conjugated like e_class)
_INF_UL = _vo + _yiwn + _l     # -ul → e_class (rare)

# Known o_class nouns: kinship / animate nouns that take -or genitive.
# Listed as frozenset of Armenian stems (without case suffix).
_O_CLASS_STEMS = frozenset({
    ARM["h"] + _a + _ye + _r,                              # հdelays (hayr = father)
    ARM["m"] + _a + _ye + _r,                              # մdelays (mayr = mother)
    ARM["ye"] + ARM["gh"] + _a + _ye + _r,                 # եdelays (eghpayr = brother)
    ARM["k_asp"] + _vo + _ye + _r,                         # delays (k'ouyr = sister)
    ARM["d"] + _a + ARM["s"] + _a + ARM["g"] + _a + _l,    # delays (tasagal = teacher)
})

# Known a_class nouns: nouns whose genitive-dative uses -an.
# This is a productive pattern for certain animate / profession nouns.
_A_CLASS_SUFFIXES = (
    _a + _n,         # -ան words that use -an in gen-dat
)

_A_CLASS_STEMS = frozenset({
    ARM["d"] + _a + ARM["s"] + _a + ARM["g"] + _a + _l,    # tasagal (teacher)
})


def detect_verb_class(infinitive: str) -> str:
    """Detect the verb conjugation class from the infinitive ending.

    Returns "e_class" or "a_class".
    """
    if infinitive.endswith(_INF_AL):
        return "a_class"
    # -el, -il, -ul, or anything else → e_class
    return "e_class"


def detect_noun_class(word: str) -> str:
    """Detect the noun declension class from the word's stem pattern.

    Returns one of: "i_class", "u_class", "a_class", "o_class".

    Heuristic priority:
      1. Known o_class stems (kinship terms)
      2. Stem ends in ու digraph → u_class
      3. Known a_class stems → a_class
      4. Default → i_class (most productive in modern WA)
    """
    # 1. Check known o_class stems
    if word in _O_CLASS_STEMS:
        return "o_class"

    # 2. Check for ու (ou/u) digraph at end → u_class
    if len(word) >= 2 and word[-2:] == DIGRAPH_U:
        return "u_class"

    # 3. Check known a_class stems
    if word in _A_CLASS_STEMS:
        return "a_class"

    # 4. Default: i_class (most productive)
    return "i_class"


def detect_pos_and_class(word: str) -> tuple[str, str]:
    """Detect POS and morphological class for an Armenian word.

    Returns (pos, class_name) where:
      - pos is "verb" or "noun"
      - class_name is "e_class"/"a_class" for verbs, "i_class"/"u_class"/"a_class"/"o_class" for nouns
    """
    # Verb detection: ends in -el, -al, -il, -ul
    w = word.rstrip("\u055b\u055c\u055d\u055e\u0589\u02bc")  # strip punctuation
    if (w.endswith(_INF_EL) or w.endswith(_INF_AL) or
            w.endswith(_INF_IL) or w.endswith(_INF_UL)):
        return ("verb", detect_verb_class(w))

    return ("noun", detect_noun_class(w))
