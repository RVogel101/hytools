# Armenian Quick Reference Card

**For quick lookup during implementation. For complete details see comprehensive guides at project root.**

## ⚠️ CRITICAL: The Voicing Reversal (START HERE)

Western Armenian has **BACKWARDS VOICING** — letter appearance ≠ pronunciation:

| Letter | Looks Like | Actually Sounds Like | Example |
|--------|-----------|----------------------|---------|
| **բ** | voiced p | **p** (unvoiced) | բան = pahn |
| **պ** | unvoiced b | **b** (voiced) | պետք = bedk |
| **դ** | voiced t | **t** (unvoiced) | դուռ = tour |
| **տ** | unvoiced d | **d** (voiced) | տուն = doun |
| **գ** | voiced k | **k** (unvoiced) | գիտ = keed |
| **կ** | unvoiced g | **g** (voiced) | կտուր = g'dour |

**TEST WORD**: պետք = "bedk" (NOT "petik")  
If you get the [p] sound, you're using Eastern Armenian ❌

---

## Context-Aware Letters (Position Changes Pronunciation)

| Letter | Position | Sound | Example |
|--------|----------|-------|---------|
| **յ** | word start | h | յոյս = huys |
| **յ** | word middle/end | y | բայ = pye |
| **ո** | before consonant | vo | ոչ = voch |
| **ո** | after consonant/as vowel | o (go) | կո = go |
| **ե** | word start | ye | ե = ye |
| **ե** | word middle/end | e | ե = e |
| **ւ** | between vowels | v | complex |

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
| **ոյ** | o / uy (IPA: uj, context-dependent) | Word-final: `o`; before consonant: `ooy` |
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
իւր → yur (իւ=yu diphthong)

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

# Pronunciation Rules Mined from docs/armenian_language_guids

**Purpose:** Single reference of pronunciation rules extracted from the Western Armenian phonetics guide, quick reference, classical orthography guide, and related docs. Used by `linguistics/transliteration.py` for unwritten schwa insertion and IPA/Latin output.

---

## 1. Context-dependent letters (from WESTERN_ARMENIAN_PHONETICS_GUIDE.md, ARMENIAN_QUICK_REFERENCE.md)

| Letter | Position / context | IPA / Latin | Example |
|--------|--------------------|-------------|---------|
| **յ** | Word-initial | h | յոյս = hoys |
| **յ** | Word-medial or -final | j (y) | բայ = pay |
| **ո** | Before consonant | vo | ոչ = voch, որ = vor |
| **ո** | After consonant or as vowel | o | կո = go |
| **ե** | Word-initial | jɛ / ye | եղ = yegh |
| **ե** | Word-medial or -final | ɛ / e | բեր = ber |
| **ւ** | In diphthongs ու, իւ | u, ju | ուր = oor, իւր = yur |
| **ւ** | Between vowels | v | այւ = ayv |

---

## 2. Unwritten ը (epenthetic schwa) — implementation rules

These rules are applied when generating **pronunciation form** (IPA or Latin with schwa) for Western Armenian.

### 2.1 Word-initial սպ

- **Rule:** Word-initial **սպ** is pronounced with an unwritten **ը** before it.
- **Example:** սպասել → pronounced ըսպասել (uspasel).
- **Source:** User requirement and project convention; document in phonetics guide if not already.

### 2.2 Between two consonants

- **Rule:** Between two consonants (no vowel in between), an unwritten **ը** is often pronounced (epenthetic schwa to break the cluster).
- **Examples:** մնալ → մընալ (mənal); տեսնել → տեսնէլ with possible ը between consonant clusters depending on syllable.
- **Implementation:** After normalization, scan for consecutive Armenian consonants (excluding digraphs like ու, իւ); insert ը between them when building the “pronunciation” string for IPA/Latin. Optionally limit to certain clusters (e.g. մն, սպ, զբ) if full C+C is too aggressive.

### 2.3 Consonant set (for “between two consonants”)

Armenian consonants (single letters, no vowels):  
**բ գ դ զ թ ժ լ խ ծ կ հ ձ ղ ճ մ ն շ չ պ ջ ռ ս վ տ ր ց ւ փ ք ֆ**.  
Vowels (no schwa between): **ա ե է ը ի ո յ օ**.

---

## 3. Voicing reversal (Western only)

From WESTERN_ARMENIAN_PHONETICS_GUIDE.md, ARMENIAN_QUICK_REFERENCE.md:

- բ→p, պ→b; գ→k, կ→g; դ→t, տ→d; ճ→j, ջ→ch; ձ→ts, ծ→dz.
- թ = t (not “th”).

---

## 4. Diphthongs

- **ու** = u (oo). In classical/Western, before a vowel the sequence may be read as **v** + vowel.
- **իւ** = ju (yoo).

---

## 5. Classical orthography (from CLASSICAL_ORTHOGRAPHY_GUIDE.md)

- Use **իւ** not յուղ (e.g. իւղ = oil).
- **ուր** = “where”; **իւր** / **իր** = “his/her”.
- Western does not use **և** inside words; use **եւ** (two characters). **և** only for the word “and”.

---

## 6. References

- `WESTERN_ARMENIAN_PHONETICS_GUIDE.md`
- `ARMENIAN_QUICK_REFERENCE.md`
- `CLASSICAL_ORTHOGRAPHY_GUIDE.md`
- `phonetics_rule_gaps.md`
- `western-armenian-grammar.md`

# Morphological Suffix and Prefix Tracking

## Tracked Suffixes

The `linguistics.metrics.text_metrics` module tracks suffixes in `MorphologicalMetrics`:

| Suffix | Armenian | Role | Dialect Signal |
|--------|----------|------|----------------|
| -եմ | em | Western 1st singular present | Western (e.g. բերեմ "I bring") |
| -իմ | im | Possessive "my" (pre-noun) | Western — not verb suffix; իմ = "my" |
| -ում | um | EA present/imperfective verbal inflection | Eastern (e.g. բերում եմ "I bring"); also occurs in WA verbal nouns and certain roots — NOT a WA present-tense conjugation marker |
| -ան | an | Various (plural, 3rd person) | Shared |
| -ել | el | Infinitive | Shared (e.g. գրել "to write") |
| -իլ | il | Infinitive (passive verb form) | Western only (e.g. խօսիլ "to speak") |

**Dialect notes:**
- In **Eastern** Armenian, "I bring" = բերում եմ (berum yem).
- In **Western** Armenian, "I bring" = կը բերեմ (perem).
- -իմ in Western means "my" (possessive, can be dropped when implied); not a 1st singular verb ending.
- -ում is distinctively EA as a verbal inflection; WA uses կոր (gor) for present progressive. -ում does appear in WA as part of verbal nouns and certain lexical roots, so its presence alone is a signal, not proof, of EA influence.
- -իլ is Western-only infinitive; -ել is shared.

**Value of these statistics:** The ratio of -եմ (WA) vs -ում (EA) is a dialect marker. -իլ presence indicates Western Armenian. -իմ as word-final on verbs was a misclassification; in correct WA, -իմ is possessive "my".

## Tracked Prefixes

Prefixes are tracked when `compute_metrics_on_ingest` or morphological analysis is enabled:

| Prefix | Armenian | Romanization | Role | Dialect |
|--------|----------|--------------|------|---------|
| կը | gu | gu | Present tense marker | Western |
| կ՚ | g' | g' | Elided before vowel | Western |
| պիտի | bidi | bidi | Future marker | Western |
| չ | ch | ch | Negative (word-initial) | Western |

See `linguistics.metrics.text_metrics.MorphologicalMetrics` and `scraping._helpers` for implementation.

## Use in WesternArmenianLLM Training

Functions suitable for import in WesternArmenianLLM:

- **`linguistics.metrics.text_metrics.QuantitativeLinguisticsAnalyzer`** — Full metric card (lexical, syntactic, morphological, orthographic, contamination, quality).
- **`linguistics.metrics.text_metrics.TextMetricCard`**, **`MorphologicalMetrics`** — Dataclasses for structured metrics.
- **`linguistics.metrics.validate_augmentation_output`** — Validate WA output (used by Phase 1 SafeAugmentationWrapper).
- **`linguistics.metrics.vocabulary_filter.WesternArmenianVocabularyFilter`** — Eastern vocabulary detection.
- **`cleaning.language_filter.is_western_armenian`**, **`compute_wa_score`** — WA classification.

# Test Validation: Western and Eastern Armenian

This document tracks all Armenian text used in dialect/validation tests: translations, transliterations (Western Armenian romanization), and the markers each test validates.

---

## 1. test_augmentation_validation.py

### test_validation_passes_for_wa_text

**Western Armenian text:**
```
Ան կը խօսի հայերէն, հոն կ՚ապրի մէջ իւրաքանչիւր մանուկ
```

| Word/Phrase | Transliteration (WA) | English |
|-------------|----------------------|---------|
| Ան | An | He/She/It |
| կը | gu | present tense marker |
| խօսի | khosi | speaks |
| հայերէն | hayeren | Armenian (language) |
| հոն | hon | there |
| կ՚ | g' | present (elided before vowel) |
| ապրի | abri | lives |
| մէջ | mej | in |
| իւրաքանչիւր | yoorakanchyoor | each/every |
| մանուկ | manook | child |

**Full translation:** He/She speaks Armenian; he/she lives there in each child.

**Markers tested:**
- Classical orthography: **մէջ**, **իւրաքանչիւր** (diphthong իւ, long է)
- Lexical: **կը** (gu), **կ՚** (g') — present tense
- Vocabulary: **հոն**, **մանուկ**
- Pronoun: **Ան** (WA he/she/it)

---

### test_validation_fails_for_ea_text

**Eastern Armenian text:**
```
Նա խոսում է հայերեն այնտեղ ապրում է
```

| Word/Phrase | Transliteration (EA) | English |
|-------------|----------------------|---------|
| Նա | Na | He/She |
| խոսում | khosum | speaks (imperfective) |
| է | e | is |
| հայերեն | hayeren | Armenian |
| այնտեղ | ayntegh | there |
| ապրում | aprum | lives |
| է | e | is |

**Full translation:** He/She speaks Armenian; he/she lives there.

**Markers tested (EA = expected to fail WA validation):**
- Reformed spelling: **խոսում** (-ում imperfective), **այնտեղ** (not հոն)
- No classical diphthongs (իւ, եա, etc.)

---

### test_validation_detects_eastern_markers

**Eastern reformed text:**
```
միյասին գնում ենք
```

| Word/Phrase | Transliteration | English |
|-------------|-----------------|---------|
| միյասին | miyasin | together |
| գնում | gnum | we go |
| ենք | yenk | we are |

**Full translation:** We go together.

**Markers tested:**
- **միյ** — EA reformed digraph (classical: **մէջ** or similar)
- **-ում** — Eastern imperfective
- **-ենք** — Eastern 1st plural

---

### test_validation_requires_classical_markers

**Weak text (no classical markers):**
```
Հայ ժողովուրդ
```

| Word | Transliteration | English |
|------|-----------------|---------|
| Հայ | Hay | Armenian |
| ժողովուրդ | zhoghovurt | people |

**Full translation:** Armenian people.

**Purpose:** Fails because no classical diphthongs/digraphs (ոյ, այ, իւ, եա, etc.).

---

### test_classical_spelling_validation

**Classical (passes):**
```
մէջ իւրաքանչիւր բան մը
```

| Word/Phrase | Transliteration | English |
|-------------|-----------------|---------|
| մէջ | mej | in |
| իւրաքանչիւր | yoorakanchyoor | each/every |
| բան մը | pan mu | something |

**Full translation:** In each something. (Classical spelling markers present.)

**Reformed (fails):**
```
միյասին
```
EA reformed digraph **միյ**.

---

### test_nayiri_dictionary_stub

**Text:**
```
կը խօսի հայերէն
```

| Word | Transliteration | English |
|------|-----------------|---------|
| կը | gu | present |
| խօսի | khosi | speaks |
| հայերէն | hayeren | Armenian |

**Full translation:** Speaks Armenian.

---

### test_low_armenian_ratio

**Mixed text:**
```
This is mostly English with some Հայերէն
```

**Purpose:** Low Armenian script ratio → validation fails.

---

### test_validation_result_structure / test_regeneration_prompt_generation

**Text:**
```
կը խօսի հայերէն
բնագիր տեքստ
```

| Word | Transliteration | English |
|------|-----------------|---------|
| բնագիր | bnagir | original |
| տեքստ | teksd | text |

---

## 2. test_text_metrics.py

### test_morphological_suffix_tracking

**Western Armenian:**
```
Ես բերեմ ու գրեմ այն տուն։
```

| Word | Transliteration | English |
|------|-----------------|---------|
| Ես | Yes | I |
| բերեմ | berem | I bring |
| ու | ou | and |
| գրեմ | grem | I write |
| այն | ayn | that |
| տուն | doon | house |

**Full translation:** I bring and write that house.

**Markers tested:** **-եմ** suffix (Western 1st singular present): բերեմ, գրեմ.

---

**Eastern Armenian:**
```
Ես բերում եմ ու գրում եմ այն տուն։
```

| Word | Transliteration | English |
|------|-----------------|---------|
| Ես | Yes | I |
| բերում | berum | bringing |
| եմ | yem | am |
| գրում | grum | writing |
| այն | ayn | that |
| տուն | doon | house |

**Full translation:** I am bringing and (I) am writing that house.

**Markers tested:** **-ում** suffix (Eastern imperfective): բերում, գրում.

---

### test_lexical_metrics_computation / test_orthographic_metrics / test_quality_flags

**Neutral/mixed text:**
```
Տունը մեծ է։ Տունը գեղավոր է։ Մենք տունը սիրում ենք։
```

| Word | Transliteration | English |
|------|-----------------|---------|
| Տունը | Doonuh | The house |
| մեծ | medz | big |
| է | e | is |
| գեղավոր | kegavor | beautiful |
| Մենք | Menk | We |
| սիրում ենք | sirum yenk | we love |

**Full translation:** The house is big. The house is beautiful. We love the house.

---

### test_syntactic_metrics_computation

```
Տունը մեծ է։ Այն գեղավոր է։ Մենք այստեղ ապրում ենք և շատ բազմում ենք այս տեղ։
```

| Word | Transliteration | English |
|------|-----------------|---------|
| Այստեղ | Aysdegh | here |
| աշատ | shad | very |
| այս տեղ | ays degh | this place |

**Full translation:** The house is big. It is beautiful. We live here and gather a lot in this place.

---

### test_high_ttr_indicates_diversity

```
Տունը մեծ, գեղավոր, հին, որտեղ ապրում է հատուկ, հմայական, բարձր արխիտեկտուր։
```

**Full translation:** The house is big, beautiful, old, where special, enchanting, high architecture lives.

---

### test_low_ttr_indicates_repetition

```
Տունը տուն է։ Տունը տուն է։ Տունը տուն է։
```

**Full translation:** The house is a house. The house is a house. The house is a house.

---

## 3. test_corpus_vocabulary_filter.py

**Note:** This test suite uses the vocabulary filter's `eastern_only_vocabulary`, which may classify **բերեմ** as Eastern. Per corrected dialect rules, **-եմ** is Western (բերեմ = I bring) and **-ում** is Eastern. Tests here reflect the *current* filter behavior, not the corrected morphological convention.

### Eastern vocabulary tests

| Test | Armenian | Transliteration | English | Marker |
|------|----------|-----------------|---------|--------|
| test_detect_eastern_verb_forms | բերեմ | berem | I bring | -եմ (filter treats as EA) |
| test_detect_eastern_plural_forms | բերենք | berenk | We bring | -ենք |
| test_detect_eastern_3rd_singular | գնայ | gna | He goes | -այ |
| test_correct_eastern_to_western | բերեմ այն | berem ayn | I bring it | → բերիմ (filter mapping) |

### Western (no false positive) test

```
Ես չեմ կարողանում հասկանալ։
```

| Word | Transliteration | English |
|------|-----------------|---------|
| Ես | Yes | I |
| չեմ | chem | I am not |
| կարողանում | garoghanoom | able |
| հասկանալ | hasgnal | to understand |

**Full translation:** I cannot understand.

**Markers:** **չ** (negative), **-ում** (if treated as EA may trigger).

---

## 4. test_phase1_eastern_prevention.py

**Note:** Same dialect convention caveat as test_corpus_vocabulary_filter. The filter may treat -եմ as Eastern and -իմ as Western; per corrected rules, -եմ is Western, -իմ is possessive "my".

### test_detects_eastern_only_words

```
Ես բերեմ գիրք։
```

**Full translation:** I bring a book. (Filter may flag **բերեմ**.)

### test_rejects_eastern_single_present_form

```
Ես ունեմ տուն։
Ես գալեմ ավելի ուշ։
```

| Word | Transliteration | English |
|------|-----------------|---------|
| ունեմ | ounem | I have |
| գալեմ | galem | I come |
| ավելի ուշ | aveli oosh | later |

**Full translation:** I have a house. I come later.

**Markers:** -եմ (1st singular); **ա** in ավելի (reformed).

### test_accepts_western_forms

```
Ես բերիմ շաբաթական ձավ։
Մենք գալինք մեր տուն։
```

| Word | Transliteration | English |
|------|-----------------|---------|
| բերիմ | berim | (filter: Western 1st sg; corrected: im = "my") |
| շաբաթական | shabadagan | weekly |
| ձավ | dzav | (context-dependent) |
| գալինք | galink | we came |
| մեր | mer | our |

**Full translation:** I bring weekly … We came to our house.

---

## 5. Grammar and Word Reference

### Suffix reference (corrected)

| Suffix | Dialect | Example | Transliteration | Meaning |
|--------|---------|---------|-----------------|---------|
| -եմ | Western | բերեմ | berem | I bring |
| -ում | Eastern | բերում | berum | bringing |
| -իլ | Western | խօսիլ | khosil | to speak |
| -ել | Shared | գրել | grel | to write |

### Prefix reference

| Prefix | Dialect | Transliteration | Meaning |
|--------|---------|-----------------|---------|
| կը | Western | gu | present tense |
| կ՚ | Western | g' | present (elided) |
| պիտի | Western | bidi | future |
| չ | Western | ch | negative |

### Affricate reference (WA voicing)

| Grapheme | WA | EA (wrong) | Example |
|----------|-----|------------|---------|
| ձ | ts | dz | ձայն = tsayn |
| ծ | dz | ts | ծանի = dzani |
| ճ | j | ch | ճերմակ = chermag |
| ջ | ch | j | ջուր = choor |

### Pronoun reference

| Armenian | WA Translit | English |
|----------|-------------|---------|
| ես | yes | I |
| դու | doo | you (sg) |
| նա | na | he/she (EA) |
| ան | an | he/she (WA) |
| մենք | menk | we |
| դուք | took | you (pl) |

# Western Armenian Language Logic Consolidated Reference

Purpose: one canonical reference for grammar logic, transliteration logic, phonetic logic, Western-vs-Eastern lexical markers, and spelling-reform dictionary differences.

Status: consolidated from current project docs + code (no external assumptions).

---

## Scope And Authority

Primary sources used in this consolidation:
- `01-docs/western-armenian-grammar.md`
- `01-docs/references/ARMENIAN_QUICK_REFERENCE.md`
- `01-docs/references/WESTERN_ARMENIAN_PHONETICS_GUIDE.md`
- `01-docs/references/CLASSICAL_ORTHOGRAPHY_GUIDE.md`
- `02-src/lousardzag/morphology/core.py`
- `02-src/lousardzag/phonetics.py`
- `02-src/lousardzag/dialect_classifier.py`
- `04-tests/unit/test_dialect_classifier.py`
- `04-tests/integration/test_transliteration.py`

Policy alignment:
- Western Armenian only.
- Classical orthography required for canonical output.
- Eastern/reformed forms may be accepted only as input signals, never as canonical storage/output.

---

## 1. Grammar Logic (Consolidated)

### 1.1 Noun System
- Western Armenian nouns have no grammatical gender.
- Number is singular/plural; plural commonly uses `-եր`.
- Case system includes nominative, accusative, genitive, dative, locative, ablative (as documented in `01-docs/western-armenian-grammar.md`).

### 1.2 Articles And Determination
- Definite article selection is phonetic (final sound driven), not gender-based.
- Western indefinite article marker: postposed `մը`.
- Dialect classifier treats `մը` as a Western signal (`WA_INDEF_ARTICLE_MUH`).

### 1.3 Verbal Particles (Dialect-Critical)
- Western present particle marker: `կը`.
- Western future marker: `պիտի`.
- Western negative particle marker in current rules: `չը`.
- These markers are used as weighted evidence in `02-src/lousardzag/dialect_classifier.py`.

### 1.4 Grammar-Related Operational Rule
- If a form has no documented Western marker, classification should remain inconclusive rather than guessed.
- Current classifier behavior follows this conservative design.

---

## 2. Transliteration Logic (Consolidated)

### 2.1 Canonical Implementation
- Core transliteration map is in `02-src/lousardzag/morphology/core.py` (`ARM`, `ARM_UPPER`).
- Romanization function: `romanize(word, capitalize=False)`.
- Digraph handling is explicit and occurs before single-character mapping.

### 2.2 Western Armenian Consonant Shift (Must Not Regress)
- Reversed voicing pairs are enforced in tests (`04-tests/integration/test_transliteration.py`):
  - `բ -> p`, `պ -> b`
  - `դ -> t`, `տ -> d`
  - `գ -> k`, `կ -> g`
  - `ծ -> dz`, `ձ -> ts`
- Affricate distinctions in current code/tests:
  - `ջ -> j` key in transliteration map tests
  - `չ -> ch`
- Aspirated series are not part of the reversed voicing swap.

### 2.3 Transliteration Rule Order
- Rule order required:
1. Detect digraphs (for example `ու`) first.
2. Apply single-letter map only when no digraph matched.
3. Preserve non-Armenian characters as-is.

### 2.4 Syllable Logic Coupling
- `count_syllables(word)` in `morphology/core.py` treats `ու` as one vowel nucleus.
- Context-aware hidden vowels are delegated to morphology difficulty/context logic.

---

## 3. Phonetic Logic (Consolidated)

### 3.1 Canonical Implementation
- Main module: `02-src/lousardzag/phonetics.py`.
- Primary data structures:
  - `ARMENIAN_PHONEMES` (letter-level IPA + English approximation + difficulty)
  - `ARMENIAN_DIGRAPHS` (multi-letter vowel units such as `ու`, `իւ`)
- Primary API:
  - `get_phonetic_transcription(armenian_word)`
  - `calculate_phonetic_difficulty(armenian_word)`
  - `get_pronunciation_guide(armenian_word)`

### 3.2 Non-Negotiable Western Phonetics
- Voicing reversal in phonetics must align with transliteration and tests.
- Context-aware behavior is mandatory for `ե`, `ո`, `յ`, `ւ`.
- `թ` is regular `t` (not English "th").
- Guttural sounds (`խ`, `ղ`) are high-difficulty and must remain explicitly marked.

### 3.3 Phonetic QA Gates
- Use quick verification words from `ARMENIAN_QUICK_REFERENCE.md` and phonetics guide.
- Any output resembling Eastern defaults (for example `petik` pattern for Western target words) is a fail condition.

---

## 4. Common Western Armenian Markers Not Usually Used In Eastern (Project-Documented)

Note: this section lists documented project markers/signals, not a complete linguistic inventory.

### 4.1 Western Lexical/Grammatical Signals
- `մը` (postposed indefinite marker)
- `կը` (present particle)
- `պիտի` (future particle)
- `չը` (negative particle in current rule set)
- Classical orthography patterns with `իւ` retained in lexical forms (see orthography section below)

Source of these markers:
- `02-src/lousardzag/dialect_classifier.py` rules
- `04-tests/unit/test_dialect_classifier.py`
- `01-docs/references/CLASSICAL_ORTHOGRAPHY_GUIDE.md`

### 4.2 Eastern/Reformed Signals Used As Contrast
- `գյուղ`, `յուղ`, `ճյուղ`, `զամբյուղ`, `ուրաքանչյուր` are treated as reformed/eastern-side evidence in current classifier rules.

Important constraint:
- These are classifier evidence features, not full lexical dictionaries.

---

## 5. Spelling Reform Differences For Dictionary Work (Detailed)

### 5.1 Canonical Project Requirement
- Canonical storage/output: classical orthography.
- Reformed forms: accepted only as input normalization or dialect evidence.

### 5.2 High-Value Classical vs Reformed Pairs (Project-Documented)

| Classical (Canonical) | Reformed (Contrast) | Meaning |
|---|---|---|
| `իւղ` | `յուղ` | oil |
| `գիւղ` | `գյուղ` | village |
| `ճիւղ` | `ճյուղ` | branch |
| `զամբիւղ` | `զամբյուղ` | basket |
| `իւրաքանչիւր` | `ուրաքանչյուր` | each/every |
| `իւր` / `իր` | `ուր` (different lexical item) | his/her vs where |

Source: `01-docs/references/CLASSICAL_ORTHOGRAPHY_GUIDE.md` and classifier rule definitions.

### 5.3 Dictionary Lookup Strategy
- Preferred dictionary reference for Western spelling checks: Nayiri (classical orthography baseline).
- For ingestion pipelines:
1. Detect classical/reformed variants.
2. Normalize to classical for canonical storage.
3. Preserve original surface form in metadata when needed.

---

## 6. Consolidated Source-Of-Truth Map (Code + Docs)

### 6.1 Grammar
- Canonical doc: `01-docs/western-armenian-grammar.md`
- Operational rule signals: `02-src/lousardzag/dialect_classifier.py`

### 6.2 Transliteration
- Canonical code: `02-src/lousardzag/morphology/core.py`
- Regression tests: `04-tests/integration/test_transliteration.py`

### 6.3 Phonetics
- Canonical code: `02-src/lousardzag/phonetics.py`
- Canonical guide: `01-docs/references/WESTERN_ARMENIAN_PHONETICS_GUIDE.md`

### 6.4 Orthography/Reform
- Canonical guide: `01-docs/references/CLASSICAL_ORTHOGRAPHY_GUIDE.md`
- Dialect evidence rules: `02-src/lousardzag/dialect_classifier.py`

---

## 7. Consolidation Actions (Recommended Next Cleanup)

- Keep this file as the top-level language logic index.
- Keep detailed deep dives in existing specialized files.
- When adding any new rule:
1. Update the owning implementation file first.
2. Add/adjust tests.
3. Mirror the summary here with source links.

---

## 8. Data Coverage Note

Local database checked during consolidation: `08-data/armenian_cards.db`.
- Observed primary lexical table: `anki_cards`.
- Some classifier markers (especially particles) are rule-level signals and may not be present as standalone lexical entries in that table.
- This consolidated reference therefore cites implementation/test sources for those markers.

---

Last updated: 2026-03-05

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

# Western Armenian Grammar Rules

**AUTHORITY**: This document is built ONLY from code already in the project and verified against the Western Armenian phonetics reference.

**SCOPE**: Verified Western Armenian rules only, limited to items explicitly validated in project code, tests, user corrections, and corpus checks.

---

## Table of Contents

1. [Phonetic Alphabet Review](#phonetic-alphabet-review)
2. [Nouns](#nouns)
   - [Gender](#gender)
   - [Number](#number)
3. [Articles](#articles)
   - [Definite Article](#definite-article)
   - [Indefinite Article](#indefinite-article)
4. [Removed Pending Explicit Rules](#removed-pending-explicit-rules)

---

## Phonetic Alphabet Review

**Critical**: Western Armenian has REVERSED VOICING from Eastern Armenian. See `/memories/western-armenian-requirement.md` for complete phoneme inventory.

**Key Stop/Affricate Pairs** (ALWAYS verify):
- բ = /p/, պ = /b/
- գ = /k/, կ = /g/
- դ = /t/, տ = /d/
- ճ = /dʒ/, ջ = /tʃ/
- ծ = /dz/, ց = /ts/, ձ = /ts/

---

## Nouns

### Proper Nouns

Proper nouns (names of persons, places) begin with a capital letter.

### Gender

**CRITICAL: Western Armenian nouns have NO GENDER**. Unlike many Indo-European languages, Armenian nouns are not inflected for gender. Determiners (articles, demonstratives) and adjectives do not mark gender agreement.

### Declension

In Armenian, nouns are declined, that is to say, their endings change according to the function they perform in a sentence. The various forms which they take are called cases.

Thus, to say "of the house," instead of using a preposition (of, as in English), the word տուն (house) is changed to տունին. Or to say "from the house," instead of using a preposition (from), the word տուն is changed to տունէն.

There are six cases:

**1) Nominative** — the case of the subject of the sentence
- տունը մեծ է = the house (subject) is large

**2) Accusative** — the case of the direct object
- կը սիրեմ տունը = I like the house (direct object)

**3) Genitive** — the case of the possessor, the possessive case. The possessor, whether a person or thing, is always put first:
- Յակոբին տուն = Hagop's house
- մարդուն աչքը = the man's eye
- տունին դուրը = the house's door (of the house the door)
- աչքին գոյնը = the eye's color, the color of the eye (of the eye the color)

**4) Dative** — the case of the indirect object, indicating the person or the thing TO whom or to which something is destined. The dative form is the same as the genitive:
- Արշակին կուտամ = I give to (the) Arshag

**5) Ablative** — the case which shows from whom or from which the action originates:
- տունէն կուգամ = (I) come from the house

**6) Instrumental** — the case which shows WITH what the action takes place:
- գրիչով կը գրեմ = I write with pen

### Basic Forms of Declension

The following noun **դաշտ** (field) demonstrates the basic form of declension across all cases in both indefinite and definite forms, singular and plural.

**Singular Indefinite:**

| Case | Form | Translation |
|------|------|-------------|
| Nominative & Accusative | դաշտ | field |
| Genitive | դաշտի | of field |
| Dative | դաշտի | to field |
| Ablative | դաշտէ | from field |
| Instrumental | դաշտով | with field |

**Plural Indefinite:**

| Case | Form | Translation |
|------|------|-------------|
| Nominative & Accusative | դաշտեր | fields |
| Genitive | դաշտերու | of fields |
| Dative | դաշտերու | to fields |
| Ablative | դաշտերէ | from fields |
| Instrumental | դաշտերով | with fields |

**Singular with Definite Article:**

| Case | Form | Translation |
|------|------|-------------|
| Nominative & Accusative | դաշտը | the field |
| Genitive | դաշտին | of the field |
| Dative | դաշտին | to the field |
| Ablative | դաշտէն | from the field |
| Instrumental | դաշտովը | with the field |

**Plural with Definite Article:**

| Case | Form | Translation |
|------|------|-------------|
| Nominative & Accusative | դաշտերը | the fields |
| Genitive | դաշտերուն | of the fields |
| Dative | դաշտերուն | to the fields |
| Ablative | դաշտերէն | from the fields |
| Instrumental | դաշտերովը | with the fields |

**Note:** The nominative and accusative cases are identical in both singular and plural. The genitive and dative cases are also identical in both singular and plural.

There are other forms of declension, mostly inherited from ancient Armenian, which exist in modern Western Armenian. The student should know them even though the tendency now is to break away from them as much as possible and to use the basic form of declension.

---

## Sentence Structure

### Word Order

In Armenian, the typical order of words in a simple sentence is:

1. **Subject** (the person or thing doing the action)
2. **Attribute** (adjective or descriptor)
3. **Verb** (the action)

This is contrary to English, where the verb typically comes before the attribute. The verb comes **last** in Armenian.

**Examples:**
- Մեծ տուն է = Big house is (The house is big)
- Սիրուն արծիւ թռչեց = Beautiful eagle flew (The beautiful eagle flew)

### Number

Plural of Nouns:
to form the plural of nouns:

a) if the word has one syllable add "եր":
- տուն = house
- տուներ = houses
- քար = stone
- քարեր = stones
- մարդ = man
- մարդեր = men

b) if the word has more than one syllable add ներ:
- պարտէզ = garden
- պարտէզներ = gardens
- գնդակ = ball
- գնդակներ = balls
- ասուպ = comet
- ասուպներ = comets
- շուկայ = market
- շուկաներ = markets

Note that the silent յ at the end of the word is dropped and then ներ is added.

---

## Articles

### Definite Article

**CRITICAL: Article selection is PURELY PHONETIC** — determined by the final sound of the noun, NOT by gender or case.

**Seven Rules for Definite Article Selection**:

| # | Noun Ending | Article Marker | Definite Form |
|---|------------|----------------|---------------|
| 1 | Consonant | ը | noun + ը |
| 2 | Vowel (ա,ե,է,ը,ի,օ) | ն | noun + ն |
| 3 | Diphthong ու | ն | noun + ն |
| 4 | Silent յ | ն | drop յ + ն |
| 5 | Non-silent յ | ը | noun + ը |
| 6 | ւ as [v] semi-vowel | ը | noun + ը |
| 7 | Consonant before vowel-initial word | ն (variation) | noun + ն |

**Context Notes**:

Silent vs non-silent -յ and ւ/ու behavior are user-specified special handling rules and remain in this document without extra examples.

### Indefinite Article

the indefinite article (the English a or an) is the word մը which is placed after the word seperately

- տուն մը = a house
- գնդակ մը = a ball
- պարտէզ մը = a garden
- շուկայ մը = a market

**Contextual Form: մըն before verb forms and ալ**

The indefinite article մը becomes մըն if followed by:
1. Forms of the verb ըլլալ (են, ես, է, էր, էի, էիք, etc.)
2. The word ալ (also/too)

- տուն մըն է = it is a house
- պարտէզ մըն է = it is a garden
- կին մըն էր = it was a woman
- տղայ մըն էիք = you were a child
- թռչուն մըն ալ = also a bird
- հատ մըն ալ = one more

---

## Verbs

### ըլլալ (to be)

**Present:**

| Person | Pronoun | Conjugation | Translation |
|--------|---------|-------------|-------------|
| 1sg | ես | եմ | I am |
| 2sg | դուն | ես | you are (singular informal) |
| 3sg | ան | է | he, she, it is |
| 1pl | մենք | ենք | we are |
| 2pl | դուք | էք | you are (plural/formal) |
| 3pl | անոնք | են | they are |

**Imperfect (Continuous Past):**

| Person | Pronoun | Conjugation | Translation |
|--------|---------|-------------|-------------|
| 1sg | ես | էի | I was |
| 2sg | դուն | էիր | you were (singular informal) |
| 3sg | ան | էր | he, she, it was |
| 1pl | մենք | էինք | we were |
| 2pl | դուք | էիք | you were (plural/formal) |
| 3pl | անոնք | էին | they were |

**Past (Definite):**

| Person | Pronoun | Conjugation | Translation |
|--------|---------|-------------|-------------|
| 1sg | ես | եղայ | I was |
| 2sg | դուն | եղար | you were (singular informal) |
| 3sg | ան | եղաւ | he, she, it was |
| 1pl | մենք | եղանք | we were |
| 2pl | դուք | եղաք | you were (plural/formal) |
| 3pl | անոնք | եղան | they were |

**Usage Notes:**

- Personal pronouns (ես, դուն, ան, մենք, դուք, անոնք) are very often omitted as the ending of the verb indicates the person and number of the subject.
- The second person singular (դուն, thou) is used only in addressing parents, intimate friends, children, and God in prayer.
- All other persons should be addressed in the second person plural: դուք (you). This is the polite way.

**Negative Form:**

The negative of the present, imperfect and past definite of ըլլալ is obtained by placing the letter չ before the verb:

**Present Negative:**

| Person | Pronoun | Conjugation | Translation |
|--------|---------|-------------|-------------|
| 1sg | ես | չեմ | I am not |
| 2sg | դուն | չես | you are not (singular informal) |
| 3sg | ան | չէ | he, she, it is not |
| 1pl | մենք | չենք | we are not |
| 2pl | դուք | չէք | you are not (plural/formal) |
| 3pl | անոնք | չեն | they are not |

**Imperfect Negative (Continuous Past):**

| Person | Pronoun | Conjugation | Translation |
|--------|---------|-------------|-------------|
| 1sg | ես | չէի | I was not |
| 2sg | դուն | չէիր | you were not (singular informal) |
| 3sg | ան | չէր | he, she, it was not |
| 1pl | մենք | չէինք | we were not |
| 2pl | դուք | չէիք | you were not (plural/formal) |
| 3pl | անոնք | չէին | they were not |

**Past Negative (Definite):**

| Person | Pronoun | Conjugation | Translation |
|--------|---------|-------------|-------------|
| 1sg | ես | չեղայ | I was not |
| 2sg | դուն | չեղար | you were not (singular informal) |
| 3sg | ան | չեղաւ | he, she, it was not |
| 1pl | մենք | չեղանք | we were not |
| 2pl | դուք | չեղաք | you were not (plural/formal) |
| 3pl | անոնք | չեղան | they were not |

All of these negative forms have the same optional pronouns as their affirmative counterparts.

---

## Removed Pending Explicit Rules

Per user instruction, the following were removed because they were not explicitly provided by the user in this conversation:

1. Case system tables and descriptions
2. Declension class tables
3. Adjective agreement and declension sections
4. All non-user-provided examples

These will only be re-added after explicit user-provided rules/examples.

Do not reintroduce rules in this file unless explicitly provided by the user.

---

## Last Updated

March 4, 2026 — Reduced to explicit user-provided Western Armenian rules only.

## Next Steps

1. Add plural rules only after explicit user specification
2. Add case rules only after explicit user specification
3. Add examples only when explicitly provided by user

# Western Armenian Phonetics Rule Gaps

**Audit Date**: 2026-03-06  
**Moved from**: WesternArmenianLLM (phonetics material not used in training).

## Summary

- **Test words**: 5
- **Eastern leakage detected**: 0
- **Words with rule gaps**: 2

## Key Findings

### 1. Reversed Voicing (բ/պ, դ/տ, գ/կ, ճ/ջ)

Western Armenian has **reversed voicing** from Eastern Armenian:


| Grapheme | WA Phone | WA Voicing | EA Phone | EA Voicing |
| -------- | -------- | ---------- | -------- | ---------- |
| բ        | /p/      | voiceless  | /b/      | voiced     |
| պ        | /b/      | voiced     | /p/      | voiceless  |
| դ        | /t/      | voiceless  | /d/      | voiced     |
| տ        | /d/      | voiced     | /t/      | voiceless  |
| գ        | /k/      | voiceless  | /g/      | voiced     |
| կ        | /g/      | voiced     | /k/      | voiceless  |
| ճ        | /dʒ/     | voiced     | /tʃ/     | voiceless  |
| ջ        | /tʃʰ/    | aspirated  | /dʒ/     | voiced     |
| ձ        | /ts/     | voiceless  | /dz/     | voiced     |
| ծ        | /dz/     | voiced     | /ts/     | voiceless  |


### 2. Contextual ո and ե Behavior

- **ո**: Word-initial → /ʋɔ/ (diphthong), elsewhere → /ɔ/
- **ե**: Word-initial → /jɛ/ (with /j/), elsewhere → /ɛ/

### 3. Classical Orthography Markers (WA-specific)

- **իւ**: /ʏ/ (rounded high front) - retained in WA, reformed away in EA written in the Republic of Armenia
- **եա**: Retained in WA, reformed to յա in EA written in the Republic of Armenia

## Per-Word Analysis

(Original per-word analysis preserved from audit.)

## Conclusion

1. A dedicated phonetics/G2P module lives in **hytools** (e.g. `linguistics/phonetics.py`).
2. Voicing reference and vocabulary filter are in **linguistics.metrics**.
3. Contextual rules for ո/ե and classical orthography (իւ, եա) are documented here for implementation in core.
4. **Recommendation**: Implement full G2P in hytools with contextual rules and digraph handling.

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
- **իւ** [ju] - "yu" diphthong (իր = his/her, by dialect/register)

**Reformed orthography merged these:** Both became ու in Eastern Armenian spelling reforms.

#### Common Examples

| Classical (✓ USE THIS) | Reformed (✗ NEVER) | English | Pronunciation |
|------------------------|---------------------|---------|---------------|
| իւղ | յուղ | oil | yoogh |
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
1. Check Nayiri dictionary in MongoDB
2. Verify against classical dictionaries (Nayiri uses classical)
3. If uncertain, use the spelling with իւ rather than merging to ու

### Rule 2: Test Words Must Use Classical

**Current test words (all classical):**
- պետք = bedk (must/need)
- ժամ = zham (time/hour)
- ջուր = choor (water)
- ոչ = voch (no)
- իր = ir (his/her, by dialect/register)
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
- [ ] Cross-reference with Nayiri data in MongoDB
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
- Wikipedia Eastern Armenian entries (uses reformed)
- Google Translate (defaults to Eastern reformed)

---

## Code Implementation Notes

### phonetics.py Diphthong Handling

ARMENIAN_DIGRAPHS must include BOTH:
```python
ARMENIAN_DIGRAPHS = {
    'ու': {'ipa': 'u', 'approx': 'oo', 'difficulty': 1},    # Simple oo vowel
    'իւ': {'ipa': 'ju', 'approx': 'yu', 'difficulty': 1},  # Yu diphthong
}
```

These are DIFFERENT and must be handled separately:
- ու at word start: ուր = [oor] "where"
- իւ anywhere: իւր = [yur] / իր = [ir] (his/her)

### Database Normalization

**Storage:** Always store classical orthography
- Entry: իւղ (not յուղ)
- Entry: իւր or իր (never ուր for "his/her")


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
# Classical Armenian (Grabar) Identification — Research and Implementation

This document summarizes research on **Classical Armenian (Grabar)** identification protocols and the implementation in armenian-corpus-core for dialect tagging and filtering. The goal is to detect and tag text that is predominantly **Classical Armenian** (ISO 639-3: **xcl**; sometimes referred to as **hyc** in legacy or informal use) so it can be distinguished from modern Western (hyw) and Eastern (hye) Armenian.

---

## 1. What is Classical Armenian (Grabar)?

- **Grabar** (գրաբար) = “written/literary language.” The oldest attested form of Armenian (5th century CE), used in liturgy, biblical and patristic texts, and scholarly editions.
- **Orthography:** Classical/Mashtotsian orthography. Same 38-letter alphabet as traditional Western Armenian; differs from Soviet-era reformed Eastern Armenian orthography.
- **Relation to modern varieties:** Western Armenian retains classical orthography (diphthongs իւ, եա, etc.). Eastern Armenian (post-reform) uses different spellings (e.g. յու for իւ, մի for certain forms). So **orthographically**, Grabar is much closer to Western Armenian script; **lexically and morphologically** it has archaic features.

---

## 2. Identification Protocols — Research Summary

### 2.1 Orthographic markers (shared with Western Armenian classical spelling)

These are **necessary but not sufficient** for Grabar, because modern WA also uses them:

| Marker | Description | WA classical | Grabar |
|--------|-------------|--------------|--------|
| **իւ** | Diphthong (e.g. [ʏ]) | ✓ | ✓ |
| **եա** | Digraph (long /a/ or similar) | ✓ | ✓ |
| **ոյ** | Diphthong oy | ✓ | ✓ |
| **եւ** | ew digraph | ✓ | ✓ |

So orthography alone cannot separate Grabar from WA; we need **morphological and lexical** cues.

### 2.2 Morphological and lexical markers (Grabar-specific)

- **Case endings:** Classical has a full case system (nominative, accusative, genitive, dative, ablative, instrumental, locative) with distinct endings that modern WA/EA have simplified or lost.
- **Verb morphology:** Archaic verb endings and conjugations (e.g. middle voice, aorist stem forms) that are rare or absent in modern WA/EA.
- **Vocabulary:** Liturgical, biblical, and patristic terms; archaic pronouns and particles (e.g. **զ-** prefix for definite accusative, **յ-** prefix for “in/to”).
- **Word order and particles:** Different distribution of clitics and particles than modern prose.

### 2.3 Practical detection strategy

1. **Source heuristics:** Text from liturgy, Bible, church publications, or explicitly “Grabar” sources → tag as classical when appropriate.
2. **Orthography + density:** High density of classical orthography (իւ, եա, յ-, զ-) **plus** absence of modern WA markers (e.g. կը, պիտի, գոր) and presence of archaic morphology/lexicon → likely Grabar.
3. **Lexicon lists:** Maintain a small set of high-precision Grabar-only words/phrases (liturgical, biblical) and archaic function words; high hit rate → boost classical score.
4. **Rule-based classifier:** Extend the existing WA/EA rule-based classifier with a third “classical” label: add Grabar-specific rules (positive weight) and optionally down-weight strong modern WA/EA markers when classical markers are present.

---

## 3. Implementation in armenian-corpus-core

### 3.1 Dialect enum and language code

- **Dialect:** `CLASSICAL_ARMENIAN` added to `scraping/metadata.py` (or equivalent) for use in metadata and tagger.
- **Language code:** Use **xcl** (ISO 639-3) in `metadata.language_code`. The label **hyc** is documented as an alternative in some systems but **xcl** is the standard.

### 3.2 Dialect classifier

- **Location:** `linguistics/dialect_branch_classifier.py`.
- **Current behavior:** Returns `western` or `eastern` (or `inconclusive`) based on rule hits.
- **Extension:** Add a third label **`classical`** and a set of **Grabar-specific rules** (e.g. զ- prefix, liturgical phrases, archaic endings). When `classical_score` is above a threshold and dominates western/eastern, return `classical`; otherwise keep existing WA/EA logic.
- **Thresholds:** Tuned so that clearly liturgical/biblical excerpts get `classical` without over-tagging modern WA text that uses classical orthography.

### 3.3 Metadata tagger

- **SOURCE_METADATA:** Add entries for known Grabar sources (e.g. a dedicated “liturgical” or “grabar” source key) with `dialect: classical_armenian`, `language_code: "xcl"`.
- **Batch runs:** When processing documents from such sources, set `metadata.dialect` and `metadata.language_code` accordingly. For generic sources, the dialect classifier can be run and may set `classical_armenian` when rules fire.

### 3.4 WA filter and downstream

- **WA filter:** In `scraping/_helpers.py`, `try_wa_filter` and related logic currently treat “Western” as pass. Decide policy for Classical: either (a) treat classical as pass (so liturgical text is kept with corpus) or (b) treat as separate bucket and filter. Recommended: **treat classical as pass** and tag only, so Grabar text is retained and queryable by dialect.
- **FUTURE_IMPROVEMENTS / INDEX:** Document Classical Armenian support in the implementation status table (e.g. “Dialect classifier Classical (hyc/xcl): Implemented — rule-based classical label and metadata tagging”).

---

## 4. Grabar-specific rule set (indicative)

Examples of rules that can be added to the dialect classifier for Classical (positive weight for “classical”):

| Rule ID | Pattern / description | Weight | Note |
|---------|------------------------|--------|------|
| CL_ACCUSATIVE_Z | զ- prefix (definite accusative) | 2.0 | Very common in Grabar |
| CL_INSTRUMENTAL_Y | յ- prefix (in/to) in classical usage | 1.5 | Context-dependent |
| CL_LITURGICAL | Liturgical phrase list (e.g. Տէր ողորմյա) | 3.0 | High precision |
| CL_ARCHAIC_PRONOUN | Archaic pronoun forms | 2.0 | e.g. certain enclitics |
| CL_VERB_ENDINGS | Archaic verb endings (e.g. -եալ, -ոյ) | 1.5 | Needs word-boundary care |

Modern WA markers (կը, պիտի, etc.) can be given **negative** weight for classical when we want to prefer “modern WA” vs “Grabar” in borderline cases.

---

## 5. Data sources and testing

- **Sources:** Liturgical texts, Bible (e.g. Armenian Bible project), patristic excerpts, explicitly tagged “Grabar” corpora.
- **Testing:** Unit tests with short Grabar excerpts (high classical score), modern WA (high western, low classical), modern EA (high eastern, low classical), and mixed snippets to avoid false positives.

---

## 6. Summary

- **Identification protocol:** Combine (1) source-based tagging for known Grabar sources, (2) orthographic markers (shared with WA), (3) Grabar-specific morphological/lexical rules in the dialect classifier, and (4) language_code **xcl** (or label hyc where needed) in metadata.
- **Implementation:** Add `CLASSICAL_ARMENIAN` dialect, extend rule-based classifier with classical label and rules, add SOURCE_METADATA for Grabar sources, and treat classical as pass in WA filter so Grabar is retained and queryable.
- **Reference:** ISO 639-3 code **xcl** = Classical Armenian; **hyc** may appear in some systems as an alternative label.

This document can be updated as more Grabar-specific rules and sources are added.

# Armenian Regex Reference

Complete inventory of every regex and Armenian string pattern used in armenian-corpus-core, with dialect labeling (Western vs Eastern) and verification notes for Western Armenian correctness.

**Unicode ranges:**

- `\u0531-\u0587`: Armenian uppercase (Ա-Տ) + lowercase (ա-տ) + punctuation
- `\u0530-\u058F`: Full Armenian block (includes modifier letters, punctuation)
- `\u0560-\u058F`: Armenian lowercase subset (redundant with above)
- `\uFB13-\uFB17`: Armenian ligatures (ﬓ ﬔ ﬕ ﬖ ﬗ)

---

## Quick Reference: Dialect by File


| File                                | Dialect                               | Purpose                           |
| ----------------------------------- | ------------------------------------- | --------------------------------- |
| scraping/_helpers.py                | **WA** (positive), **EA** (negative)  | WA classifier, Wikitext           |
| linguistics/dialect_classifier.py   | **WA**, **EA**                        | Rule-based dialect classification |
| ingestion/discovery/book_inventory.py | **Neutral** (WA context)              | Title discovery                   |
| scraping/frequency_aggregator.py    | **Neutral**                           | Word tokenization                 |
| cleaning/armenian_tokenizer.py      | **Neutral**                           | Word extraction                   |
| augmentation/batch_worker.py        | **Neutral**                           | Armenian char detection           |
| ingestion/enrichment/biography_enrichment.py | **Both**                              | Death/place extraction            |
| linguistics/metrics/text_metrics.py | **WA** (classical), **EA** (reformed) | Orthography metrics               |
| ocr/postprocessor.py                | **Neutral**                           | OCR cleanup                       |


---

## 1. scraping/_helpers.py — WA/EA Dialect Classifier

**Purpose:** Western Armenian vs Eastern Armenian classification via orthographic and lexical markers.

### 1.1 WESTERN ARMENIAN — Classical Orthography Markers

**Note:** "Classical orthography" refers to *spelling* (diphthongs/digraphs), not Classical Armenian language. Eastern Armenians in Iran use classical orthography but speak Eastern. Classical markers: diphthongs/digraphs **ոյ, այ, իւ, եա, եօ, էյ**; **յ** at word end; **ութիւն** at word end = classical.

| Pattern (Unicode)                                                    | Armenian    | Romanization       | Purpose                                        | WA Correct? |
| -------------------------------------------------------------------- | ----------- | ------------------ | ---------------------------------------------- | ----------- |
| `\u0565\u0561`                                                       | եա          | ea                 | Digraph retained in WA; EA reformed to ya (յա) | ✅ Yes       |
| `\u056B\u0582`                                                       | իւ          | yu / yoo           | Classical digraph (not iw); EA dropped         | ✅ Yes       |
| `\u0574\u0567\u057B`                                                 | մէջ         | mej                | "in" (postposition)            | ✅ Yes       |
| `\u056B\u0582\u0580\u0561\u0584\u0561\u0576\u0579\u056B\u0582\u0580` | իւրաքանչիւր | yoorakanchyoor     | "each/every" (classical spelling)              | ✅ Yes       |
| `\u056C\u0565\u0566\u0578\u0582`                                     | լեզու       | lezou              | "language" (classical spelling)                 | ✅ Yes       |
| `\u0578\u0575`                                                       | ոյ          | uy                 | Diphthong (classical)                          | ✅ Yes       |


### 1.2 WESTERN ARMENIAN — Lexical Markers


| Pattern (Unicode)                            | Armenian | Romanization | Purpose                        | WA Correct? |
| -------------------------------------------- | -------- | ------------ | ------------------------------ | ----------- |
| `\u056F\u0568`                               | կը       | gu           | Present tense prefix           | ✅ Yes       |
| `\u056F\u055A`                               | կ՚       | g'           | Elided before vowel            | ✅ Yes       |
| `\u057A\u056B\u057F\u056B`                   | պիտի     | bidi         | WA future marker (beedee)      | ✅ Yes       |
| `\u0570\u0578\u0576`                         | հոն      | hon          | "there" (EA: այնտեղ)          | ✅ Yes       |
| `\u0570\u0578\u057D`                         | հոս      | hos          | "here" (EA: այստեղ)            | ✅ Yes       |
| `\u0561\u056C`                               | ալ       | al           | "also/too" (EA: էլ)            | ✅ Yes       |
| `\u0570\u056B\u0574\u0561`                   | հիմա     | hima         | "now"                          | ✅ Yes       |
| `\u0561\u0575\u057D\u057A\u0567\u057D`       | այսպէս   | aysbes       | "like this" (long-e)           | ✅ Yes       |
| `\u0561\u0575\u0576\u057A\u0567\u057D`       | այնպէս   | aynbes       | "like that" (long-e)           | ✅ Yes       |
| `\u0578\u0579\u056B\u0576\u0579`             | ոչինչ    | vochinch     | "nothing" (EA: ոչինչ, same)    | ✅ Yes       |
| `\u0562\u0561\u0576 \u0574\u0568`            | բան մը   | pan mu       | "something" (indefinite is մը/մըն postposition) | ✅ Yes |
| `\u0579\u0565\u0574`                         | չեմ      | chem         | Negative particle              | ✅ Yes       |
| `\u0574\u0565\u0576\u0584`                   | մենք     | menk         | "we" (EA: մենք, same)          | ✅ Yes       |
| `\u056B\u056C`                               | իլ       | il           | Passive verb suffix (e.g. խօսիլ); NOT indefinite | ✅ Yes |
| `\u0563\u0565\u0572\u0565\u0581\u056B\u056F` | գեղեցիկ  | keghetsig    | "beautiful"                    | ✅ Yes       |


### 1.3 WESTERN ARMENIAN — Vocabulary


| Pattern (Unicode)                            | Armenian | Romanization | Purpose                           | WA Correct? |
| -------------------------------------------- | -------- | ------------ | --------------------------------- | ----------- |
| `\u0573\u0565\u0580\u0574\u0561\u056f`       | ճերմակ   | jermag      | "white" (EA: սպիտակ)              | ✅ Yes       |
| `\u056d\u0578\u0570\u0561\u0576\u0578\u0581` | խոհանոց  | khohanots    | "kitchen"                         | ✅ Yes       |
| `\u0573\u0578\u0582\u0580`                   | ջուր     | chour         | "water" (EA: ջուր, same)          | ✅ Yes       |
| `\u0577\u0561\u057a\u056b\u056f`             | շապիկ    | shabig       | "shirt" (EA: շապիկ)               | ✅ Yes       |
| `\u0574\u0561\u0576\u0578\u0582\u056f`       | մանուկ   | manoog       | "child" (EA: մանկիկ)              | ✅ Yes       |
| `\u057f\u0572\u0561\u0575`                   | տղայ     | d'gha         | "boy" (WA with silent յ; EA: տղա) | ✅ Yes       |
| `\u056d\u0585\u057d\u056b\u056c`             | խօսիլ    | khosil       | "to speak" (EA: խոսել)            | ✅ Yes       |
| `\u0565\u0580\u0569\u0561\u056c`             | երթալ    | yertal       | "to go" (EA: գնալ)                | ✅ Yes       |
| `\u0568\u0576\u0565\u056c`                   | ընել     | unel         | "to do" (EA: անել)                | ✅ Yes       |
| `\u0578\u0582\u0566\u0565\u056c`             | ուզել    | ouzel        | "to want" (EA: ուզում եմ)         | ✅ Yes       |
| `\u0570\u0561\u057d\u056f\u0576\u0561\u056c` | հասկնալ  | hasgunal      | "to understand" (EA: հասկանալ)    | ✅ Yes       |
| `\u0561\u0580\u0564\u0567\u0576`             | արդէն    | arten        | "already" (EA: արդեն)             | ✅ Yes       |
| `\u0570\u0561\u057a\u0561`                   | հապա     | haba         | "then/so" (colloquial)            | ✅ Yes       |
| `\u0577\u0561\u057f`                         | շատ      | shad         | "very/much"                       | ✅ Yes       |
| `\u056f\u056b\u0580\u0561\u056f\u056b`       | կիրակի   | giragi       | "Sunday" (EA: same spelling)      | ✅ Yes       |


### 1.4 EASTERN ARMENIAN — Reform Markers (negative signal)


| Pattern (Unicode)                | Armenian | Romanization | Purpose                       | EA Correct? |
| -------------------------------- | -------- | ------------ | ----------------------------- | ----------- |
| `\u0574\u056B\u0575`             | միյ      | miy          | EA reformed digraph (from ea) | ✅ Yes       |
| `\u056D\u0576\u0561\u0575\u0574` | խնայմ    | khnaym       | EA reformed (WA: խնամ)        | ✅ Yes       |


### 1.5 Regex — Word-internal long-e, diphthongs


| Regex                                        | Purpose                                  | Dialect                  |
| -------------------------------------------- | ---------------------------------------- | ------------------------ |
| `[\u0531-\u0587]\u0567[\u0531-\u0587]`       | Word-internal long-e (է) between letters | **WA** (classical)       |
| `\u0561\u0575(?=[\s\u0589\u055D\u055E,.;:!?] | \Z)`                                     | Word-final -ay diphthong |
| `\u0578\u0575(?=[\s\u0589\u055D\u055E,.;:!?] | \Z)`                                     | Word-final -oy diphthong |


### 1.6 WA Authors (boost score)

*-եան transliterated as "ian" in Western Armenian*

| Pattern                                                  | Armenian  | Name          |
| -------------------------------------------------------- | --------- | ------------- |
| `\u0544\u0565\u056D\u056B\u0569\u0561\u0580`             | Մեղիթար   | Meghitar      |
| `\u0544\u056D\u056B\u0569\u0561\u0580\u0565\u0561\u0576` | Մխիթարեան | Mukhitarian  |
| `\u054F\u0561\u0576\u056B\u0567\u056C`                   | Տանիէլ    | Daniel        |
| `\u054E\u0561\u0580\u0578\u0582\u056A\u0561\u0576`       | Վարուժան  | Varoujan    |
| `\u054D\u056B\u0561\u0574\u0561\u0576\u0569\u0578`       | Սիամանթօ  | Siamanto    |
| `\u0536\u0561\u0580\u056B\u0586\u0565\u0561\u0576`       | Զարիբեան  | Zarifian    |
| `\u054F\u0565\u0584\u0567\u0565\u0561\u0576`             | Թէքէեան   | Tekeian     |
| `\u054D\u0561\u0580\u0561\u0586\u0565\u0561\u0576`       | Սարաֆեան  | Sarafian    |
| `\u0547\u0561\u0570\u0576\u0578\u0582\u0580`             | Շահնուր   | Shahnour    |
| `\u0536\u0561\u0580\u0564\u0561\u0580\u0565\u0561\u0576` | Զարդարեան | Zartarian   |
| `\u0536\u0561\u057A\u0567\u056C`                         | Զապէլ     | Zabel       |
| `\u0535\u057D\u0561\u0575\u0565\u0561\u0576`             | Եսայեան   | Yesayian    |
| `\u0540\u0561\u0574\u0561\u057D\u057F\u0565\u0572`       | Համաստեղ  | Hamasdegh   |
| `\u0536\u0578\u0570\u0580\u0561\u057A`                   | Զոհրապ    | Zohrab      |


### 1.7 WA Publication Cities


| Pattern                                            | Armenian | Place                | Note                             |
| -------------------------------------------------- | -------- | -------------------- | -------------------------------- |
| `\u054A\u0567\u0575\u0580\u0578\u0582\u0569`       | Պէյրութ  | Beyrout (Beirut)     | _helpers.py, book_inventory.py ✅ |
| `\u054A\u0578\u056C\u056B\u057D`                   | Պոլիս    | Bolis (Istanbul)     | ✅                                |
| `\u0553\u0561\u0580\u056B\u0566`                   | Փարիզ    | Pariz (Paris)        | ✅                                |
| `\u0533\u0561\u0570\u056B\u0580\u0567`             | Գահիրէ   | Kahire (Cairo)       | ✅                                |
| `\u054A\u0578\u057D\u0569\u0578\u0576`             | Պոսդոն   | Boston               | ✅                                |
| `\u0546\u056B\u0582 \u0535\u0578\u0580\u0584`      | Նիւ Եորք | Nyu York           | ✅                                |
| `\u0540\u0561\u056C\u0567\u057A`                   | Հալէպ    | Haleb (Aleppo)       | ✅                                |
| `\u0544\u0578\u0576\u0569\u0580\u0567\u0561\u056C` | Մոնթրէալ | Monturial (Montreal) | ✅                                |


---

## 2. ingestion/discovery/book_inventory.py — Title Discovery

**Purpose:** Book/manuscript title extraction from MongoDB corpus.

### 2.1 General


| Regex              | Purpose                         | Dialect |
| ------------------ | ------------------------------- | ------- |
| `[\u0530-\u058F]+` | Any Armenian character sequence | Neutral |


### 2.2 Context Markers (substring match)


| Pattern                                                  | Armenian  | Romanization | Purpose            |
| -------------------------------------------------------- | --------- | ------------ | ------------------ |
| `\u056f\u0561\u0580\u0564`                               | կարդ      | gart         | "read" (verb: կարդալ) |
| `\u0563\u056b\u0580\u0584`                               | գիրք      | kirk         | "book"             |
| `\u0571\u0565\u0580\u0561\u0563\u056b\u0580`             | ձեռագիր   | tserakir     | "manuscript"       |
| `\u0563\u0580\u0561\u056e`                               | գրած      | k'radz       | "wrote"            |
| `\u0544\u0561\u0569\u0565\u0561\u0576`                   | Մատեան    | madian       | "manuscript/codex" |
| `\u0536\u0578\u0572\u0578\u0582\u056e\u0561\u0581\u0582` | Ժողովածու | zhoghovadzou | "collection"       |


### 2.3 "Book of" / Title-start Patterns (regex)


| Regex                                                                 | Armenian     | Romanization  | WA Correct?   |
| --------------------------------------------------------------------- | ------------ | ------------- | ------------- |
| `^\u0563\u056b\u0580\u0584\s`                                         | Գիրք         | kirkʿ         | ✅ Yes         |
| `^\u0536\u0578\u0572\u0578\u0582\u056e\u0561\u0581\u0582\s`           | Ժողովածու    | Zhoghovadzou  | ✅ Yes         |
| `^\u054a\u0561\u0569\u0574\u0582\u0569\u056b\u0582\u0576`             | Պատմութիւն   | Badmoutyun    | ✅ Yes (fixed) |
| `^\u054f\u0561\u0563\u0565\u0580`                                     | Տաղեր        | Dagher        | ✅ Yes         |
| `^\u054f\u0561\u0563\u0565\u0580\u0563\u0582\u0569\u056b\u0582\u0576` | Տաղերգութիւն | Dagherkoutyun | ✅ Yes (fixed) |
| `^\u0535\u0580\u056f\u0565\u0580\s`                                   | երկիր        | Yergir        | ✅ Yes (works) |


### 2.4 Exclusion — Person Prefixes


| Pattern               | Armenian | Meaning         |
| --------------------- | -------- | --------------- |
| `\u054e\u0580\u0564.` | Վրդ.     | Vrt. (Reverend) |
| `\u0564\u0578\u056f.` | Դոկ.     | Tok. (Doctor)   |


### 2.5 Exclusion — Places


| Pattern                                            | Armenian | Place    |
| -------------------------------------------------- | -------- | -------- |
| `\u054a\u0567\u0575\u0580\u0582\u0569`             | Պէյրութ  | Beyrout |
| `\u054a\u0578\u056c\u056b\u057d`                   | Պոլիս    | Bolis    |
| `\u0553\u0561\u0580\u056b\u0566`                   | Փարիզ    | Pariz    |
| `\u0540\u0561\u056c\u0567\u057a`                   | Հալէպ    | Haleb    |
| `\u0535\u0580\u0582\u0561\u0576`                   | Երեւան   | Yerevan  |
| `\u0544\u0578\u0576\u0569\u0580\u0567\u0561\u056c` | Մոնթրէալ | Monturial |
| `\u0546\u056b\u0582 \u0535\u0578\u0580\u0584`      | Նիւ Եորք | Nyu York |


### 2.7 Quoted Title Extraction


| Regex                      | Purpose                     |
| -------------------------- | --------------------------- |
| `\u00AB([^\u00BB]+)\u00BB` | «...» (Armenian guillemets) |
| `"([^"]+)"`                | Double-quoted               |


---

## 3. linguistics/dialect_branch_classifier.py — Rule-based Classifier

**Purpose:** Dialect/Branch classification using morphology and orthography.

### 3.1 WESTERN ARMENIAN


| Pattern | Armenian  | Purpose                                                                 |
| ------- | --------- | ----------------------------------------------------------------------- |
| `իւ`    | իւ        | Classical digraph (EA: յու/ու)                                          |
| `(^     | \s)մը($   | \s                                                                      |
| `(^     | \s)կը($   | \s                                                                      |
| `(^     | \s)պիտի($ | \s                                                                      |
| `(^     | \s)չ($   | \s                                                                      |

**Negation:** Western Armenian marks negation with **չ** at the beginning of a word. Any word starting with **չ** (e.g. չեմ, չէ, չուզեմ) indicates negative. Purpose: strong WA signal.


### 3.2 EASTERN ARMENIAN


| Pattern     | Armenian          | Classical (WA) equivalent |
| ----------- | ----------------- | ------------------------- |
| `(^         | \s)յուղ($         | \s                        |
| `(^         | \s)գյուղ($        | \s                        |
| `(^         | \s)ճյուղ($        | \s                        |
| `(^         | \s)զամբյուղ($     | \s                        |
| `(^         | \s)ուրաքանչյուր($ | \s                        |
| `\bpetik\b` | (Latin)           | Transliteration cue       |
| `\bjayur\b` | (Latin)           | Transliteration cue       |


---

## 4. scraping/frequency_aggregator.py


| Regex                           | Purpose                    | Note                                                                                 |
| ------------------------------- | -------------------------- | ------------------------------------------------------------------------------------ |
| `[\u0530-\u058F\u0560-\u058F]+` | Armenian word tokenization | **Redundant:** \u0560-\u058F is subset of \u0530-\u058F. Consider `[\u0530-\u058F]+` |


---

## 5. scraping/_helpers.py — Wikitext


| Regex  | Purpose | Armenian?                      |
| ------ | ------- | ------------------------------ |
| `(File | Image   | \u054a\u0561\u057f\u056f):.*?` |


---

## 6. scraping/rss_news.py

**ARMENIAN_KEYWORDS:** Latin transliteration only (armenia, armenian, hye, yerevan, etc.). No Armenian script. Used for filtering international RSS feeds.

---

## 7. cleaning/armenian_tokenizer.py — Word Extraction


| Regex                                        | Purpose                          | Dialect     |
| -------------------------------------------- | -------------------------------- | ----------- |
| `[\u0531-\u0556\u0561-\u0587\uFB13-\uFB17]+` | Armenian words (incl. ligatures) | **Neutral** |


**Ligature map (U+FB13–U+FB17):** ﬓ→մն, ﬔ→մե, ﬕ→մի, ﬖ→վն, ﬗ→մխ

---

## 8. augmentation/batch_worker.py


| Regex                          | Purpose                                | Dialect     |
| ------------------------------ | -------------------------------------- | ----------- |
| `[\u0531-\u0587\uFB13-\uFB17]` | Single Armenian char (incl. ligatures) | **Neutral** |


---

## 9. ingestion/enrichment/biography_enrichment.py — Author Profile Extraction


| Regex                    | Armenian | Romanization | Purpose                            | Dialect  |
| ------------------------ | -------- | ------------ | ---------------------------------- | -------- |
| `հրաժեշտ\s*–?\s*(\d{4})` | հրաժեշտ  | hrajesht     | "farewell" (death year)            | **Both** |
| `մահ\s*–?\s*(\d{4})`     | մահ      | mah          | "death" (death year)               | **Both** |
| `[Ա-Ֆ][ա-ֆ]{3,15}`       | —        | —            | Place names (cap + 3–15 lowercase) | **Both** |


---

## 10. linguistics/metrics/text_metrics.py — Orthography Metrics


| Pattern | Armenian | Purpose          | Dialect |
| ------- | -------- | ---------------- | ------- |
| `ո`     | ո        | Classical marker | **WA**  |
| `իւ`    | իւ       | Diphthong        | **WA**  |
| `եա`    | եա       | Digraph          | **WA**  |
| `յու`     | յու        | Reformed marker  | **EA**  |
| `ույ`     | ույ        | Reformed marker  | **EA**  |

**Orthography metrics captured:** classical markers (ո, իւ, եա counts), reformed markers (ա, ե counts), classical_to_reformed_ratio. Used to distinguish classical (WA) vs reformed (EA) orthography.

**Pronouns list:** ես, դու, նա, ան, ինք, մենք, դուք, նրանք, այն, սա — used in both dialects at different rates; Western also uses **ան** for he/she/it. Used for semantic metrics (pronoun frequency), not dialect classification.

---

## 11. ocr/postprocessor.py — OCR Cleanup


| Regex                                 | Purpose                                | Dialect     |
| ------------------------------------- | -------------------------------------- | ----------- |
| `[^\u0530-\u058F\u0020-\u007E\s]{4,}` | Garbage (non-Armenian, non-ASCII runs) | **Neutral** |
| `(?<=\S)\.\.` → `։`                   | Replace `..` with Armenian full stop   | **Neutral** |


**Preserved punctuation:** ՝ (comma), ՞ (question), ։ (full stop), ՛ (emphasis), ՜ (exclamation)

---

## 12. Sentence Splitting (Armenian Full Stop)


| File                                    | Regex            | Purpose               |
| --------------------------------------- | ---------------- | --------------------- |
| augmentation/strategies.py              | `(?<=[։.!?])\s+` | Split on sentence end |
| linguistics/metrics/dialect_distance.py | `(?<=[։.!?])\s+` | Split on sentence end |


**Armenian full stop:** `։` (U+0589)

---

## 13. ingestion/discovery/author_extraction.py


| Regex       | Armenian                 | Purpose          |
| ----------- | ------------------------ | ---------------- |
| `[,\.։՝\-]` | ։ (full stop), ՝ (comma) | Strip from names |


---

## 14. Summary by Dialect


| Dialect     | Files                                                                                                | Purpose                                                                             |
| ----------- | ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **Western** | _helpers.py, dialect_classifier.py, book_inventory.py, text_metrics.py                               | WA markers, classical orthography, WA vocabulary, WA authors/cities, title patterns |
| **Eastern** | _helpers.py, dialect_classifier.py, text_metrics.py                                                  | EA reform markers (negative signal), EA reformed spellings                          |
| **Neutral** | book_inventory.py, frequency_aggregator.py, armenian_tokenizer.py, batch_worker.py, postprocessor.py | Armenian script detection, tokenization, OCR                                        |


---

## 15. Bugs Fixed (Western Armenian)


| Item         | Location          | Fix                       |
| ------------ | ----------------- | ------------------------- |
| Պատմութիւն   | book_inventory.py | Changed final ր → ն       |
| Տաղերգութիւն | book_inventory.py | Changed final ր → ն       |
| Պէյրութ      | book_inventory.py | Added missing ո (7 chars) |

# Armenian-Corpus-Core — Audit Report

**Audit Date:** 2026-03-08  
**Scope:** Package structure, CI/CD, data flow, augmentation, scraping, and documentation.

---

## 1. CI/CD Automation — What It Is and Implications

### What Is CI/CD?

**CI/CD** stands for **Continuous Integration** and **Continuous Delivery/Deployment**:

- **Continuous Integration (CI):** Automatically build, test, and validate code whenever changes are pushed (e.g. on every commit or pull request). Catches integration issues early.
- **Continuous Delivery (CD):** Automatically prepare and deliver artifacts (e.g. built packages, reports) so they can be deployed or used without manual steps.
- **Continuous Deployment:** Automatically deploy to production after successful CI. (Often not used for research/corpus projects.)

### What This Project Has

The project uses **GitHub Actions** for CI/CD:


| Component         | Location                         | Purpose                                     |
| ----------------- | -------------------------------- | ------------------------------------------- |
| Scraping workflow | `.github/workflows/scraping.yml` | Scheduled and manual scraping pipeline runs |


**Triggers:**

- **Weekly (Mondays 03:00 UTC):** Wikipedia, Wikisource, Archive.org, HathiTrust, LOC
- **Daily (06:00 UTC):** Newspapers, Eastern Armenian news, CulturaX, RSS, English sources
- **Manual:** `workflow_dispatch` with configurable stages

**Steps:**

1. Checkout code, install package (`pip install -e '.[all]'`)
2. Restore cache (`data/raw/`, `data/logs/`, `data/frequencies/`)
3. **[REMOVED]** Ingest cached JSONL into MongoDB (previously `integrations.database.run_ingestion`)
4. Determine stages from schedule or manual input
5. Run scraping pipeline (`scraping.runner run`)
6. Upload artifacts: `pipeline_summary.json`, frequency lists

### Implications


| Implication                | Description                                                                            |
| -------------------------- | -------------------------------------------------------------------------------------- |
| **Automated data refresh** | Corpus data is refreshed on a schedule without manual runs.                            |
| **Reproducibility**        | Same steps run in a controlled environment (Ubuntu, Python 3.12, MongoDB 7).           |
| **Artifact retention**     | Pipeline summary and frequency lists are stored as GitHub artifacts (30–90 days).      |
| **MongoDB dependency**     | CI uses a MongoDB service container; scraping and ingestion require MongoDB.           |
| **No local storage in CI** | Output goes to MongoDB; local JSON/CSV for metrics is deprecated.                      |
| **Cache behavior**         | Cache key includes `run_number`; cache is best-effort and may not persist across runs. |


### What Is Not Automated (Yet)

- **Tests:** No dedicated test workflow (e.g. `pytest` on push/PR).
- **Augmentation:** Augmentation pipeline is not run in CI.
- **Cleaning:** Cleaning runs as part of scraping when `cleaning` stage is enabled; not a separate workflow.
- **Book catalog / author research:** Run locally or via cron/systemd (see `docs/LOCAL_SCHEDULER.md`).

---

## 2. Package Structure

### Flat Packages (Current)

The project uses **flat packages** only. The legacy `armenian_corpus_core` package does not exist.


| Package          | Purpose                                                                 |
| ---------------- | ----------------------------------------------------------------------- |
| `scraping`       | Data acquisition (Wikipedia, LOC, newspapers, etc.), registry, metadata |
| `cleaning`       | Text normalization, WA filtering, MongoDB cleaning                      |
| `augmentation`   | LLM-based augmentation, metrics, drift detection                        |
| `linguistics`    | Dialect distance, text metrics, vocabulary filter                       |
| `ocr`            | Tesseract pipeline, preprocessing, cursive detection                    |
| `research`       | Book inventory, author research, coverage analysis                      |
| `integrations`   | MongoDB client, Anki                                                    |
| `core_contracts` | Types, hashing, domain contracts                                        |


### Import Conventions

- Use `ingestion.discovery.book_inventory`, `ingestion.acquisition.loc`, `augmentation.runner`, etc.
- Do **not** use `armenian_corpus_core.`* or `src.*` — these are removed.
- See `docs/IMPORT_REDIRECTS.md` for full mapping.

---

## 3. Data Flow and Persistence

### Primary Storage: MongoDB


| Collection             | Purpose                                             |
| ---------------------- | --------------------------------------------------- |
| `documents`            | Scraped/cleaned text, metadata, dialect tags        |
| `augmented`            | Augmented documents (when `output_backend=mongodb`) |
| `book_inventory`       | Book catalog (when config has `mongodb_uri`)        |
| `augmentation_metrics` | Per-task and batch metric cards, reports            |
| `word_frequencies`     | Aggregated word counts by source                    |
| `catalogs`             | LOC, archive_org, etc. catalog state                |


### No Local JSON/CSV for Metrics

- **Metrics pipeline:** All output goes to MongoDB (`augmentation_metrics`). No `cache/metric_cards/*.json` or CSV export.
- **Book inventory:** When MongoDB is configured, inventory is stored in `book_inventory`; no `data/book_inventory.jsonl`.

### Local Files (Minimal)


| Path                   | Purpose                                                |
| ---------------------- | ------------------------------------------------------ |
| `data/raw/`            | Cached JSONL before ingestion (CI restores from cache) |
| `data/logs/`           | Pipeline summary, runner logs                          |
| `data/frequencies/`    | Frequency lists (also uploaded as artifacts)           |
| `config/settings.yaml` | Pipeline configuration                                 |


---

## 4. Implementation Summary (Recent Changes)

### Metrics Pipeline → MongoDB Only

- `MetricsComputationPipeline` takes `mongodb_client`; per-task cards and batch reports stored in `augmentation_metrics`.
- `runner metrics` removed `--out` and `--export-csv`; all output to MongoDB.

### Cursive Detection in OCR

- `ocr/preprocessor.py`: `estimate_cursive_likelihood()` (contour elongation, stroke-width variance).
- `binarize()` and `preprocess()` support `cursive_mode` (Niblack/Sauvola, smaller block, optional morphology).
- Config: `detect_cursive`, `cursive_threshold` in `config/settings.yaml`.

### Scraping Workflow

- Stage names aligned with runner: `wikipedia_wa`, `wikipedia_ea`, `ea_news`, `loc`, etc.
- Artifact path: `data/logs/pipeline_summary.json`.
- Ingestion step: **removed** (previously `integrations.database.run_ingestion --raw-only`).

### Run Ingestion Script

- `integrations/database/run_ingestion.py`: **removed** (JSONL caching path is no longer supported).
- Used by CI; available for manual runs.

### LOC and Background Design

- LOC is a normal pipeline stage (like archive_org, hathitrust).
- Background: `scraping.runner run --background` (full pipeline) or `scraping.loc run --background` (LOC only).
- See `docs/SCRAPING_RUNNER_AND_LOC.md`.

### Book Catalog MongoDB

- `BookInventoryManager` uses MongoDB when `config` has `database.mongodb_uri`.
- `book_inventory_runner` defaults to `config/settings.yaml`.
- Migration: `python -m ingestion.discovery.migrate_book_inventory --config config/settings.yaml`.

### Import Cleanup

- Removed `armenian_corpus_core` and `src` fallbacks across research, augmentation, cleaning, tests.
- All imports use flat packages.

### Local Scheduler

- `docs/LOCAL_SCHEDULER.md`: Cron and systemd examples for scraping, cleaning, augmentation, book catalog, author research.

---

## 5. Component Status


| Component            | Implemented | Integrated | Notes                                 |
| -------------------- | ----------- | ---------- | ------------------------------------- |
| scraping.runner      | ✅           | ✅          | Central pipeline entry point          |
| cleaning.run_mongodb | ✅           | ✅          | Via `scraping.runner --only cleaning` |
| augmentation.runner  | ✅           | ✅          | CLI: estimate, run, status, metrics   |
| augmentation metrics | ✅           | ✅          | MongoDB only; `runner metrics`        |
| run_ingestion        | ❌ Removed | ❌ Removed | Not used (JSONL path removed)         |
| book_inventory       | ✅           | ✅          | MongoDB when config present           |
| cursive detection    | ✅           | ✅          | OCR preprocessor                      |
| CI scraping workflow | ✅           | ✅          | Weekly + daily + manual               |


---

## 6. Recommendations

1. **Add a test workflow** — Run `pytest` on push/PR to catch regressions.
2. **Document CI limitations** — Cache and MongoDB are ephemeral in CI; document expectations for artifact retention.
3. **Optional: augmentation in CI** — If desired, add a separate workflow or stage for augmentation (requires LLM availability).
4. **Keep metrics MongoDB-only** — No reintroduction of local JSON/CSV for metrics.

---

## 7. Related Documentation


| Document                                                 | Purpose                        |
| -------------------------------------------------------- | ------------------------------ |
| `docs/IMPORT_REDIRECTS.md`                               | Flat package mapping           |
| `docs/SCRAPING_RUNNER_AND_LOC.md`                        | Runner design, LOC, background |
| `docs/LOCAL_SCHEDULER.md`                                | Cron/systemd examples          |
| `docs/SOURCE_DOCUMENT_STORAGE_AND_AUGMENTATION_AUDIT.md` | Storage and augmentation audit |
| `docs/FUTURE_IMPROVEMENTS.md`                            | Planned work                   |
| `docs/DATA_PERSISTENCE_AND_FILE_USAGE.md`                | Data storage overview          |



