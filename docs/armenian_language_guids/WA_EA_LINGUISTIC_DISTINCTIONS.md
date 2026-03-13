# Western vs Eastern Armenian: Linguistic Distinctions

**Purpose:** Reference for dialect detection, sentence generation tests, and word-use checks.

---

## 1. Analytic vs Synthetic

- **Eastern Armenian** tends to be more analytic: uses auxiliary words for tense and mood.
- **Western Armenian** uses more verb inflections and preverbal particles.

---

## 2. Indefinite Article

| Dialect | Word | Position | Example |
|---------|------|----------|---------|
| **Eastern** | մի (mi) | Before noun | մի տուն (mi doon) = a house |
| **Western** | մը / մըն (mu/mun) | After noun | տուն մը (doon mu) = a house |

**Western contextual form:** մըն before verb forms (են, ես, է, etc.) and ալ:
- տուն մըն է = it is a house
- թռչուն մըն ալ = also a bird

**Detection:** `մի\s+` before a noun = EA. `\s+մը($|\s)` or `\s+մըն($|\s)` after noun = WA.

---

## 3. Present Tense

| Dialect | Structure | Example |
|---------|-----------|---------|
| **Eastern** | Subject + verb(-ում) + auxiliary (եմ, etc.) | Ես վազում եմ (yes vazum em) = I run |
| **Western** | Subject + gu/g' + verb(-եմ) | Ես կը վազեմ (yes gu vazem) = I run |

**Western:** Preverbal particle **կը** (gu) or **կ՚** (g') before the verb.
**Eastern:** Auxiliary verb after the main verb (e.g. -ում + եմ).

---

## 4. Future and Present Progressive

| Feature | Western | Eastern |
|---------|---------|---------|
| Future | **պիտի** (bidi) before verb | Different construction |
| Present progressive | **կոր** (gor) as suffix or with կը/կ՚ | Not typical in standard EA |

---

## 5. Verb Stems

| Meaning | Eastern | Western |
|---------|---------|---------|
| to speak | խոսել (khosel) | խօսիլ (khosil) |
| to run | ... | վազել → վազեմ |

---

## 6. Case System

| Dialect | Cases |
|---------|-------|
| **Eastern** | 7 distinct cases |
| **Western** | 4 cases (some merged) |

**Western informal:** Accusative merges with dative; Eastern keeps them separate.

---

## 7. Adjectives

**Both:** Adjectives come before the noun and do not change form for case or number.

---

## 8. Letter ւ (viwm)

- **Eastern:** ւ is often dropped or changed to **վ**.
- **Western:** ւ retained in diphthongs (ու, իւ) and as semi-vowel.

---

## 9. Vocabulary: Dialect-Specific and False Friends

| Word | Eastern | Western | Notes |
|------|---------|---------|-------|
| egg | ձու (dzu) | հավկիթ (havkit) | Different roots |
| little rose | վարդիկ (vardik) | — | Sounds like |
| underwear | — | վարտիք (vardig) | WA "vardig" ≈ EA "vardik" (false friend) |

---

## 10. Loanword Geographic Clues

| Loan source | Likely dialect / region |
|-------------|-------------------------|
| Russian | Eastern (Armenia, former USSR) |
| Modern Farsi | Eastern (Iran) |
| Arabic | Western (Lebanon, Syria, Iraq) |
| Turkish | Western (Ottoman diaspora) |
| French | Western (Lebanon, France/Paris) |
| Spanish | Western (Argentina diaspora) |

---

## 11. Detection Rules (for implementation)

### WA positive signals
- Postposed indefinite: `noun + մը` or `noun + մըն`
- Preverbal present: `կը` or `կ՚` before verb
- Preverbal future: `պիտի`
- Present progressive: `կոր` (gor)
- Verb suffix `-իլ` (e.g. խօսիլ)
- Classical orthography (իւ, ութիւն, etc.)

### EA positive signals
- Preposed indefinite: `մի` before noun
- Auxiliary-after structure: verb-ում + եմ/եք/են
- Reformed spelling (յուղ, գյուղ, etc.)
- ւ dropped or changed to վ
- Vocabulary: ձու (egg), dzu
- Russian loanwords → likely EA speaker

---

## 12. Sentence Generation Tests

When generating or validating sentences:

1. **Indefinite article:** WA must use `noun + մը`; EA uses `մի + noun`.
2. **Present:** WA `կը verb-եմ`; EA `verb-ում եմ`.
3. **Vocabulary:** Use havgit (WA) or dzu (EA) for "egg" depending on target dialect.

---

## 13. Loanword Tracking

`linguistics.loanword_tracker` identifies loanwords by source language:
- **Russian** → likely EA (Armenia, former USSR)
- **Turkish** → likely WA (Ottoman diaspora)
- **Arabic** → likely WA (Lebanon, Syria, Iraq)
- **French** → likely WA (Lebanon, France)
- **Spanish** → likely WA (Argentina diaspora)
- **Farsi** → likely EA (Iran)

Per-text reports include: `counts_by_language`, `unique_loanwords`, `loanword_ratio`.
Use `analyze_loanwords(text, text_id=..., source=...)` and integrate into ingestion metrics.
