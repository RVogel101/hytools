# Stem Catalog Design: Rules-Based Stem List for Armenian

**Purpose:** Design a rules-based stem catalog to support compound-word analysis, prefix/suffix-only stems, and consistent normalization. Armenian builds words via compounding and affixation; stems may have distinct meanings only as prefix or suffix, and connecting vowels (ա, ե) must be accounted for.

See also: `ETYMOLOGY_STEM_TRANSLITERATION_STRATEGIES.md`, `LOANWORD_TRACKING_ANALYSIS.md`, and `linguistics/etymology_db.py` (etymology collection used for lookup).

---

## 1. Goals

- **Stem list:** Curated set of roots/stems with metadata (position: prefix | suffix | free; meaning; WA/EA/Classical variants).
- **Compound-word handling:** Split compounds into constituent stems; support multiple stems per word.
- **Position-bound stems:** Stems that have a fixed meaning only when in prefix or suffix position (e.g. ան- “not”, -ութիւն “-ness”).
- **Connecting sounds:** Model linking vowels ա and ե between stems (e.g. գիր + ա + խոս → գրախոս “critic”; արք + ե + ա → արքեա “royal”).
- **Pipeline:** Strip known affixes → lookup remainder in etymology/stem catalog → return stem(s) + confidence.

---

## 2. Armenian Word Formation

### 2.1 Compounding

Armenian forms many words by combining two or more roots:

- **Noun + noun:** գիր “writing” + խոս “speech” → գրախոս “critic” (via connecting ա).
- **Adjective + noun:** արքայ “king” + -եա (adj. suffix) → արքեա “royal”.
- **Prefix + stem:** ան- “not” + կարելի “possible” → անկարելի “impossible”.
- **Stem + suffix:** կար “can” + -ութիւն “-ness” → կարութիւն “ability”.

The **connecting vowel** is often **ա** or **ե** between two roots, and can appear as part of a suffix (e.g. -եա, -ական, -ային).

### 2.2 Position-Bound Stems

Some forms have a clear meaning only in a specific position:

| Form   | Position | Meaning / function      | Example (WA)        |
|--------|----------|-------------------------|---------------------|
| ան-    | prefix   | negation, “un-”         | անկարելի, անուն    |
| դժ-    | prefix   | “bad”, “ill”            | դժբախտ              |
| չ-     | prefix   | negation (verbal)       | չգիտեմ              |
| -ութիւն| suffix   | abstract noun “-ness”   | կարութիւն, բարութիւն|
| -ություն| suffix  | (EA spelling) same      | կարություն          |
| -արան  | suffix   | place “-ary, -orium”    | գրադարան           |
| -ացնել | suffix   | causative verb          | ճանաչացնել          |
| -անալ  | suffix   | inchoative “become”     | մեծանալ             |
| բարի-  | prefix   | “good”, “well”          | բարիագոյն           |
| ամենա- | prefix   | “every”, “all”          | ամենատարի           |

Stems that are **free** (can stand alone) vs **bound** (only in compound) must be tagged so the stemmer does not over-strip (e.g. չ- is bound; չէ “no” is a word).

### 2.3 Connecting Vowels: ա and ե

- **ա:** Often appears between two roots: գիր + ա + խոս → գրախոս. After some roots the connecting vowel is dropped or altered (e.g. vowel reduction in classical orthography).
- **ե:** Used in adjectival/relational suffixes: -եա, -ական, -ային; also in compounds like արքայ + ե + ա → արքեա.

**Design implication:** The stem list and rules must:
1. List possible connecting vowels (ա, ե) as linking elements.
2. When splitting a compound, try both “stem1 + ա + stem2” and “stem1 + ե + stem2” (and no vowel) for lookup.
3. Normalize orthographic variants (e.g. -ութիւն vs -ություն) before matching.

---

## 3. Schema for the Stem Catalog

Stems can live in the same MongoDB collection as etymology (extended schema) or in a dedicated `stems` collection. Recommended: extend **etymology** with optional stem-related fields, or add a **stems** collection that references etymology by lemma.

### Option A: Extended etymology document

```python
{
    "lemma": str,
    "source": "wiktionary" | "nayiri" | "manual" | "rule_based",
    "confidence": float,
    "etymology_text": str | None,
    "relationships": list[str],
    # Stem-catalog extensions:
    "stem_type": "free" | "prefix" | "suffix" | "bound_root",  # optional
    "affix_form": str | None,   # e.g. "ան-", "-ութիւն"
    "connecting_vowel": "ա" | "ե" | None,  # preferred linking vowel when used in compounds
    "updated_at": datetime,
}
```

### Option B: Dedicated stems collection

```python
{
    "stem_id": str,             # normalized form (e.g. "ան", "ութիւն")
    "form": str,                # display form (e.g. "ան-", "-ութիւն")
    "position": "prefix" | "suffix" | "free",
    "meaning_gloss": str | None,
    "connecting_vowel": "ա" | "ե" | None,
    "variants": list[str],      # WA/EA/Classical spellings
    "source": "nayiri" | "rule_based" | "manual",
    "updated_at": datetime,
}
```

Affix stripping then uses `stems` for known affixes and `etymology` (or a combined index) for the remaining base.

---

## 4. Indicative Affix List (Rules-Based Pass)

Curate a minimal list for the first rule-based pass. Orthography: classical (WA) and reformed (EA) variants where different.

### Prefixes

| Affix   | Meaning / function   | Example (WA)   | Note                    |
|---------|---------------------|----------------|-------------------------|
| ան-     | not, un-            | անկարելի       | Very productive         |
| դժ-     | bad, ill            | դժբախտ         |                         |
| դձ-     | (variant)           | —              | Rare                    |
| չ-      | negation (verbal)   | չգիտեմ         | Bound; do not strip in չէ|
| բարի-   | good, well          | բարիագոյն      |                         |
| ամենա-  | every, all          | ամենատարի      |                         |
| ներ-    | down, under         | ներքին         |                         |
| հան-    | out, ex-            | հանել          |                         |
| նա-     | re- (again)         | նախանձ         |                         |

### Suffixes

| Affix      | Meaning / function   | Example (WA)   | Variants      |
|------------|----------------------|----------------|---------------|
| -ութիւն   | abstract noun        | կարութիւն      | -ություն (EA)|
| -ստան     | (place/suffix)       | —              |               |
| -արան     | place “-ary”         | գրադարան       |               |
| -ացնել    | causative            | ճանաչացնել     |               |
| -անալ     | become               | մեծանալ        |               |
| -եա       | adjectival           | արքեա          |               |
| -ական     | adjectival           | ազգական        |               |
| -ային     | relational adj       | տարեկան        |               |
| -ավոր     | having, -ful         | պատուավոր      | -ավոր (EA)   |

Exact Unicode and WA/EA variants should be curated in a data file (e.g. `data/stem_affixes.yaml`) and loaded by the stemmer.

---

## 5. Algorithm: Stemmer with Stem Catalog

1. **Normalize input:** NFC, decompose ligatures, lowercase (same as tokenizer).
2. **Suffix strip (longest first):** Match against known suffixes; remove and record `affix_removed`; repeat on remainder if desired (e.g. կարութիւն → կար + -ութիւն).
3. **Prefix strip:** Match known prefixes; remove and record; repeat.
4. **Lookup remainder:** Query etymology (or stems) by lemma; if found, return stem + confidence.
5. **Connecting vowel:** If remainder contains ա or ե in the middle, try splitting at vowel and lookup both parts (e.g. գրախոս → գիր + ա + խոս → look up գիր, խոս).
6. **Return:** List of stems + list of affixes removed + confidence.

Over-stemming: avoid stripping when the remainder is too short (e.g. min length 2) or when it would create a non-word. Under-stemming: accept that some compounds will not split without a larger stem list or Nayiri integration.

---

## 6. Connecting Sounds: ա and ե (In Depth)

### 6.1 ա as connector

- Between two roots: **stem1 + ա + stem2** is very common (e.g. գիր + ա + խոս → գրախոս). Sometimes the first stem loses a vowel (գիր → գր).
- In some formations ա is part of the second stem (e.g. արքայ “king” → արքա- in արքեա “royal”, where the linking is ե + ա).

Rule for splitting: when the word has an internal ա that is not the first or last letter, try split at ա and check both parts in the stem catalog.

### 6.2 ե as connector

- Often in suffixes: -եա, -ական, -ային. Here ե is part of the suffix.
- Between roots: less common than ա, but e.g. արքայ + ե + ա → արքեա.

Rule: treat -եա as one suffix; for internal ե, try split and lookup (e.g. արքեա → արքայ + -եա).

### 6.3 Data structure for linking

In the stem catalog, for each stem that frequently appears in compounds, store:

- `connecting_vowel`: preferred vowel when this stem is first (e.g. գիր → ա) or second (e.g. խոս after ա).
- Optional: `combining_form`: the form used in compounds (e.g. գիր → գր when followed by ա).

This allows the stemmer to propose candidate splits (e.g. գրախոս → գր + ա + խոս) and validate both parts.

---

## 7. Implementation Checklist

- [x] **Monosyllabic roots:** `data/monosyllabic_roots.json` — 200 one-syllable roots and orthographic alternants (e.g. գիր/գր, սէր/սիր) from *200 Monosyllabic Words* (Fr. Ghevond Ajamian ©2015). Loaded by `linguistics/stemmer.py`; `get_all_lemmas()` adds alternant forms when the word is a known root; `get_root_alternants(word)` returns the alternant set. Tests: `tests/test_stemmer_monosyllabic_roots.py`.
- [ ] Add `data/stem_affixes.yaml` (or JSON) with prefix/suffix list and variants (WA/EA).
- [ ] Implement stemmer module: normalize → strip affixes (longest match) → lookup remainder in etymology/stems.
- [ ] Add connecting-vowel logic: try split at ա/ե, lookup both parts.
- [ ] Extend etymology schema or add stems collection (see §3).
- [ ] Unit tests: known words → expected stem(s) and affixes; avoid over-stemming (e.g. չէ, անուն).
- [ ] Document WA vs EA spelling in affix list (e.g. -ութիւն vs -ություն).

---

## 8. References

- `docs/development/ETYMOLOGY_STEM_TRANSLITERATION_STRATEGIES.md` — Phase 1 etymology schema; stem catalog strategy.
- `docs/development/LOANWORD_TRACKING_ANALYSIS.md` — Loanword detection; future stem/etymology integration.
- `cleaning/armenian_tokenizer.py` — Normalization (NFC, ligature decomposition, lowercase).
- `linguistics/etymology_db.py` — Etymology collection and lookup.
- Nayiri (nayiri.com) — Stem dictionary (Atcharyan); potential source for stem list and validation.
