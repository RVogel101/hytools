# Etymology DB, Stem Catalog, and Transliteration Pipelines — Implementation Strategies

This document summarizes **implementation strategies** for three related capabilities: an **etymology database**, a **stem catalog**, and **transliteration pipelines**. It is intended for review and planning; see also `docs/FUTURE_IMPROVEMENTS.md` for the high-level roadmap and loanword/etymology extensions.

---

## 1. Etymology database

**Goal:** Track etymological origin per Armenian word (and support multiple theories with credibility weights). Used for loanword tracking, dictionary lookups, and corpus analysis.

### Strategy comparison

| Approach | Pros | Cons |
|----------|------|------|
| **Wiktionary / Wiktextract** | Structured dumps (JSONL) with etymology, glosses, relations; kaikki.org and etymology-db (3.8M entries, 31 relationship types); no API key. | Armenian coverage is partial; need to filter by language and map to WA/EA; pipeline to import and index. |
| **Nayiri** | Armenian-focused; stem dictionary (Atcharyan); Developers section for API. | API terms and rate limits unclear; may require partnership or bulk export. |
| **Custom curation** | Full control; credibility weights per theory. | High effort; needs linguist input; maintenance. |

### Recommended approach

- **Phase 1:** Import Armenian entries from Wiktextract/kaikki into a small **etymology** or **loanword_origin** collection (or extend existing loanword catalog). Schema: lemma → source (wiktionary | nayiri | manual), confidence, optional etymology text and relationship types.
- **Phase 2:** Add Nayiri headword list (already used for `in_nayiri` in frequency aggregator) as a second source; link to existing `loanword_tracker` and document_metrics loanword fields.
- **Phase 3:** If Nayiri API becomes available, add live lookup or periodic bulk sync.

### Data sources

- **Wiktionary / Wiktextract:** https://kaikki.org/dictionary/Armenian/ ; https://github.com/tatuylonen/wiktextract  
- **Nayiri:** https://www.nayiri.com/ (dictionary, stemmer, Developers section)

### Schema (indicative)

```python
# MongoDB collection: etymology (or loanword_origin)
{
    "lemma": str,           # normalized headword
    "source": "wiktionary" | "nayiri" | "manual",
    "confidence": float,
    "etymology_text": str | None,
    "relationships": list,  # e.g. ["borrowed_from_turkish"]
    "updated_at": datetime,
}
```

---

## 2. Stem catalog

**Goal:** Build a catalog of stem/root forms; support lookup from inflected forms and compound-word analysis (e.g. prefix ան-, suffix -ութիւն).

### Strategy comparison

| Approach | Pros | Cons |
|----------|------|------|
| **Nayiri stemmer** | Returns canonical form from inflected form (e.g. կատուներուս → կատու); Atcharyan stem dictionary. | May be EA-biased; API/export needed for integration. |
| **Rule-based suffix stripping** | No external dependency; repeatable. | WA/EA/Classical differ; overstemming/understemming; needs rule maintenance. |
| **ML stemmer** | Can learn WA-specific patterns from corpus. | Requires labeled data and training. |

### Recommended approach

- **Lookup:** Use Nayiri for stem lookup when available (same as etymology phase).
- **Rule-based fallback:** Maintain a **minimal rule-based stem list** for frequent affixes (e.g. -ութիւն, -ութիւն, ան-, դժ-) and compound markers. Store stems in the same schema as etymology (lemma → stem, source).
- **Pipeline:** Stemmer that (1) strips known suffixes from the word, (2) looks up remainder in Nayiri or etymology collection, (3) returns stem + confidence.

### Affix list (indicative, for rule-based pass)

- Prefixes: ան-, դժ-, դձ-, չ-, բարի-, ամենա-
- Suffixes: -ութիւն, -ություն, -ութիւն, -ստան, -արան, -ացնել, -անալ

(Exact Unicode and WA/EA variants to be curated.)

### Schema

Reuse or extend etymology collection with fields: `stem`, `affix_removed`, `source` (nayiri | rule_based).

---

## 3. Transliteration pipelines

**Goal:** Support dictionary lookup and search across scripts: Armenian ↔ Latin (romanization), Armenian → IPA, and (optionally) romanized input → Armenian.

### Strategy comparison

| Direction | Standard / source | Pros | Cons |
|-----------|-------------------|------|------|
| **Armenian → Latin** | ISO 9985:1996 / 2026 | Single standard; bibliographic use; many tools. | Multiple systems exist (Hübschmann-Meillet, BGN/PCGN, ALA-LC); WA vs EA spelling differences affect mapping. |
| **Armenian → IPA** | Linguistic convention | Unambiguous pronunciation; WA vs EA different realizations. | Need separate WA/EA/Classical tables; combining characters. |
| **Latin → Armenian** | Reverse mapping + heuristics | Enables search and input. | Ambiguous (e.g. e → ե vs Է); context or dictionary needed. |
| **Armenian → Cyrillic (EA)** | Russian/Soviet convention | Russian dictionary lookup. | EA-specific; not for WA. |

### Recommended approach

- **First pipeline:** **Armenian (script) → ISO 9985 Latin** for dictionary keys and search. Implement as a single table (Armenian grapheme → Latin) and a small module; optional caching in MongoDB by word.
- **Second:** **Armenian → IPA** for WA and EA as separate modules (different phonetic realizations).
- **Third:** **Romanized → Armenian** with disambiguation (dictionary-first, then rules).

Store transliteration tables as **data files** (JSON/CSV) in the repo; keep code in a small `transliteration` or `linguistics/transliteration` module.

### Implementation notes

- **ISO 9985:** Map each Armenian letter (and common digraphs) to Latin; handle punctuation and spaces. One function: `armenian_to_latin(text: str, variant: "wa" | "ea") -> str`.
- **IPA:** Two tables (WA and EA) for vowel/consonant realization; function `armenian_to_ipa(text: str, variant: "wa" | "ea") -> str`.
- **Romanized → Armenian:** Reverse map + frequency or dictionary for disambiguation (e.g. e → ե vs Է).

---

## 4. Implementation timeline (indicative)

| Phase | Scope | Duration |
|-------|--------|----------|
| **Etymology** | Import Armenian entries from Wiktextract/kaikki; schema and index; link to loanword_tracker | 2–4 weeks |
| **Stem catalog** | Curate ~50–100 affixes; stemmer (strip + lookup); store in same schema as etymology | 2–3 weeks |
| **Transliteration** | ISO 9985 Armenian→Latin table + function; optional IPA (WA/EA) | 1–2 weeks |
| **Romanized → Armenian** | Reverse map + disambiguation (dictionary, then rules) | 2–4 weeks |

---

## 5. Dependencies and integration

- **Existing code:** `linguistics/loanword_tracker.py`, `metadata.document_metrics.loanwords`, Nayiri headword set in `scraping/frequency_aggregator.py`, `scraping/nayiri.py`.
- **Config:** Optional `etymology.mongodb_collection`, `transliteration.table_path`, etc. in `config/settings.yaml`.
- **Tests:** Unit tests for transliteration (round-trip where unambiguous), stemmer (known word → stem), and etymology lookup (mock or small fixture).

This document should be updated as strategies are implemented or revised.
