# Western Armenian Phonetics Implementation Guide

**AUTHORITATIVE REFERENCE FOR ALL ARMENIAN PHONETIC WORK**

This document is the source of truth for Western Armenian phonetics in the Lousardzag project. Every phonetic implementation must reference this guide.

---

## Critical Principle: Voicing Reversal

**Western Armenian is unique among Armenian dialects: letter APPEARANCE has OPPOSITE voicing from PRONUNCIATION.**

This is architectural, not an exception. It appears in multiple unrelated letter pairs.

### What This Means
- Visual letter shape ≠ pronounced voicing
- "Looking voiced" (like բ) doesn't mean "sounds voiced"
- This is UNIQUE TO WESTERN ARMENIAN, not Eastern

### Memorization Tool
Think of it as **BACKWARDS from English expectations**:
- բ (looks like voiced "b" shape) → actually [p] sound (like English "pat")
- պ (looks like unvoiced "p" shape) → actually [b] sound (like English "bat")

---

## Complete Western Armenian Phoneme Map (38 Letters)

### Unaspirated Stop Pairs (VOICING REVERSED)

| Letter | Looks Like | IPA | English | Example | Difficulty | Notes |
|--------|-----------|-----|---------|---------|------------|-------|
| **բ** | voiced p | p | pat | բան (pahn) | 1 | REVERSED from appearance |
| **պ** | unvoiced b | b | bat | պետք (bedk) | 1 | REVERSED from appearance |
| **դ** | voiced t | t | top | դուռ (toor) | 1 | REVERSED from appearance |
| **տ** | unvoiced d | d | dog | տուն (doon) | 1 | REVERSED from appearance |

### Velar Pairs (VOICING REVERSED)

| Letter | Looks Like | IPA | English | Example | Difficulty | Notes |
|--------|-----------|-----|---------|---------|------------|-------|
| **գ** | voiced k | k | kit | գիտ (keed) | 1 | REVERSED from appearance |
| **կ** | unvoiced g | g | go | կտուր (g'door) | 1 | REVERSED from appearance |

### Affricate Pairs (CRITICAL: Easy to Confuse)

| Letter | IPA | English | Word | Difficulty | Notes |
|--------|-----|---------|------|------------|-------|
| **ժ** | ʒ | zh (azure) | ժամ (zham) | 1 | Voiced postalveolar fricative, sounds like "zh" in "azure" |
| **ջ** | tʃ | ch (chop) | ջուր (choor) | 1 | Unvoiced affricate, sounds like English "ch" |
| **չ** | tʃ | ch (chop) | չեն (chen) | 1 | Alternative spelling for tʃ sound |

**CRITICAL DISTINCTION**: Western Armenian ճ = [dʒ] like "j" in "job" (NOT "ch")

### Fricatives & Other Consonants

| Letter | IPA | English | Word | Difficulty | Notes |
|--------|-----|---------|------|------------|-------|
| **ծ** | dz | dz | ծանի (dzani) | 2 | Voiced affricate (like "adze") |
| **ց** | ts | ts | ցանց (tsants) | 2 | Unvoiced affricate |
| **ժ** | ʒ | zh | ժամ (zham) | 2 | Voiced fricative |
| **շ** | ʃ | sh | շատ (shad) | 1 | Unvoiced fricative |
| **ս** | s | s | սառ (sar) | 1 | Unvoiced alveolar fricative |
| **ր** | ɾ | r (flap) | (better) | 2 | Flapped r, like English "better" |
| **ռ** | r | r (trill) | Spanish r | 3 | Trilled r (more difficult) |
| **ֆ** | f | f | ֆլ (fl) | 1 | Labiodental fricative |
| **խ** | x | kh (guttural) | խաղ (khagh) | 4 | Velar fricative (GUTTURAL) |
| **ղ** | ɣ | gh (voiced) | ղանճ (ghanj) | 4 | Voiced velar fricative (GUTTURAL) |
| **հ** | h | h | հայ (hay) | 1 | Glottal fricative |

### Nasals and Liquids

| Letter | IPA | English | Word | Difficulty | Notes |
|--------|-----|---------|------|------------|-------|
| **մ** | m | m | մարդ (mart) | 1 | Labial nasal |
| **ն** | n | n | նոր (nor) | 1 | Alveolar nasal |
| **լ** | l | l | լեզու (lezoo) | 1 | Alveolar lateral |

### Glides and Context-Aware Letters

| Letter | Phoneme Context | IPA | English | Word | Difficulty | Notes |
|--------|-----------------|-----|---------|------|------------|-------|
| **յ** | Word-initial | h | hat | յոյս (hoys) | 1 | At word start sounds like "h" |
| **յ** | Word-medial/final | j | yes | բայ (pay) | 1 | In middle/end sounds like "y" |
| **ո** | Before consonant | vo | vo- | ոչ (voch) | 2 | Before consonants = [vo] onset |
| **ո** | After consonant/as vowel | o | go | կո (go) | 2 | As vowel after consonant = [o] |
| **ւ** | In diphthongs | u | oo | ու (u) | 1 | Part of ու diphthong |
| **ւ** | Between vowels | v | vet | այւ (ayv) | 1 | Between vowels = [v] sound |

### Full Vowel Set (Complete)

| Letter | IPA | English | Word | Difficulty | Notes |
|--------|-----|---------|------|------------|-------|
| **ա** | ɑ | father | ամ (am) | 1 | Open back unrounded vowel |
| **ե** | ɛ~jɛ | e/ye | (varies) | 1 | Context-dependent (see below) |
| **ի** | i | fleece | իմ (im) | 1 | Close front unrounded vowel |
| **ո** | o~vo | o/vo | (varies) | 2 | Context-dependent (see above) |
| **օ** | o | go | օր (or) | 1 | Close back rounded vowel |

**IMPORTANT**: 
- ե changes by position (ye at word start, e in middle)
- ո changes by position (vo before consonants, o elsewhere)
- ւ is NOT a vowel by itself (only vowel in diphthongs)
- EXCLUDE: է is Eastern Armenian, never use in Western

### Diphthongs (Two-Letter Vowel Combinations)

| Pair | IPA | English | Example | Difficulty | Notes |
|------|-----|---------|---------|------------|-------|
| **ու** | u | oo (goose) | ուր (oor = where) | 1 | First element ո (v-colored) + second ո |
| **իւ** | ju | yoo (you) | իւր (yur) | 1 | First element ի + second ու |

**Critical Note**: ւ is only a vowel when part of these diphthongs. Elsewhere it's a consonant [v] or part of a diphthong.

---

## Context-Aware Pronunciation Rules

### Letter յ (Y/H) - Two Pronunciations

**Word-Initial Position**: Pronounced as [h] (like English "hat")
- Example: յոյս = [hoys] (hope)
- Note: Sounds like starting "h", not "y"

**Word-Medial or Word-Final**: Pronounced as [j] (like English "yes")
- Example: բայ = [pay] (but, "pa-y")
- Note: Acts as glide/consonant between vowels

**Implementation**: Check character position in word; apply [h] at index 0, [j] elsewhere

### Letter ո (O/V) - Two Pronunciations

**Before Consonants (Including Word-Initial)**: Pronounced as [vo]
- Example: ոչ = [voch] (no)
- Example: որ = [vor] (who, before ր consonant)
- Note: Even in Armenian words, check if next char is consonant

**After Consonant or As Standalone Vowel**: Pronounced as [o] (like English "go")
- Example: կո = [go] (after consonant կ)
- Example: որբ = [vorp] (first ո before consonant, so [vo])

**Implementation**: Check if next character is consonant; if yes use [vo], else [o]

### Letter ե (E/YE) - Two Pronunciations

**Word-Initial Position**: Pronounced as [jɛ] (like "ye" in yes)
- Example: եղջ = [yeghch] (starting with ye sound)
- Note: Sometimes written with glide marker, sometimes not

**Word-Medial or Word-Final**: Pronounced as [ɛ] (like English "bed")
- Example: բե = [pe] (in middle)
- Note: Short vowel, clean "e" sound

**Implementation**: Check character position; [jɛ] at index 0, [ɛ] elsewhere

### Letter ւ (V/OO) - Three Contexts

**In Diphthongs (ու, իւ)**: Part of vowel combination
- ու = [u] (like oo in goose)
- իւ = [ju] (like yoo in "you")
- Note: Check if preceded by vowel that forms digraph

**Between Vowels (Not in Digraph)**: Pronounced as [v] (like English "vet")
- Example: այւ = [ayv] (and)
- Note: Between vowels but NOT a diphthong

**Standalone (Rare)**: Usually not standalone in native words

**Implementation**: Check if part of known digraph first (ու, իւ); if yes apply digraph rule; if between consonant and vowel, apply [v]

---

## Difficulty Scoring (1-5 Scale)

### Base Difficulty Assignment

| Difficulty | Phonemes | Characteristics |
|------------|----------|-----------------|
| **1** | բ, պ, դ, տ, գ, կ, շ, ս, ա, ե, ի, օ, յ, մ, ն, լ, ֆ, հ, ջ, ճ | Common, easy to pronounce for English speakers |
| **2** | ծ, ց, ժ, ր, ո, ու, իւ | Less common, require practice |
| **3** | ռ | Trill r is difficult (Spanish-style rolling) |
| **4** | խ, ղ | Guttural consonants (French/German-style) |
| **5** | (varies by combination) | Clusters of difficult phonemes |

### Automatic Boost Rules

Words containing **guttural consonants** (խ, ղ) automatically get:
- **+1 to base difficulty** (so minimum 2) 
- These sounds are notoriously difficult for English speakers

### Word-Level Scoring (Entire Word)

1. Calculate base score from phoneme difficulties
2. Take maximum difficulty in word (not average)
3. Apply guttural boost if word has խ or ղ
4. Cap at 5.0
5. Round to 1 decimal place

Example:
- բան (simple) = 1 (all base-1 phonemes)
- շատ (has շ) = 1 (all easy)
- խաղ (has խ guttural) = 4 (base difficulty on խ is 4)

---

## Common Mistakes to Avoid (Checklist)

### ❌ Mistake: Eastern Armenian Phoneme Values

**Wrong** (if you see these, STOP immediately):
```python
{
    'բ': 'b',      # WRONG: reversed
    'պ': 'p',      # WRONG: reversed
    'դ': 'd',      # WRONG: reversed
    'տ': 't',      # WRONG: reversed
    'կ': 'k',      # WRONG: reversed
    'գ': 'g',      # WRONG: reversed
    'ճ': 'tʃ',     # WRONG: should be dʒ
    'ջ': 'dʒ',     # WRONG: should be tʃ
    'թ': 'θ',      # WRONG: should be t (no "th")
    'ե': 'ɛ',      # INCOMPLETE: missing ye variant
    'ո': 'ɔ',      # INCOMPLETE: missing v variant
    'յ': 'j',      # INCOMPLETE: missing h variant
    'ւ': 'u',      # INCOMPLETE: missing v variant
    'է': '...',    # WRONG: Eastern only
}
```

**Override**: Fix all voicing-reversed pairs immediately

### ❌ Mistake: Confusing ճ and ջ

**Wrong**:
- ճ = [tʃ] (ch sound) — NO!
- ջ = [dʒ] (j sound) — NO!

**Correct**:
- ճ = [dʒ] (j sound, like "job")
- ջ = [tʃ] (ch sound, like "chop")

**Memory aid**: ճ has MORE strokes (looks complex) → complex sound [dʒ]

### ❌ Mistake: Treating թ as "TH"

**Wrong**: թ = [θ] (like English "th")  
**Correct**: թ = [t] (regular t, like "top")

**Why**: "TH" sound doesn't exist in Western Armenian. Aspirated stops are unvoiced/voiced alveolars depending on context.

### ❌ Mistake: Treating ւ as Always a Vowel

**Wrong**: Mapping ւ → [u] in all contexts  
**Correct**: ւ → [u] in diphthongs, [v] between vowels, absent in clusters

Example: իւր = [yur] (diphthong իւ = [ju]), NOT [i][v][ɾ]

### ❌ Mistake: Ignoring Context for ո, ե, յ

**Wrong**: Always apply same IPA regardless of position  
**Correct**: Context-dependent — check position and surrounding letters

Test words:
- ո before consonant: ոչ = [voch] (not [ɔch])
- ե after consonant: կե = [ke] (not [kje])
- իւ diphthong: իւղ = [yoogh] (not [i-v-gh])

### ❌ Mistake: Missing Digraphs

**Wrong**: Processing ու as [u] + [u] separately  
**Correct**: Recognize ու combination first, apply [u] to entire digraph

Example: ուր should be processed as DIGRAPH ու + single ր, not ո + ո + ր

---

## Implementation Checklist

**Before implementing or modifying ANY phonetic code**, verify all of these:

- [ ] Verify you're targeting WESTERN ARMENIAN, not Eastern
- [ ] Verify voicing pairs are REVERSED (բ=p, պ=b, δ=t, տ=d, գ=k, կ=g)
- [ ] Verify ճ = [dʒ] (j sound, not ch)
- [ ] Verify ջ = [tʃ] (ch sound, not j)
- [ ] Verify թ = [t] (not th)
- [ ] Context-aware letters (ո, ե, յ, ւ) have position-dependent pronunciation documented
- [ ] Vowel set is ա, ե, ի, ո, օ (NOT ւ, NOT է)
- [ ] Diphthongs section includes ու and իւ
- [ ] Difficulty scores: base 1-5, guttural boost included
- [ ] All comments explicitly say "Western Armenian"
- [ ] No Eastern Armenian artifacts in code (no թ=θ, no կ=k, etc.)
- [ ] Test words work: պետք=bedk, ժամ=zham, ջուր=choor, ոչ=voch, իւր=yur

---

## Testing Guide

### Quick Verification (5 test words)

```python
from lousardzag.phonetics import get_phonetic_transcription

test_words = {
    'պետք': 'bedk',        # պ=b, տ=d (reversed)
    'ժամ': 'zham',          # ժ=ʒ (zh sound)
    'ջուր': 'choor',         # ջ=tʃ (ch sound)
    'ոչ': 'voch',           # ո at start = vo
    'իւր': 'yur',           # իւ = yu diphthong
}

for word, expected in test_words.items():
    result = get_phonetic_transcription(word)
    print(f"{word} → {result['english_approx']} (expected: {expected})")
    if result['english_approx'] != expected:
        print(f"  ❌ MISMATCH! Using Eastern Armenian?")
```

### IPA Verification

```python
from lousardzag.phonetics import ARMENIAN_PHONEMES

# Check voicing-reversed pairs
assert ARMENIAN_PHONEMES['բ']['ipa'] == 'p'  # NOT 'b'
assert ARMENIAN_PHONEMES['պ']['ipa'] == 'b'  # NOT 'p'
assert ARMENIAN_PHONEMES['դ']['ipa'] == 't'  # NOT 'd'
assert ARMENIAN_PHONEMES['տ']['ipa'] == 'd'  # NOT 't'
assert ARMENIAN_PHONEMES['գ']['ipa'] == 'k'  # NOT 'g'
assert ARMENIAN_PHONEMES['կ']['ipa'] == 'g'  # NOT 'k'

# Check affricates
assert ARMENIAN_PHONEMES['ճ']['ipa'] == 'dʒ'  # NOT 'tʃ'
assert ARMENIAN_PHONEMES['ջ']['ipa'] == 'tʃ'  # NOT 'dʒ'

# Check special letters
assert ARMENIAN_PHONEMES['թ']['ipa'] == 't'   # NOT 'θ'

print("✅ All assertion checks passed!")
```

### Regression Testing

After any phonetic change:
```bash
python -m pytest 04-tests/unit/test_difficulty.py -v
python -m pytest 04-tests/integration/test_transliteration.py -v
```

Should have 0 failures.

---

## Related Files & References

### Implementation Files
- **02-src/lousardzag/phonetics.py** (200+ lines)
  - ARMENIAN_PHONEMES dict
  - ARMENIAN_DIGRAPHS dict
  - get_phonetic_transcription() function
  - calculate_phonetic_difficulty() function

### Reference Files
- **ARMENIAN_QUICK_REFERENCE.md** (Quick lookup card)
- **CLASSICAL_ORTHOGRAPHY_GUIDE.md** (Classical spelling requirements)
- **/memories/western-armenian-requirement.md** (Persistent memory)

### Test Files
- **04-tests/integration/test_transliteration.py** (60+ test cases)
- **04-tests/unit/test_difficulty.py** (28+ test cases)

### Usage Files
- **07-tools/gen_vocab_simple.py** (Uses phonetic module)
- **08-data/vocab_n_standard.csv** (Output with IPA column)

---

## Version History

| Date | Version | Change |
|------|---------|--------|
| 2026-03-02 | 1.0 | Complete 38-letter phoneme map with voicing reversal principle documented |
| 2026-03-03 | 1.1 | Assessment created; context-aware implementation pending |

---

## Final Note

**This guide is the source of truth for all Western Armenian phonetic work in Lousardzag.**

If you find a discrepancy between this guide and the implementation code:
1. **Assume the guide is correct**
2. **Fix the code to match this guide**
3. **Add a regression test to prevent recurrence**
4. **Commit with clear explanation of the fix**

The voicing reversal principle is architectural. It cannot be simplified or bypassed.

---

**Last Updated**: March 3, 2026  
**Status**: AUTHORITATIVE REFERENCE  
**Dialect**: Western Armenian (Արևմտյան հայերեն)
