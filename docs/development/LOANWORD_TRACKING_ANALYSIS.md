# Loanword Tracking: In-Depth Analysis

**Purpose:** Document how loanword detection is implemented, what is and isn’t supported, and planned improvements.

---

## 1. Current Implementation Overview

### 1.1 Detection Method: Static Lexicon Lookup

**How we detect loanwords:** By direct string matching against an in-memory lexicon of known loanwords.

We do **not**:

- Use dictionary lookups (Wiktionary, Nayiri, etc.)
- Transliterate Armenian to English/Cyrillic/Arabic/etc. for cross-language checks
- Use morphological analysis, etymological databases, or NLP models
- Infer loanwords from orthography or phonotactics alone

**How we know it’s a loanword:** Because the word appears in our curated lexicon. Words are classified by source language (Russian, Turkish, Arabic, French, Spanish, Farsi) based on linguistic literature and Wiktionary-derived lists. Lexicon membership is our only criterion.

### 1.2 Lexicon Structure

| Source Language | Scope | Example Entries |
|----------------|-------|-----------------|
| **russian**    | EA (Armenia, former USSR) | ապարատ, ավտոբուս, տուրիստ, լիմոնադ |
| **turkish**    | WA (Ottoman diaspora)    | բալիկ, չախմախ, կրպակ, պասպորտ |
| **arabic**     | WA (Lebanon, Syria, Iraq) | քաթիպ, սուլթան, քաֆէ |
| **french**     | WA (Lebanon, France)     | բուֆէ, պարֆեմ, սալոն, տակսի |
| **spanish**    | WA (Argentina diaspora)  | տանգո, պասիո, ֆիեստա |
| **farsi**      | EA (Iran)                | բաղչա, շահ, կաբաբ |

Lexicons live in `linguistics/loanword_tracker.py` as Python `set`s. Each word is stored in Armenian script (lowercase, NFC-normalized). Normalization (ligature decomposition, lowercase) follows `cleaning.armenian_tokenizer`.

### 1.3 Processing Pipeline

1. **Tokenization:** `extract_words(text)` from `cleaning.armenian_tokenizer` (or a fallback regex if that module is unavailable)
2. **Lookup:** Each token is checked against `_WORD_TO_LANGUAGE`, a prebuilt map from word → source language
3. **Aggregation:** Per-text counts by language, unique loanword list, and ratio

Output (`LoanwordReport`):

```python
{
  "total_words": 150,
  "total_loanwords": 12,
  "loanword_ratio": 0.08,
  "counts_by_language": {"russian": 5, "turkish": 4, "french": 3},
  "unique_loanwords": ["ապարատ", "ավտոբուս", ...],
  "loanwords_by_language": {"russian": ["ապարատ", ...], ...}
}
```

---

## 2. What Is Not Implemented

### 2.1 Dictionary-Based Verification

There is now a **placeholder pipeline** for dictionary-based verification:

- `PossibleLoanwordReport` in `linguistics.loanword_tracker`
- `analyze_possible_loanwords(text, text_id, source, is_known_word=None)`
- Ingestion integration via `metadata.document_metrics.possible_loanwords`

By default, the internal `_default_is_known_armenian_word()` treats **all tokens as known**, so no words are currently flagged as possible loanwords. To make this useful, wire `is_known_word` to:

- A Nayiri-backed lookup (Western Armenian dictionary)
- A local Armenian lexicon compiled from corpora

Still **not implemented**:

- Direct online lookups into Wiktionary or Nayiri
- Per-language dictionary backends (Russian, Turkish, Arabic, etc.)

Approximate transliteration (WA vs EA) is **not** yet used for dictionary checks. Transliteration modules for that purpose do not exist.

### 2.2 Transliteration Functions

| Function | Purpose | Status |
|----------|---------|--------|
| Armenian → English (WA) | Dictionary lookup, romanization | **Not implemented** |
| Armenian → English (EA) | Dictionary lookup, romanization | **Not implemented** |
| Eastern Armenian → Cyrillic | Russian dictionary lookup | **Not implemented** |
| Western Armenian → Arabic | Arabic dictionary lookup | **Not implemented** |
| Western Armenian → French | French dictionary lookup | **Not implemented** |
| Western/Eastern → Turkish | Turkish dictionary lookup | **Not implemented** |
| Eastern Armenian → Farsi/Persian | Farsi dictionary lookup | **Not implemented** |

The `.cursor/rules/western-armenian-transliteration.mdc` and similar docs define transliteration conventions for human use but do **not** provide programmatic functions.

### 2.3 Updatable Catalog / Learning from Data

The lexicon is **not**:

- Loaded from a JSON/TSV/YAML file
- Updated when classifiers process new text
- Derived from a database or external API

The current design is static: new entries are added manually via `add_loanwords(language, words)` or by editing the source. There is no pipeline that:

- Suggests candidate loanwords from unseen tokens
- Validates them against dictionaries
- Adds them to a persisted catalog

---

## 3. Ingestion Integration

When `database.compute_metrics_on_ingest` or `scraping.compute_metrics_on_ingest` is `true`, ingestion calls `_compute_document_metrics()` in `scraping/_helpers.py`. That function now:

1. Computes the quantitative linguistics TextMetricCard
2. Runs `analyze_loanwords(text, text_id, source)` → `loanwords`
3. Runs `analyze_possible_loanwords(text, text_id, source)` → `possible_loanwords`
4. Stores the full object in `metadata.document_metrics`

**Storage schema (logical):**

```
metadata.document_metrics = {
  "text_id": "...",
  "source": "...",
  "text_length": N,
  "lexical": { ... },
  "syntactic": { ... },
  ...
  "loanwords": {
    "total_words": N,
    "total_loanwords": M,
    "loanword_ratio": r,
    "counts_by_language": {"russian": k1, "turkish": k2, ...},
    "unique_loanwords": ["...", ...],
    "loanwords_by_language": {"russian": [...], ...}
  },
  "possible_loanwords": {
    "total_words": N,
    "total_possible_loanwords": U,
    "possible_loanword_ratio": u,
    "possible_loanword_counts": {"token1": c1, "token2": c2, ...},
    "unique_possible_loanwords": ["token1", "token2", ...]
  }
}
```

**Config:** Loanword and possible-loanword tracking run whenever document metrics are computed. There is no separate `compute_loanwords_on_ingest` flag. Scrapers must pass `config` to `insert_or_skip` for this to run (e.g. `ocr_ingest` does; some others may not).

---

## 4. Extending the Lexicon

### 4.1 Programmatic Extension

```python
from linguistics.loanword_tracker import add_loanwords

add_loanwords("russian", ["նորակառույց", "ակնարկ"])
add_loanwords("turkish", ["թամամ"])
```

This mutates the in-memory lexicons; changes are lost on restart unless the code is updated.

### 4.2 Future: File-Based Catalog

A possible design for an updatable catalog:

- **File:** `data/loanwords/loanwords.json` or similar
- **Format:** `{"russian": [" word1", "word2", ...], "turkish": [...], ...}`
- **Load on startup:** Replace or merge with in-memory sets
- **Add candidates:** Human review → append to file → reload
- **Version control:** Track changes in git for auditability

---

## 5. Future Improvements (Planned)

### 5.1 Etymological Origin Tracking

- For each Armenian word: record etymology (one or many hypotheses, with weights)
- Integrate sources: Wiktionary etymology sections, Nayiri, academic references
- Allow queries like: “Words of Iranian origin” or “Disputed: Greek vs Latin”

### 5.2 Stem and Root Catalog

- Catalog of stem/bound roots (prefixes, suffixes, roots)
- For compound words: list of root words involved
- Examples: `ան-` (negation), `-ութիւն` (abstract noun), etc.
- Support for querying: “Words containing root X”

### 5.3 English Transliteration → Western Armenian Spelling

- Input: Romanized Armenian (e.g. “Barev”, “dzez”)
- Output: Western Armenian orthography (e.g. “Պարեւ”, “ձեզ”)
- Use case: Converting romanized input into classical spelling

### 5.4 Armenian → IPA

| Function | Input | Output |
|----------|-------|--------|
| `western_armenian_to_ipa(text)` | WA text (classical spelling) | IPA string |
| `eastern_armenian_to_ipa(text)` | EA text (reform or traditional) | IPA string |

These would encode dialect-specific phonetics (WA vs EA differences).

---

## 6. Transliteration Functions (Future)

Intended interfaces (not yet implemented):

```python
# For dictionary lookups (future)
def transliterate_to_english_western(armenian: str) -> str: ...
def transliterate_to_english_eastern(armenian: str) -> str: ...
def transliterate_eastern_to_cyrillic(armenian: str) -> str: ...
def transliterate_western_to_arabic(armenian: str) -> str: ...
def transliterate_western_to_french(armenian: str) -> str: ...
def transliterate_armenian_to_turkish(armenian: str, dialect: Literal["western","eastern"]) -> str: ...
def transliterate_eastern_to_farsi(armenian: str) -> str: ...
```

These would allow checking Armenian tokens in Russian, Arabic, French, Turkish, and Farsi dictionaries by transliteration.

---

## 7. Summary

| Aspect | Current State |
|--------|---------------|
| **Detection** | Static lexicon lookup only |
| **Dictionary lookup** | Not used |
| **Transliteration** | Not implemented for dictionary checks |
| **Catalog** | In-code sets; not file-based or auto-updated |
| **Ingestion** | Loanwords stored in `metadata.document_metrics.loanwords` when metrics are computed |
| **Extensibility** | `add_loanwords()` for runtime; manual edits for persistence |

The system is suitable for tagging and counting known loanwords by source language. Improving recall and reliability will require dictionary-based verification and transliteration support.
