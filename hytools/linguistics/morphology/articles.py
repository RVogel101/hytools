"""
Western Armenian article generation (definite and indefinite).

Western Armenian rules (WA dialect meanings and parsing):
  - Definite:   append -ը after consonant, -ը or -ն after vowel (based on orthographic harmony)
  - Indefinite: postposed մը (mə) as separate token

This module uses WA-specific morphology and avoids Eastern Armenian forms.
"""

from .core import ARM, ends_in_vowel


# ─── Article Markers ──────────────────────────────────────────────────
DEF_AFTER_CONSONANT = ARM["y_schwa"]   # ը (schwa) — appended after consonant (WA definite)
DEF_AFTER_VOWEL = ARM["n"]             # ն — appended after vowel (WA definite form)
INDEF_ARTICLE = ARM["m"] + ARM["y_schwa"]  # մը (mə) — postposed WA indefinite


def add_definite(word: str) -> str:
    """Add the Western Armenian definite article to a noun.

    Rules:
      - After a consonant: append ը (schwa) e.g. գիրք → գիրքը
      - After a vowel: append ն e.g. տուն → տունը
      - If word already has definite suffix, return as-is

    Examples:
      - գրք (girk', "book")    → գիրքը
      - տուն (tun, "house")     → տունը
      - մայր (mayr, "mother")   → մայրն (when the noun ends in vowel)
    """
    if not word:
        return word

    if ends_in_vowel(word):
        # After vowel → add ն (n)
        # Special case: if word already ends in ն, definite is the same word
        if word[-1] == ARM["n"]:
            return word
        return word + DEF_AFTER_VOWEL
    else:
        # After consonant → append ը (schwa)
        return word + DEF_AFTER_CONSONANT


def add_indefinite(word: str) -> str:
    """Add the Western Armenian indefinite article after the noun.

    The indefinite article is the postposed particle մը (mə).
    The noun stays unchanged, then a space and մը are appended.

    Examples:
      - գիրք (kirk', "book") → գիրք մը (kirk' mə, "a book")
      - տուն (tun, "house")   → տուն մը (tun mə, "a house")
    """
    if not word:
        return word
    return word + " " + INDEF_ARTICLE


def remove_definite(word: str) -> str:
    """Remove the definite article suffix if present.

    Strips trailing ը (ə) or ն (n) if added by definite article rules.
    Note: This is a heuristic — some nouns naturally end with these letters.
    """
    if not word:
        return word
    if word.endswith(DEF_AFTER_CONSONANT):
        return word[:-1]
    return word
