# NFC and Ligature Decomposition — In-Depth Guide

This document explains **Unicode NFC normalization** and **Armenian ligature decomposition** as used in armenian-corpus-core for consistent tokenization, frequency counts, and loanword lookup. The pipeline is implemented in `cleaning/armenian_tokenizer.py`.

---

## 1. Unicode normalization (NFC)

### What is NFC?

**NFC** stands for **Canonical Decomposition, followed by Canonical Composition** (Unicode Standard Annex #15). It is one of four Unicode normalization forms:

| Form | Description | Use case |
|------|-------------|----------|
| **NFD** | Canonical Decomposition | Decompose accented characters into base + combining mark (e.g. é → e + ́) |
| **NFC** | NFD then recompose | Preferred for storage and comparison; “composed” form |
| **NFKD** | Compatibility Decomposition | Broader decomposition (e.g. ligatures, compatibility variants) |
| **NFKC** | NFKD then recompose | Stronger normalization; can change meaning in some scripts |

**NFC** ensures that characters that can be represented as a single codepoint (e.g. **é** = U+00E9) are stored in that **composed** form, rather than as base + combining character (e.g. **e** + U+0301). That way, string comparison and hashing behave consistently regardless of how the text was typed or imported.

### Why use NFC for Armenian?

- **Consistency:** Different keyboards or sources may produce the same visual character via different codepoint sequences. NFC reduces that variation so that “the same word” has a single binary representation.
- **Deduplication and hashing:** Content hashes (e.g. for deduplication) and word counts should not depend on accidental NFD vs NFC form.
- **Lookup:** Lexicons (e.g. loanword sets, etymology DB) store words in NFC so that tokenized text (also normalized to NFC) matches.

### How we use it

In `cleaning/armenian_tokenizer.normalize()`:

```python
import unicodedata
text = unicodedata.normalize("NFC", text)
```

This is applied to raw text **before** ligature decomposition and lowercase, so that all downstream steps (regex word extraction, frequency counts, loanword detection) see a single, stable form.

### What NFC does *not* do

- **Ligatures:** Armenian presentation-form ligatures (e.g. U+FB13 ﬓ) are **not** decomposed by NFC. They are in the “compatibility” space, so we handle them explicitly (see below).
- **Case:** NFC does not change case. We apply Armenian-specific lowercase after NFC.
- **Spelling:** NFC does not convert between Western and Eastern Armenian spelling (e.g. իւ vs յու).

---

## 2. Armenian ligature decomposition

### What are Armenian ligatures?

In Unicode, Armenian has a small block of **presentation-form ligatures** at U+FB13–U+FB17. These are single glyphs that represent two letters joined for typographic style (e.g. in fonts that show մն as ﬓ). For corpus work we want **one canonical form**: the sequence of two underlying letters, so that word boundaries and string matching are independent of font.

| Codepoint | Name | Decomposed to | Meaning |
|-----------|------|----------------|---------|
| U+FB13 | ARMENIAN SMALL LIGATURE MEN NOW | U+0574 U+0576 | մն (m + n) |
| U+FB14 | ARMENIAN SMALL LIGATURE MEN ECH | U+0574 U+0565 | մե (m + e) |
| U+FB15 | ARMENIAN SMALL LIGATURE MEN INI | U+0574 U+056B | մի (m + i) |
| U+FB16 | ARMENIAN SMALL LIGATURE VEW NOW | U+057E U+0576 | վն (v + n) |
| U+FB17 | ARMENIAN SMALL LIGATURE MEN XEH | U+0574 U+056D | մխ (m + kh) |

All five are **lowercase** presentation forms. Uppercase ligatures exist in the range U+FB13–U+FB17 in some fonts, but the Unicode standard defines these as the Armenian ligature block; we decompose them to the two-letter sequence and then apply Armenian lowercase to the whole string so that casing is consistent.

### Why decompose?

1. **Tokenization:** Our word regex matches `[\u0531-\u0556\u0561-\u0587\uFB13-\uFB17]+`. If we left ligatures as single characters, “word” identity would depend on whether the source text used ﬓ or մն. Decomposing to մն ensures the same word form everywhere.
2. **Lexicons and search:** Loanword lists and etymology DB store words in decomposed form (e.g. **մն**), so that a tokenized token (after normalization) matches.
3. **Reproducibility:** Two documents that differ only in ligature vs. decomposed form should be treated as identical for word counts and hashing.

### Implementation

In `cleaning/armenian_tokenizer`:

```python
_LIGATURE_MAP = {
    "\uFB13": "\u0574\u0576",  # ﬓ → մն
    "\uFB14": "\u0574\u0565",  # ﬔ → մե
    "\uFB15": "\u0574\u056B",  # ﬕ → մի
    "\uFB16": "\u057E\u0576",  # ﬖ → վն
    "\uFB17": "\u0574\u056D",  # ﬗ → մխ
}

def decompose_ligatures(text: str) -> str:
    for lig, decomposed in _LIGATURE_MAP.items():
        text = text.replace(lig, decomposed)
    return text
```

The full pipeline is: **NFC → decompose_ligatures → armenian_lowercase**. So “ﬓ” becomes “մն”, and if the string had uppercase Armenian, it becomes lowercase after the third step.

### Relation to NFKC

Unicode **NFKC** also decomposes these ligatures (they are compatibility characters). We do **not** use NFKC for the whole string because:

- NFKC can change other characters in ways we don’t want (e.g. compatibility digits, symbols).
- We only want to normalize Armenian script; we prefer an explicit, minimal step (NFC + our ligature map + our lowercase) so behavior is predictable and documented.

---

## 3. Order of operations

The tokenizer applies, in order:

1. **NFC** — canonical composition so that equivalent sequences collapse to one form.
2. **Ligature decomposition** — replace U+FB13–U+FB17 with the corresponding two-letter sequences.
3. **Armenian lowercase** — map uppercase (U+0531–U+0556) to lowercase (U+0561–U+0587) by a fixed offset (0x30).
4. **Word extraction** — regex over Armenian script (and, if present, ligatures) to produce a list of tokens.

So every token coming out of `extract_words()` is NFC, decomposed, and lowercase. Any component that builds lexicons (e.g. loanword_tracker, etymology import) must store words in the same form so that lookup matches.

---

## 4. References

- Unicode Standard Annex #15: Unicode Normalization Forms  
  https://unicode.org/reports/tr15/
- Unicode Armenian block: U+0530–U+058F  
  https://unicode.org/charts/PDF/U0530.pdf
- Armenian ligatures: U+FB13–U+FB17 (Armenian subset of Alphabetic Presentation Forms)  
  https://unicode.org/charts/PDF/UFB00.pdf
- `cleaning/armenian_tokenizer.py` — implementation used across corpus-core
