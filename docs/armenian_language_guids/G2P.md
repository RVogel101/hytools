# Grapheme-to-Phoneme (G2P) Guide — Armenian (focus: Western Armenian)

This document explains what a Grapheme-to-Phoneme (G2P) system does, why it's important, and how to design and evaluate one for Armenian — with a focus on Western Armenian (WA) issues such as digraphs, classical orthography, and reversed voicing.

## 1. What is G2P?

- Definition: G2P is the process of converting written text (graphemes) into a sequence of phonemes or phones (pronunciation). The output is typically expressed in IPA, ARPAbet, or another phonetic alphabet.
- Purpose: supply pronunciations for TTS, ASR, forced alignment, pronunciation lexica, phonetic search, and linguistic analysis.

## 2. Why G2P matters

- TTS needs reliable pronunciations for natural-sounding synthesis.
- ASR and forced-alignment use expected phone sequences to improve decoding and to align audio with text.
- Linguistic tooling (phonology research, phonetic search, deduplication) depends on phonetic representations.
- OOV handling: G2P provides plausible pronunciations for names and neologisms.

## 3. Core components of a G2P system

1. Normalization
   - Unicode normalization (NFC), case folding, punctuation handling, canonical mapping of orthographic variants.
2. Segmentation / tokenization
   - Word-level tokenization, then grapheme segmentation inside words.
   - Use longest-match segmentation to prefer digraphs/trigraphs (e.g., `իւ`, `եա`, `ու`) over single letters.
3. Grapheme→phone mapping
   - A base table mapping graphemes or grapheme clusters to phones.
4. Contextual / phonological rules
   - Position-sensitive rules (word-initial vs medial), assimilation, voicing alternations, vowel reduction, stress placement.
5. Disambiguation / sequence modeling
   - Decision procedures (ordered rules, decision trees, FSTs) or learned sequence models (joint-sequence models, seq2seq Transformers) to pick between competing mappings.
6. Post-processing
   - Sandhi/liaison across token boundaries, syllabification, stress marking, output normalization and formatting.
7. Output formatting & integration
   - Provide canonical phone sequences, optional alternate pronunciations, and export to chosen phonetic alphabets.

## 4. Approaches

- Rule-based / finite-state
  - Pros: transparent, linguistically interpretable, works with small resources.
  - Cons: requires manual rule engineering; brittle for many exceptions.
- Data-driven / neural
  - Pros: handles irregularities automatically given training data; scales with data.
  - Cons: requires a good aligned lexicon, can hallucinate or overfit, less interpretable.
- Hybrid
  - Rule-based preprocessing/postprocessing combined with a learned core is often the most practical for low-resource/dialectal cases.

## 5. Western Armenian (WA) specific concerns

- Digraphs and classical orthography
  - `իւ`, `եա`, `ու` and other multigraphs must be matched first (longest-match) to avoid mis-segmentation.
  - Example: `իւ` often represents a rounded high front vowel `/ʏ/` in WA (classical behavior).
- Contextual behavior of `ո` and `ե`
  - `ո`: word-initial often realized `/ʋɔ/` or `/vo/` in WA, medial `/ɔ/` (or part of `ու` sequences).
  - `ե`: word-initial realized with palatal onset `/jɛ/`, medial `/ɛ/`.
- Reversed voicing (dialectal mapping)
  - WA has reversed voicing pairs relative to Eastern Armenian (EA). For example, letters that map to voiced consonants in EA may map to voiceless counterparts in WA and vice versa. This must be encoded per-dialect in the base mapping table.
- Assimilation and allophony
  - Voicing assimilation across morpheme and word boundaries, regressive or progressive assimilation, and vowel reduction occur and may be applied as a second-pass phonological process.
- Orthographic variants and normalization
  - Classical spellings, ligatures, or archaic sequences may appear in corpora. Decide whether to normalize to reformed orthography or explicitly handle classical sequences.

## 6. Practical pipeline (recommended)

1. Input normalization
   - Unicode NFC, lowercasing (if appropriate), strip/normalize punctuation, map orthographic variants.
2. Word tokenization
3. Grapheme segmentation
   - Use a longest-match algorithm driven by a digraph/trigraph table.
4. Base mapping
   - Map segments using a dialect-aware `grapheme -> phone` table.
5. Apply contextual rules
   - Word-initial `ո/ե`, `իւ/եա`, palatalization, reversed-voicing, aspiration.
6. Phonological post-processing
   - Assimilation, liaison, vowel reduction, syllabification, stress assignment.
7. Output
   - Export IPA (recommended) or other target encodings; provide alternates and confidence if available.

## 7. Evaluation and testing

- Gold lexicon comparison
  - Measure phone error rate (PER), word-level accuracy, and Levenshtein distance against a curated lexicon.
- Unit tests per-rule
  - Tests that cover digraphs, initial/medial alternations, voicing reversals and edge cases.
- Error analysis
  - Track and log frequent substitutions, unknown graphemes, and alignment mismatches.
- Human perceptual checks (TTS)
  - Synthesize sample outputs and perform listening tests for perceived correctness.

## 8. Common pitfalls

- Missing Unicode normalization leads to mismatches.
- Failing to use longest-match segmentation results in wrong tokenization of digraphs.
- Hard-coding mappings without dialect flags overwrites dialectal phonologies.
- Relying solely on neural models with limited training lexica can produce hallucinated pronunciations.
- Omitting post-token assimilation produces unnatural word-boundary pronunciations.

## 9. Example mappings & rules (illustrative)

> Note: the table below is a minimal illustrative snippet — do not treat it as a complete lexicon.

| Grapheme / cluster | WA phone (IPA) | Notes |
|---|---:|---|
| յ / `յ` | j | palatal approximant |
|-ը | ə | schwa-like |
| ո (initial) | ʋɔ | word-initial realization |
| ո (medial) | ɔ | medial realization |
| ե (initial) | jɛ | palatal onset at word start |
| ե (medial) | ɛ | mid-front vowel |
| իւ / `իւ` | ʏ | classical rounded front vowel (digraph) |
| եա / `եա` | ja | diphthong/digraph |
| բ | p | WA reversed-voicing mapping example |
| պ | b | WA reversed-voicing mapping example |

## 10. Integration recommendations for `hytools`

- Start with a deterministic, well-documented rule-based core for WA:
  - Implement a longest-match grapheme tokenizer (digraphs first).
  - Build a dialect-aware base mapping table (separate `wa` and `ea` sets).
  - Implement position-sensitive rules for `ո` and `ե` and for classical digraphs.
- Logging & iterability
  - Log unknown graphemes and fallback cases to build a curated lexicon.
- API
  - Expose a concise API: `g2p(word, dialect='wa', output='ipa') -> List[str]` and `g2p_batch(words, ...)`.
- Testing
  - Add a curated lexicon and unit tests that exercise the audit cases in `docs/armenian_language_guids/phonetics_rule_gaps.md`.
- Hybrid path
  - After a stable rule-based core exists, consider training a small seq2seq model that runs after rule-based preprocessing, with rule-based postprocessing to enforce unavoidable constraints.

## 11. Suggested unit tests

- Digraph coverage: `իւ`, `եա`, `ու`, `եւ`.
- Position-sensitive: `վեն`, `ոն`, `եվրո`.
- Reversed voicing: minimal pairs for `բ/պ`, `դ/տ`, `գ/կ`.
- Boundary assimilation: pairs where voicing changes across token boundaries.

## 12. Next steps (practical)

1. Create a canonical `g2p` module in `hytools/linguistics` with:
   - Normalization, tokenizer, base mapping, contextual rule engine, post-processing.
2. Populate a small gold lexicon (200–1,000 words) covering core WA patterns.
3. Add automated tests as described above.
4. Iterate: collect errors from running G2P on real corpora and refine mappings and rules.

---

If you want, I can now:

- Implement the initial rule-based `g2p` module in `hytools/linguistics/phonetics.py` with unit tests, or
- Create a smaller reference lexicon file and test-suite skeleton under `tests/test_g2p.py`.

Choose one and I'll proceed.
