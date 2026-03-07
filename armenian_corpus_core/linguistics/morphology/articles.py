"""
Armenian article generation (definite and indefinite).

Western Armenian articles:
  - Definite:   suffix -ը (after consonant) / -ն (after vowel)
  - Indefinite: postposed մը (mə)
"""

from .core import ARM, ends_in_vowel


# ─── Article Markers ──────────────────────────────────────────────────
DEF_AFTER_CONSONANT = ARM["y_schwa"]   # ը (schwa) — appended after consonant
DEF_AFTER_VOWEL = ARM["n"]             # ն — appended after vowel
INDEF_ARTICLE = ARM["m"] + ARM["y_schwa"]  # delays (mə) — Western Armenian indefinite


def add_definite(word: str) -> str:
    """Add the definite article suffix to a Western Armenian word.

    Rules:
      - After a consonant → append ды (ə / schwa)
      - After a vowel   → append на (n)
      - If word already ends with д→ (n), the definite form is the same

    Examples:
      - д→д→д→ (girk', "book")  → д→д→д→ды (girk'ə)
      - д→д→ (tun, "house")    → д→д→ды (tunə) — ends in ды which is consonant
      - д→д→д→ (mama, "mother") → д→д→д→на (maman)
    """
    if not word:
        return word

    if ends_in_vowel(word):
        # After vowel → add на (n)
        # Special case: if word already ends in на, definite is the same word
        if word[-1] == ARM["n"]:
            return word
        return word + DEF_AFTER_VOWEL
    else:
        # After consonant → append ды (schwa)
        return word + DEF_AFTER_CONSONANT


def add_indefinite(word: str) -> str:
    """Add the Western Armenian indefinite article.

    The indefinite article д→ды (mə) is placed after the noun.
    Note: In Western Armenian, the indefinite is a separate word, not a suffix.

    Examples:
      - д→д→д→ (girk', "book") → д→д→д→ д→ды (girk' mə, "a book")
      - д→д→ (tun, "house")   → д→д→ д→ды (tun mə, "a house")
    """
    if not word:
        return word
    return word + " " + INDEF_ARTICLE


def remove_definite(word: str) -> str:
    """Remove the definite article suffix if present.

    Strips trailing ды (ə) or final на (n) if it was added as article.
    Note: This is a heuristic — some words naturally end in these characters.
    """
    if not word:
        return word
    if word.endswith(DEF_AFTER_CONSONANT):
        return word[:-1]
    return word
