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
- Dialect classifier treats `մը` as a Western signal (`WA_INDEF_ARTICLE_MEH`).

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
