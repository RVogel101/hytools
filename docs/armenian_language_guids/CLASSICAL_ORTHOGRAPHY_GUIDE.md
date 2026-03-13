# Classical Western Armenian Orthography Guide

**CRITICAL REQUIREMENT: Always use classical orthography, never reformed spelling**

This document establishes the requirement to use classical Western Armenian orthography (pre-1920s) for ALL words in this project, even when pronunciation is identical between Eastern and Western dialects.

---

## Core Principle

**This project uses CLASSICAL ORTHOGRAPHY exclusively.**

Classical orthography (Արևմտահայերէն դասական ուղղագրութիւն) is the traditional spelling system used before the Soviet-era spelling reforms. Western Armenian communities worldwide continue to use this system.

**NEVER use reformed/Eastern Armenian spelling**, even if:
- The word is pronounced the same in both dialects
- The reformed spelling looks "simpler"
- You see Eastern Armenian sources

Orthography and pronunciation are not the same axis: communities can keep classical spelling while pronouncing by Western or Eastern phonology.

---

## Key Classical vs. Reformed Differences

### 1. The իւ / ու Distinction

**Classical orthography preserves the distinction between:**
- **ու** [u] - simple "oo" vowel (ուր = where)
- **իւ** [ju] - "yoo" diphthong (իւր/իր = his/her, by dialect/register)

**Reformed orthography merged these:** Both became ու in Eastern Armenian spelling reforms.

#### Common Examples

| Classical (✓ USE THIS) | Reformed (✗ NEVER) | English | Pronunciation |
|------------------------|---------------------|---------|---------------|
| իւղ | յուղ | oil | yoogh |
| իւր / իր | ուր | his/her | yur / ir |
| իւրաքանչիւր | ուրաքանչյուր | each/every | yur-kahn-chyur |
| գիւղ | գյուղ | village | kyoogh |
| ճիւղ | ճյուղ | branch | jyoogh |
| զամբիւղ | զամբյուղ | basket | zampyoogh |

### 2. The է / ե Distinction

**Classical orthography distinguishes:**
- **ե** [ɛ] or [jɛ] - context-dependent vowel
- **է** [ɛ] - standalone vowel (rarely in Western, mainly Eastern)

**Reformed orthography:** Uses є for copula "is" and other contexts

**Note:** Western Armenian uses է MUCH LESS than Eastern. Most words spell with ե in classical Western orthography.

### 3. Word-Final -եան vs. -յան

**Classical:** Uses -եան for many suffixes
- Հայեան (Armenian, as adjective/surname)
- ազգային → classical: ազգային or ազգեան

**Reformed:** Merged to -յան in many cases

### 4. Ո vs. Ու at Word Start

**Classical:** Preserves ո [vo] before consonants
- ոսկի (gold) = vo-sgi
- ոչ (no) = voch

**Reformed:** Sometimes changes to ու

---

## Implementation Rules for This Project

### Rule 1: Default to Classical

**ALL Armenian text must use classical orthography by default.**

When adding new words:
1. Check Anki export data (08-data/anki_export.json) for existing spellings
2. Verify against classical dictionaries (Nayiri uses classical)
3. If uncertain, use the spelling with իւ rather than merging to ու

### Rule 2: Test Words Must Use Classical

**Current test words (all classical):**
- պետք = bedk (necessity)
- ժամ = zham (time/hour)
- ջուր = choor (water)
- ոչ = voch (no)
- իւր/իր = yur/ir (his/her, by dialect/register)
- իւղ = yoogh (oil)

### Rule 3: Documentation Examples Must Use Classical

All documentation files must show classical spellings:
- WESTERN_ARMENIAN_PHONETICS_GUIDE.md
- ARMENIAN_QUICK_REFERENCE.md
- NEXT_SESSION_INSTRUCTIONS.md
- All code examples in test files

### Rule 4: Code Must Handle Both (But Prefer Classical)

The phonetics implementation should:
- Recognize classical spellings (իւ, ու distinction)
- Store words in classical orthography in database
- Display classical orthography in flashcards
- Optionally handle reformed spellings as input (for corpus processing), but normalize to classical internally

---

## Common Mistakes to Avoid

### ❌ Mistake: Confusing յուղ and իւղ

**Wrong:** յուղ = yoogh (oil)
- Why wrong: This uses Eastern reformed spelling
- The word յ+ուղ would be "you-ugh" with y-glide + oo + gh

**Correct:** իւղ = yoogh (oil)
- Uses classical իւ diphthong [ju]
- Pronounced "yoogh" with proper diphthong

### ❌ Mistake: Writing ուր for the possessive pronoun

**Wrong:** ուր for "his/her"

**Correct:**
- ուր = oor (where) - uses simple ու vowel
- իւր = yur (his/her, classical Western form)
- իր = ir (his/her, also attested by dialect/register)

`ուր` is a different word from possessive `իւր/իր`.

### ❌ Mistake: Using գյուղ Instead of գիւղ

**Wrong:** գյուղ (reformed spelling for village)

**Correct:** գիւղ (classical spelling)
- Middle letter is իւ diphthong, not yoo-glide
- Pronounced "kyoogh" in Western Armenian

### ❌ Mistake: Assuming Reformed = "Correct"

**Wrong assumption:** "Reformed spelling is modernized and correct"

**Reality:** Western Armenian communities never adopted Soviet reforms. Classical orthography is the standard for Western Armenian.

---

## Verification Checklist

Before committing any Armenian text:

- [ ] Check for իւ vs ու - is this the classical spelling?
- [ ] Cross-reference with Anki export data (08-data/anki_export.json)
- [ ] Verify test words haven't changed to reformed spelling
- [ ] Check documentation examples use classical orthography
- [ ] Confirm diphthong table includes both ու and իւ as SEPARATE entries

---

## Historical Context

### Why Two Systems Exist

**Classical orthography** (pre-1920s):
- Used in Ottoman Empire and diaspora
- Preserved by Western Armenian communities worldwide
- Maintained orthographic distinctions (իւ/ու, etc.)
- Standard for Western Armenian teaching today

**Reformed orthography** (1920s+):
- Introduced by Soviet Armenia
- Simplified some distinctions
- Merged իւ → ու, changed some vowel usage
- Standardized in Soviet/post-Soviet Eastern Armenian (primarily Armenia)
- Not universal in Iranian diaspora usage; many communities retain classical spelling

### Why We Use Classical

1. **Western Armenian standard:** All Western Armenian schools, churches, and publications use classical orthography
2. **Preserves distinctions:** Classical spelling maintains meaningful differences (իւր vs ուր)
3. **User expectation:** Western Armenian learners expect classical spelling
4. **Corpus sources:** Most Western Armenian texts (newspapers, books) use classical orthography

---

## Resources for Verification

### Primary Sources (Classical Orthography)
- **Nayiri Dictionary** (classical spellings): http://www.nayiri.com
- **Anki export data** (08-data/anki_export.json): Contains 3,200+ words in classical orthography
- **Western Armenian newspapers** (corpus): Azdak, Nor Osk, etc. use classical
- **CWAS materials** (Centre for Western Armenian Studies): Uses classical exclusively

### Warning: Eastern Armenian Sources
Do NOT reference these for spelling:
- Eastern Armenian dictionaries (will show reformed spelling)
- Wikipedia Armenian entries (uses reformed)
- Google Translate (defaults to Eastern reformed)

---

## Code Implementation Notes

### phonetics.py Diphthong Handling

ARMENIAN_DIGRAPHS must include BOTH:
```python
ARMENIAN_DIGRAPHS = {
    'ու': {'ipa': 'u', 'approx': 'oo', 'difficulty': 1},    # Simple oo vowel
    'իւ': {'ipa': 'ju', 'approx': 'yoo', 'difficulty': 1},  # Yoo diphthong
}
```

These are DIFFERENT and must be handled separately:
- ու at word start: ուր = [oor] "where"
- իւ anywhere: իւր = [yur] / իր = [ir] (his/her)

### Database Normalization

**Storage:** Always store classical orthography
- Entry: իւղ (not յուղ)
- Entry: իւր or իր (never ուր for "his/her")

**Lookup:** Optionally accept reformed as input, but normalize:
```python
def normalize_to_classical(word):
    # If processing corpus with mixed spelling, normalize to classical
    # Example: ուր (if context shows it means "his/her") → իւր or իր
    # This is complex - better to enforce classical input
    pass
```

**Display:** Always show classical spelling in flashcards and output

---

## Testing Requirements

### Test Word Updates

All test files must use classical orthography:
```python
test_words = {
    'իւր': 'yur',      # NOT ուր (unless testing word meaning "where")
    'իր': 'ir',        # possessive variant by dialect/register
    'իւղ': 'yoogh',    # NOT յուղ
    'գիւղ': 'kyoogh',  # NOT գյուղ
}
```

### Regression Prevention

Add tests to verify:
1. իւ diphthong handled correctly (not merged to ու)
2. Test words haven't been changed to reformed spelling
3. Database entries use classical spelling
4. Output shows classical spelling in flashcards

---

## Version History

| Date | Version | Change |
|------|---------|--------|
| 2026-03-03 | 1.0 | Initial guide created to formalize classical orthography requirement |

---

## Final Notes

**This is non-negotiable: use classical orthography exclusively.**

If you find reformed spelling in:
1. **Code:** Update to classical immediately
2. **Tests:** Fix and add regression test
3. **Documentation:** Correct all examples
4. **Data:** Verify against Anki export and correct

Classical orthography is an architectural requirement for this project, not a preference.

---

**Last Updated:** March 3, 2026  
**Status:** AUTHORITATIVE REQUIREMENT  
**Dialect:** Western Armenian (Արևմտահայերէն) - Classical Orthography
