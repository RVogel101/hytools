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
