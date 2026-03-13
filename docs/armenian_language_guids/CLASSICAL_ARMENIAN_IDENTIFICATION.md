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

- **Location:** `linguistics/dialect_classifier.py`.
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
