# Linguistics Directory — Structure Audit

In-depth audit of `linguistics/`: organization, redundancies, modularity, and naming. Refactor options and name suggestions at the end.

**Status: Option B implemented.** Layout is now: `phonology/`, `lexicon/`, `dialect/`, `metrics/` (slimmed), `morphology/` (with difficulty exported, grammar_rules in archive), `tools/` (phonetics_audit, import_etymology_from_wiktextract). Backward-compat: `linguistics.phonetics`, `linguistics.dialect_classifier`, `linguistics.loanword_tracker`, `linguistics.etymology_db` are aliased so existing imports still work.

Dialect review/audit thresholds are now also centralized under `linguistics/dialect/` via `review_audit.py` and `review_heuristics.yaml`, so ingestion-stage review routing pulls its defaults from the linguistics package instead of scattering them across acquisition and enrichment modules.

---

## 1. Current layout

```
linguistics/
├── __init__.py              # Public API (phonetics, fsrs, dialect_classifier, stemmer, loanword_tracker, morphology, transliteration)
├── phonetics.py             # WA letter→IPA, difficulty, is_vowel, pronunciation
├── letter_data.py           # Letter names, ARMENIAN_LETTERS, example words (uses phonetics) — NOT imported elsewhere
├── transliteration.py       # BGN/PCGN to_latin, to_armenian, to_ipa
├── dialect_classifier.py    # Rule-based WA/EA/classical classifier
├── stemmer.py               # Lemmatization (uses morphology + data/monosyllabic_roots.json)
├── loanword_tracker.py      # In-memory loanword lexicons + analyze_* (no etymology_db)
├── etymology_db.py          # Wiktextract→MongoDB etymology schema + import (used by import_etymology CLI)
├── fsrs.py                  # Spaced-repetition scheduler (CardState, FSRSScheduler)
├── phonetics_audit.py       # CLI/audit for EA leakage in phonetics (not in __all__)
├── import_etymology_from_wiktextract.py   # CLI (etymology import)
├── morphology/
│   ├── __init__.py          # core, nouns, verbs, articles, detect, irregular_verbs
│   ├── core.py              # ARM/ARM_UPPER (latin key→Armenian), VOWELS, is_vowel, ends_in_vowel, count_syllables
│   ├── nouns.py
│   ├── verbs.py
│   ├── articles.py
│   ├── detect.py
│   ├── irregular_verbs.py
│   ├── grammar_rules.py    # Large validation module — NOT imported by other linguistics code
│   └── difficulty.py       # Word difficulty scoring — NOT in morphology/__all__; no external imports
└── metrics/
    ├── __init__.py          # validation, vocabulary_filter, variant_pairs_helper, text_metrics only
    ├── validation.py       # Augmentation output validation
    ├── vocabulary_filter.py
    ├── variant_pairs_helper.py
    ├── text_metrics.py     # TextMetricCard, QuantitativeLinguisticsAnalyzer
    ├── corpus_vocabulary_builder.py   # Not in metrics/__all__
    ├── dialect_distance.py # WA/EA corpus distance — not in __all__; used by augmentation/
    ├── dialect_clustering.py          # PCA/DBSCAN — not in __all__
    └── dialect_pair_metrics.py        # Pair orthographic load — not in __all__
```

---

## 2. Redundancies and overlaps

### 2.1 Two “phonetic” / letter layers

| Location | Purpose | Overlap |
|----------|---------|--------|
| **phonetics.py** | Letter→IPA, difficulty, pronunciation (Western Armenian). Single-letter `is_vowel(letter)` (set of 6 vowel letters). | Canonical WA phonetics. |
| **letter_data.py** | Rich per-letter catalog: names, upper/lower, IPA, example words. Imports `ARMENIAN_PHONEMES`, `ARMENIAN_DIGRAPHS` from phonetics. | **Unused**: no other module imports `letter_data`. Duplicates/extends phonetics with names and examples. |
| **morphology/core.py** | Latin-key→Unicode (ARM/ARM_UPPER), `VOWELS` (Unicode chars), `is_vowel(char)` (Unicode), `ends_in_vowel`, `count_syllables`. | Different role (morphology engine). **Name overlap**: `is_vowel` in both phonetics and morphology/core (different signatures: letter vs Unicode char). |

**Recommendation:** Keep phonetics as the single source for “letter → sound” and IPA. Either (a) fold letter_data into phonetics as optional “extended letter info” (names, examples), or (b) move letter_data to a separate package (e.g. `resources` or `card_data`) if it’s only for card generation / future use. Add a one-line comment in morphology/core that `is_vowel` is for word-level morphology, distinct from phonetics’ letter-level use.

### 2.2 Dialect: classifier vs metrics

| Module | Role | Consumers |
|--------|------|------------|
| **dialect_classifier.py** | Rule-based: WA/EA/classical from pattern matches (e.g. իւ, particles). | tests, direct imports. |
| **metrics/dialect_distance.py** | Quantitative corpus distance (lexical + structural). | augmentation (benchmark, calibrate). |
| **metrics/dialect_clustering.py** | PCA + DBSCAN on text + metadata. | Standalone/CLI. |
| **metrics/dialect_pair_metrics.py** | Per-pair orthographic load (letter_delta, etc.). | augmentation, tests. |
| **metrics/variant_pairs_helper.py** | Build WA/EA variant pairs from mapping. | metrics __init__, augmentation. |

No code duplication: classifier is rule-based per text; metrics are corpus-level and pairwise. **Structural issue**: “dialect” is split between top-level (`dialect_classifier`) and `metrics/` (dialect_distance, dialect_clustering, dialect_pair_metrics). That’s consistent if “metrics” = “quantitative analysis,” but the name `metrics` also carries validation, vocabulary, and text_metrics, so the package is doing two jobs: (1) augmentation support (validation, vocabulary_filter, text_metrics, variant_pairs), (2) dialect analytics (distance, clustering, pair_metrics).

### 2.3 Etymology vs loanwords

| Module | Role | Storage |
|--------|------|---------|
| **etymology_db.py** | Wiktextract→etymology docs (lemma, source, confidence, etymology_text). | MongoDB `etymology` collection. |
| **loanword_tracker.py** | Detect loanwords by source language (Russian, Turkish, etc.). | In-memory Python sets (LOANWORD_LEXICONS). |

**No direct link**: loanword_tracker does not use etymology_db. Etymology is for storage and future “dictionary/etymology lookup”; loanword_tracker is for fast per-text counts. Optional future step: allow loanword_tracker to optionally use etymology collection for “possible loanword” or coverage. No refactor required for redundancy; just clarify in docs that they are complementary (storage vs. runtime detection).

### 2.4 Morphology: grammar_rules vs nouns/verbs

- **morphology/nouns.py** and **morphology/verbs.py** define `NounDeclension` and `VerbConjugation` and are used by stemmer and morphology API.
- **morphology/grammar_rules.py** is a large module (noun/verb validation, agreement, cases, tenses) and is **not imported** by any other linguistics code. It references an external test harness path.

So there are two parallel “grammar” implementations: one used (nouns, verbs, articles, detect, irregular_verbs) and one unused (grammar_rules). **Recommendation:** Either integrate grammar_rules into the morphology API (and use it from nouns/verbs or validation) or move it to `docs/` or `archive/` and document it as reference/legacy. Do not leave it as an unused 1k+ line module in the main tree.

### 2.5 morphology/difficulty.py

- Uses morphology/core (ARM, VOWELS, count_syllables, is_armenian).
- **Not** exported from `morphology/__init__.py`.
- **Not** imported elsewhere in the repo.

So difficulty is effectively dead code from the package’s perspective. Either export and use it (e.g. from ingestion or learning tools) or move it to a “learning” or “difficulty” subpackage and document the intended entry point.

### 2.6 FSRS

**fsrs.py** is a generic spaced-repetition scheduler; it has no Armenian-specific logic. It fits “learning support” rather than “linguistics” per se. Optional: move to a top-level `learning/` or `srs/` package if you want linguistics to be strictly language-specific.

---

## 3. Cross-cutting dependencies

- **cleaning**: `armenian_tokenizer` (extract_words, normalize) used by metrics (dialect_distance, text_metrics, corpus_vocabulary_builder, vocabulary_filter), stemmer (indirect), etymology_db (normalize).
- **ingestion._shared.helpers**: `compute_wa_score`, `is_western_armenian`, etc., used by metrics (vocabulary_filter, validation).
- **linguistics** → **linguistics**: stemmer → morphology; letter_data → phonetics; morphology (nouns, verbs, articles, detect, difficulty) → morphology/core and irregular_verbs.

Keeping tokenization and WA scoring in cleaning/ingestion is reasonable; linguistics stays focused on analysis and rules.

---

## 4. Public API vs internal use

- **In linguistics/__init__ __all__:** phonetics, fsrs, dialect_classifier, stemmer, loanword_tracker, morphology, transliteration. **Not** exported: etymology_db, letter_data, phonetics_audit, import_etymology_from_wiktextract (CLI), and the whole **metrics** package (consumers import `linguistics.metrics` or `linguistics.metrics.text_metrics` etc. directly).
- **metrics/__init__**: Exposes validation, vocabulary_filter, variant_pairs_helper, text_metrics. Does **not** expose dialect_distance, dialect_clustering, dialect_pair_metrics, corpus_vocabulary_builder (augmentation and tests import those submodules explicitly).

So the “public” surface is the top-level __init__; metrics is a second surface used mainly by augmentation. Consistency improvement: either add the dialect_* and corpus_vocabulary_builder to metrics/__all__ (and document them) or group them under a clear subnamespace (e.g. `linguistics.metrics.dialect`).

---

## 5. Name: does “linguistics” fit?

The directory mixes:

1. **Core language description**: phonetics, transliteration, morphology (alphabet, IPA, grammar, inflection).
2. **Lexicon / etymology**: etymology_db, loanword_tracker (and import CLI).
3. **Dialect and variation**: dialect_classifier, metrics (dialect distance, clustering, pair metrics, variant pairs).
4. **Analysis and metrics**: text_metrics, vocabulary_filter, validation, corpus_vocabulary_builder.
5. **Utilities**: stemmer (lemmatization), fsrs (SRS).

“Linguistics” is a reasonable umbrella for (1)–(4). (5) is tangential. Alternatives:

- **Keep `linguistics`** — Broad and accurate; no change.
- **`armenian` or `armenian_linguistics`** — Emphasizes language; longer and redundant if the repo is already Armenian-focused.
- **`language`** — Generic; could conflict with “language” in NLP sense.
- **Split names** — If you split (see refactor options), you could have e.g. `linguistics/` for (1), `lexicon/` or `etymology/` for (2), `dialect/` or `metrics/` for (3)–(4). Then the top-level name could stay `linguistics` as the parent for all.

**Recommendation:** Keep **`linguistics`** as the top-level name. If you create subpackages, use subnames (e.g. `linguistics.phonology`, `linguistics.morphology`, `linguistics.metrics`, `linguistics.lexicon`) rather than renaming the root.

---

## 6. Refactor options

### Option A — Minimal (reduce redundancy, no big moves)

- **letter_data**: Either remove if truly unused, or add a single use (e.g. from ingestion or a card tool) and document; or move to `linguistics/resources/letter_data.py` and re-export from linguistics only if needed.
- **phonetics vs morphology is_vowel**: Add a short comment in morphology/core that `is_vowel` is for word-level morphology (Unicode), distinct from phonetics’ letter-level IPA/vowel check.
- **grammar_rules**: Move to `linguistics/morphology/archive/grammar_rules.py` or `docs/archive/` and add a README pointing to it as reference; or wire it into morphology (e.g. validation) and use it.
- **difficulty**: Either export from morphology and use from somewhere (e.g. learning pipeline), or move to `linguistics/learning/difficulty.py` (or archive) and document.
- **metrics/__init__**: Add to __all__: dialect_distance (e.g. DistanceWeights, DistanceReport, dialect_distance), dialect_pair_metrics (e.g. DialectPairRecord, DialectMetricsSummary), corpus_vocabulary_builder (CorpusVocabularyBuilder). Optionally add dialect_clustering (e.g. FeatureRow, run_clustering) if you want it part of the public metrics API.

**Pros:** Low risk, clear ownership. **Cons:** “metrics” still mixes augmentation helpers and dialect analytics.

---

### Option B — Moderate (group by purpose, keep one package)

Keep a single `linguistics/` package but group modules into subpackages:

- **linguistics/phonology/** (or **linguistics/sound/**): phonetics.py, letter_data.py (if kept). Transliteration could stay here or stay top-level (it’s script conversion, not strictly “sound”).
- **linguistics/morphology/** (existing): core, nouns, verbs, articles, detect, irregular_verbs. Move difficulty here and export it; move or archive grammar_rules as in Option A.
- **linguistics/lexicon/** (new): etymology_db.py, loanword_tracker.py. Optional: import_etymology_from_wiktextract.py as a CLI under lexicon or as `linguistics/tools/import_etymology.py`.
- **linguistics/dialect/** (new): dialect_classifier.py + from metrics: dialect_distance.py, dialect_clustering.py, dialect_pair_metrics.py, variant_pairs_helper.py. So “dialect” = rule-based classification + quantitative dialect metrics.
- **linguistics/metrics/** (slimmed): validation.py, vocabulary_filter.py, text_metrics.py, corpus_vocabulary_builder.py. All augmentation-oriented (validation, filtering, text stats, corpus vocab). Keep a single place for “augmentation pipeline” helpers.
- **linguistics/tools/** (optional): phonetics_audit.py, import_etymology_from_wiktextract.py (if not under lexicon).
- **Top-level linguistics:** stemmer.py, transliteration.py, fsrs.py (or move fsrs to learning/). __init__.py re-exports from subpackages.

**Pros:** Clear grouping (sound, morphology, lexicon, dialect, metrics). **Cons:** Many import path changes; need to update augmentation and tests.

---

### Option C — Split “linguistics” from “augmentation support”

- **linguistics/** (language core only): phonetics, letter_data (or merged), transliteration, morphology, dialect_classifier, stemmer, etymology_db, loanword_tracker, fsrs. Optional subpackages: phonology, morphology, lexicon, dialect (classifier only).
- **augmentation/linguistics/** or **augmentation/analysis/** (new): Move from linguistics/metrics: validation, vocabulary_filter, text_metrics, variant_pairs_helper, corpus_vocabulary_builder, dialect_distance, dialect_clustering, dialect_pair_metrics. So all augmentation-specific analysis lives next to the augmentation pipeline.

**Pros:** linguistics is purely “Armenian language” (phonetics, grammar, dialect rules, lexicon); augmentation owns its metrics and dialect analytics. **Cons:** Bigger move; anything that only needs “dialect distance” would import from augmentation.

---

### Option D — Flatten metrics into “dialect” + “analysis”

- **linguistics/dialect/**: dialect_classifier.py, dialect_distance.py, dialect_clustering.py, dialect_pair_metrics.py, variant_pairs_helper.py. Single place for “WA/EA and variants.”
- **linguistics/analysis/** (or keep **metrics**): validation.py, vocabulary_filter.py, text_metrics.py, corpus_vocabulary_builder.py. Name “analysis” or “metrics” to taste; “metrics” is already used by augmentation.
- Leave phonetics, transliteration, morphology, stemmer, loanword_tracker, etymology_db, fsrs at top level or under minimal subpackages (e.g. phonology, lexicon) as in Option B.

**Pros:** Clear “dialect” vs “general analysis” split without moving code out of linguistics. **Cons:** Still two subpackages to maintain; import paths change.

---

## 7. Summary table

| Issue | Minimal (A) | Moderate (B) | Split (C) | Flatten (D) |
|-------|-------------|-------------|-----------|-------------|
| letter_data | Document or move to resources | Under phonology/ | Same | Same |
| is_vowel duplicate | Comment only | Comment only | Comment only | Comment only |
| grammar_rules | Archive or integrate | Archive or integrate | Same | Same |
| difficulty | Export or archive | Under morphology, export | Same | Same |
| metrics vs dialect | __all__ + docs | New dialect/ subpackage | Move dialect+metrics to augmentation | New dialect/ + keep metrics/ |
| etymology vs loanword | Docs only | lexicon/ subpackage | Same | Same |
| FSRS | Leave | Leave or learning/ | Leave | Leave |
| Directory name | Keep `linguistics` | Keep `linguistics` | Keep `linguistics` | Keep `linguistics` |

---

## 8. Recommended path

- **Short term (Option A):** Clean up unused or duplicate surface: letter_data (use or document/relocate), grammar_rules (archive or integrate), difficulty (export and use or archive), and metrics __all__. Add the morphology/core vs phonetics comment for `is_vowel`. Keeps modularity and reduces confusion.
- **Medium term (Option B or D):** If you want clearer structure without moving code out of linguistics, introduce **linguistics/dialect/** for all dialect-related modules (classifier + distance, clustering, pair_metrics, variant_pairs) and keep **linguistics/metrics/** for augmentation-only helpers (validation, vocabulary_filter, text_metrics, corpus_vocabulary_builder). Option B adds more subpackages (phonology, lexicon, tools); Option D only adds dialect/ and optionally renames metrics to analysis.
- **Name:** Keep **`linguistics`**; use subpackage names (e.g. **dialect**, **metrics**, **lexicon**, **phonology**) to reflect purpose.

If you tell me which option you prefer (A, B, C, or D), I can outline concrete file moves and import updates step by step.
