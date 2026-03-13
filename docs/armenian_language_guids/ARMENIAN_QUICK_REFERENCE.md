# Armenian Quick Reference Card

**For quick lookup during implementation. For complete details see comprehensive guides at project root.**

## ⚠️ CRITICAL: The Voicing Reversal (START HERE)

Western Armenian has **BACKWARDS VOICING** — letter appearance ≠ pronunciation:

| Letter | Looks Like | Actually Sounds Like | Example |
|--------|-----------|----------------------|---------|
| **բ** | voiced p | **p** (unvoiced) | բան = pahn |
| **պ** | unvoiced b | **b** (voiced) | պետք = bedk |
| **դ** | voiced t | **t** (unvoiced) | դուռ = toor |
| **տ** | unvoiced d | **d** (voiced) | տուն = doon |
| **գ** | voiced k | **k** (unvoiced) | գիտ = keed |
| **կ** | unvoiced g | **g** (voiced) | կտուր = g'door |

**TEST WORD**: պետք = "bedk" (NOT "petik")  
If you get the [p] sound, you're using Eastern Armenian ❌

---

## Context-Aware Letters (Position Changes Pronunciation)

| Letter | Position | Sound | Example |
|--------|----------|-------|---------|
| **յ** | word start | h | յոյս = hoys |
| **յ** | word middle/end | y | բայ = pay |
| **ո** | before consonant | vo | ոչ = voch |
| **ո** | after consonant/as vowel | o (go) | կո = go |
| **ե** | word start | ye | ե = ye |
| **ե** | word middle/end | e | ե = e |
| **ւ** | between vowels | v~oo | (complex, see diphthongs) |

---

## Consonant Quick Map

Use these in both directions. Keep spelling in classical Western Armenian.

### Sound -> Letter

| Sound | Western | NOT | Notes |
|-------|---------|-----|-------|
| p | բ | պ | Remember: opposite of appearance |
| b | պ | բ | Remember: opposite of appearance |
| t | դ | տ | Remember: opposite of appearance |
| d | տ | դ | Remember: opposite of appearance |
| k | գ | կ | Remember: opposite of appearance |
| g | կ | գ | Remember: opposite of appearance |
| j (like "job") | ճ | ջ | ճ is voiced affricate [dʒ] |
| ch (like "chop") | ջ/չ | ճ | ջ and չ both map to [tʃ] |
| ts | ց | - | |
| dz | ծ | - | |
| sh | շ | - | |
| zh | ժ | - | |
| s | ս | - | |
| t (regular) | թ | th | NOT "th" sound — just regular t |
| r (flap) | ր | - | Like English "better" |
| r (trill) | ռ | - | Spanish rolled r |
| f | ֆ | - | |
| h | հ | - | |
| kh (guttural) | խ | - | Difficult (difficulty 4) |
| voiced gh | ղ | - | Difficult (difficulty 4) |
| m | մ | - | |
| n | ն | - | |
| l | լ | - | |

### Letter -> Sound

| Western Letter | Sound | Common Wrong Read |
|----------------|-------|-------------------|
| բ | p | b |
| պ | b | p |
| դ | t | d |
| տ | d | t |
| գ | k | g |
| կ | g | k |
| ճ | j ([dʒ]) | ch ([tʃ]) |
| ջ | ch ([tʃ]) | j ([dʒ]) |
| չ | ch ([tʃ]) | j ([dʒ]) |
| ց | ts | - |
| ծ | dz | - |
| շ | sh | - |
| ժ | zh | - |
| ս | s | - |
| թ | t | th |
| ր | r (flap) | - |
| ռ | r (trill) | - |
| ֆ | f | - |
| հ | h | - |
| խ | kh | - |
| ղ | gh | - |
| մ | m | - |
| ն | n | - |
| լ | l | - |

---

## Vowels (Complete Set)

| Letter | Sound | Example |
|--------|-------|---------|
| **ա** | a (father) | ամ = am |
| **ե** | e (bed) or ye* | (context) |
| **ի** | i (fleece) | իմ = im |
| **ո** | o (go) or vo* | (context) |
| **օ** | o (go) | օր = or |

*Context-dependent, see above

**NOTE**: ւ is NOT a standalone vowel!

---

## Diphthongs (Two-Letter Vowel Combos)

| Pair | Sound | Example |
|------|-------|---------|
| **ու** | oo | ուր = oor (where) |
| **իւ** | yoo | իւղ = yoogh (oil), իւր/իր = yur/ir |
| **եա** | e-a (IPA: ɛɑ) | See `02-src/lousardzag/phonetics.py` (`DIPHTHONG_SOUND_IPA`) |
| **ոյ** | o / ooy (IPA: uj, context-dependent) | Word-final: `o`; before consonant: `ooy` |
| **այ** | ai (IPA: aj) | See `02-src/lousardzag/phonetics.py` (`DIPHTHONG_SOUND_IPA`) |

---

## Test Words (Verify Your Phonetics)

Use these to check if you're using Western Armenian (correct) or Eastern (wrong):

```
Correct (Western Armenian):
պետք → bedk (պ=b, տ=d)
ժամ → zham (ժ=zh like "azure")
ջուր → choor (ջ=tʃ like "ch")
ոչ → voch (ո=vo before consonant)
իւր → yur (իւ=yoo diphthong)

Wrong (Eastern Armenian - if you get these, STOP):
պետք → petik (wrong voicing)
ախամ → akham (a-kh-a-m, NOT jahm)
ջուր → jayur (wrong affricate)
թ → th (doesn't exist in Western)
```

---

## The WRONG Way ❌

```python
# EASTERN ARMENIAN (NOT THIS PROJECT)
mapping = {
    'բ': 'b',     # WRONG: Should be p
    'պ': 'p',     # WRONG: Should be b
    'դ': 'd',     # WRONG: Should be t
    'տ': 't',     # WRONG: Should be d
    'կ': 'k',     # WRONG: Should be g
    'գ': 'g',     # WRONG: Should be k
    'ճ': 'tʃ',    # WRONG: Should be dʒ
    'ջ': 'dʒ',    # WRONG: Should be tʃ
    'թ': 'θ',     # WRONG: Should be t (no "th" sound)
    'ե': 'ɛ',     # INCOMPLETE: Missing ye variant
    'ո': 'ɔ',     # INCOMPLETE: Missing v variant
    'յ': 'j',     # INCOMPLETE: Missing h variant
    'ւ': 'u',     # INCOMPLETE: Missing v variant
    'է': ...,     # WRONG: Eastern only, exclude!
}
```

---

## The RIGHT Way ✅

```python
# WESTERN ARMENIAN (THIS PROJECT)
mapping = {
    'բ': {'ipa': 'p', 'english': 'p', ...},
    'պ': {'ipa': 'b', 'english': 'b', ...},
    'դ': {'ipa': 't', 'english': 't', ...},
    'տ': {'ipa': 'd', 'english': 'd', ...},
    'կ': {'ipa': 'g', 'english': 'g', ...},
    'գ': {'ipa': 'k', 'english': 'k', ...},
    'ճ': {'ipa': 'dʒ', 'english': 'j', ...},
    'ջ': {'ipa': 'tʃ', 'english': 'ch', ...},
    'թ': {'ipa': 't', 'english': 't', ...},
    'ե': {'ipa': 'ɛ~jɛ', 'english': 'e/ye', ...},  # Context-aware
    'ո': {'ipa': 'v~ɔ', 'english': 'vo/o', ...},  # Context-aware: vo or o
    'յ': {'ipa': 'j~h', 'english': 'y/h', ...},   # Context-aware
    'ւ': {'ipa': 'v~u', 'english': 'v/oo', ...},  # Context-aware
    # NO 'է' entry — Eastern Armenian only
}
```

---

## One-Sentence Summary

**Western Armenian voicing is backwards from letter appearance: բ/պ, դ/տ, κ/կ pairs are REVERSED. Test with պետք (bedk, not petik). Always verify before implementing.**

---

For complete details: See comprehensive guides at project root (WESTERN_ARMENIAN_PHONETICS_GUIDE.md, etc.)
