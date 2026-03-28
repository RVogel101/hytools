# Textbook of Modern Western Armenian — Grammar Summary & Test Baseline

**Source:** `c:\Users\litni\OneDrive\Documents\anki\books\textbook-of-modern-western-armenian.pdf` (327 pages).

**Status:** The PDF does not yield extractable text (likely scanned images). This document summarizes (1) how to use the textbook once text is available, (2) grammar logic already implemented in the codebase as the baseline for comparison, and (3) a checklist of topics to align with the textbook.

---

## 1. Extracting Content from the Textbook (Option A — OCR)

**Chosen method:** Run OCR on the PDF and save a single plain-text file in the repo.

### 1.1 Run OCR

From the repo root, activate the wa-llm conda env (Tesseract with Armenian is installed there), then run:

```bash
conda activate wa-llm
python -m ocr.textbook_modern_wa "c:\Users\litni\OneDrive\Documents\anki\books\textbook-of-modern-western-armenian.pdf"
```

Or in one line: `conda run -n wa-llm python -m ocr.textbook_modern_wa "path\to\textbook.pdf"`.

The script uses Tesseract with **hye+eng** so both Armenian and English text are captured (explanations, glosses, examples). It uses **PSM 6** (uniform block) and **confidence_threshold=50** to reduce missed words; see **docs/development/ARMENIAN_OCR_GPU_AND_QUALITY.md** if you need to tweak DPI, binarization, or PSM further.

Or copy the PDF to `data/raw/textbook-of-modern-western-armenian.pdf` and run:

```bash
python -m ocr.textbook_modern_wa
```

**Requirements:** Tesseract with Armenian (`hye`) data, `pytesseract`, `pdf2image`. The script uses the existing `ocr.pipeline` (Armenian language, adaptive DPI).

**Output:**

- `data/textbook_modern_wa_pages/` — one `.txt` per page
- `data/textbook_modern_wa_extract.txt` — single concatenated file (Armenian + English). Use this as context for summarization, grammar documentation updates, and coding logic (dialect classifier, transliteration, morphology).

### 1.2 After extraction — do the following

1. **Summarize all grammar rules** in this doc and in `docs/armenian_language_guids/` (e.g. add `TEXTBOOK_GRAMMAR_RULES.md` or expand this file with chapter-by-chapter grammar from the extract).
2. **Use every example sentence** from the book as a test case:
   - **Dialect classifier:** Add each example to `tests/data/textbook_modern_wa_vocab_and_sentences.json` under `sentences_western`; run `pytest tests/test_textbook_wa_dialect.py -v`.
   - **Transliteration/grammar:** Add tests in `tests/test_transliteration.py` or a dedicated test module that runs `to_latin`, `to_ipa`, and grammar checks on each textbook example.
3. **Add the book’s vocabulary** to the testing logic and dialect classifier baseline: append words to `vocabulary` in `textbook_modern_wa_vocab_and_sentences.json`; extend dialect classifier rules if the textbook introduces new WA/EA markers.

### 1.3 Other options

- **Option B — Manual:** Copy-paste chapters into `data/textbook_modern_wa/` (e.g. `ch01_grammar.txt`).
- **Option C — Structured data:** As you extract, add vocabulary and example sentences directly to `tests/data/textbook_modern_wa_vocab_and_sentences.json`.

### 1.4 OCR and GPU

**Current setup is CPU-only.** The pipeline uses Tesseract (via `pytesseract`), which does **not** officially support GPU. The Tesseract project has declined to add CUDA/GPU support; they rely on multi-core CPU and have improved speed via CPU vectorization. So `ocr.textbook_modern_wa` and `ocr.pipeline` run entirely on CPU.

**If you want GPU-accelerated OCR** you would need a different engine and pipeline, for example:

- **PaddleOCR** or **EasyOCR** — support GPU (e.g. CUDA) and can be faster on large batches; you would need to verify Armenian (and hye+eng) support and integrate a new pipeline.
- **Kraken** — has CUDA support (mainly for training); less common for production OCR.

For the textbook (327 pages), running with Tesseract on a multi-core CPU is typically sufficient; GPU would require replacing the OCR backend and revalidating Armenian quality. See **docs/development/ARMENIAN_OCR_GPU_AND_QUALITY.md** for Armenian support in PaddleOCR/EasyOCR and for OCR quality tuning (PSM, DPI, confidence, binarization).

---

## 2. Grammar Logic Already in the Codebase (Baseline)

These are the Western Armenian grammar rules currently implemented; use them as the base when comparing with the textbook and when finding issues.

### 2.1 Dialect classifier (`linguistics/dialect_classifier.py`)

- **Western markers:** Classical orthography **իւ**; postposed indefinite **մը** / **մըն**; present particle **կը**; future **պիտի**; negative **չը**; vocabulary **հավկիթ** (egg).
- **Eastern markers:** Reformed **յուղ**, **գյուղ**, **ճյուղ**, **զամբյուղ**, **ուրաքանչյուր**; preposed **մի**; **ձու** (egg); Latin cues **petik**, **jayur**.
- **Classical:** Definite accusative **զ-**; liturgical phrase **Տէր ողորմյա**; archaic **-եալ**.

### 2.2 Morphology & grammar (`linguistics/morphology/`, `linguistics/morphology/grammar_rules.py`)

- **Definite article:** Consonant → **-ը**; vowel → **-ն**; **ու** diphthong → **-ն**; silent **յ** → drop յ + **-ն**; non-silent **յ** (e.g. հայ, բայ) → **-ը**; **ւ** as v → **-ը**.
- **Indefinite article:** **մը** after noun; **մըն** before verb forms (եմ, է, etc.) and **ալ**.
- **Plural:** One-syllable → **-եր**; multi-syllable → **-ներ**; silent **յ** dropped before **-ներ**.
- **Cases:** Nominative, accusative, genitive, dative, ablative, instrumental (with exemplars: տուն, մարդ, աչք, գրիչ, դաշտ).
- **Verb classes:** Class I (**-ել**, thematic **-ե-**), Class II (**-ալ**, **-ա-**), Class III (**-իլ**, **-ի-**); irregulars in `irregular_verbs.py`.
- **Tenses:** Present, imperfect, aorist, subjunctive, conditional, perfect.
- **Ըլլալ (to be):** Present (եմ, ես, է, ենք, էք, են), imperfect (էի, …), past definite (եղայ, …); negatives with **չ**.

### 2.3 WA vs EA distinctions (`docs/armenian_language_guids/WA_EA_LINGUISTIC_DISTINCTIONS.md`)

- Indefinite: WA **noun + մը/մըն**, EA **մի + noun**.
- Present: WA **կը/կ՚ + verb**, EA verb-**ում** + auxiliary.
- Future: WA **պիտի**.
- Vocabulary: egg WA **հաւկիթ**, EA **ձու**; verb “to speak” WA **խօսիլ**, EA **խոսել**.
- Orthography: WA classical **իւ**, **ու**; EA reformed **յու**, **գյ** etc.

### 2.4 Transliteration & phonetics

- **linguistics/transliteration.py:** BGN/PCGN-style; Western voicing reversal; **ու** → ou, **ը** → u; **ոյ** when not word-final or in a 3-letter word → **uy** (e.g. յոյս → huys); word-final **ոյ** in longer words → **o** (յ silent); unwritten schwa before word-initial **ս+կ/պ/տ/ք** and between consonants; **և** only for “and”, **եւ** in words; **-եան** → ian.
- **docs/armenian_language_guids/WESTERN_ARMENIAN_PHONETICS_GUIDE.md**, **ARMENIAN_QUICK_REFERENCE.md**: Voicing, affricates, context-dependent letters, diphthongs.

---

## 3. Textbook Grammar Checklist (To Align)

When the textbook text is available, verify and extend the codebase for:

- **Alphabet & pronunciation** — Match phonetics/transliteration and any textbook-specific romanization.
- **Nouns** — Gender (none in WA), number, case (all six + instrumental); definite/indefinite article rules; plural formation and exceptions.
- **Adjectives** — Position, agreement (if any), comparison.
- **Pronouns** — Personal (ես, դու, ան/նա, մենք, դուք, անոնք); demonstrative; possessive; reflexive.
- **Verbs** — Conjugation classes; present, imperfect, aorist, future, perfect; negative (չ); particle **կը** / **կ՚**; **պիտի**; imperative; participles; infinitives (**-ել**, **-ալ**, **-իլ**).
- **Particles & word order** — **կը**, **պիտի**, **չը**; sentence word order; questions.
- **Adverbs & prepositions** — Common adverbs; case government of prepositions.
- **Conjunctions & subordination** — **եւ**, **բայց**, **որ**, etc.
- **Orthography** — Classical vs reformed; **իւ** vs **յու**; **է** vs **ե**; textbook conventions.
- **Vocabulary** — Dialect-specific words (WA vs EA) and any textbook glossary.

---

## 4. Example Sentences & Vocabulary (Current Baseline)

Example sentences and vocabulary already used in tests (from `TEST_VALIDATION_ARMENIAN.md` and dialect classifier) are in `tests/data/textbook_modern_wa_vocab_and_sentences.json`. Once textbook content is extracted, add its examples there so that:

- **Dialect classifier:** All textbook WA sentences are used as standard “should be classified as Western” tests.
- **Transliteration:** Textbook examples can be used for Armenian ↔ Latin and IPA round-trips.
- **Grammar:** Textbook examples can drive validation (articles, conjugation, word order) against `grammar_rules.py` and morphology.

### 4.1 Dialect classifier tests (`tests/test_textbook_wa_dialect.py`)

- **Not wrong dialect:** Western examples must not be classified as `likely_eastern`; Eastern examples must not be classified as `likely_western`. Sentences without any documented marker may be `inconclusive`.
- **With markers:** Sentences that contain known WA markers (e.g. **կը**, **մը**, **իւ**) must classify as `likely_western`; sentences with EA markers (e.g. **մի** before noun) must classify as `likely_eastern`.
- **Vocabulary:** WA vocabulary in the JSON must not be classified as Eastern.
- Run: `pytest tests/test_textbook_wa_dialect.py -v`

---

## 5. Files to Create or Update


| File                                                                       | Purpose                                                                               |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `docs/armenian_language_guids/TEXTBOOK_MODERN_WESTERN_ARMENIAN_GRAMMAR.md` | This document: summary, baseline, checklist.                                          |
| `tests/data/textbook_modern_wa_vocab_and_sentences.json`                   | Vocabulary and example sentences (baseline + textbook when available).                |
| `tests/test_textbook_wa_dialect.py`                                        | Tests that run dialect classifier (and optionally transliteration) on these examples. |
| `data/textbook_modern_wa_extract.txt` | Single OCR output (Option A). Created by `python -m ocr.textbook_modern_wa`. |
| `data/textbook_modern_wa_pages/` | Per-page OCR .txt (Option A). |
| `data/textbook_modern_wa/` (optional) | Extracted textbook text by chapter (Option B). |


---

## 6. References

- **Textbook PDF:** `c:\Users\litni\OneDrive\Documents\anki\books\textbook-of-modern-western-armenian.pdf`
- **Codebase grammar:** `linguistics/morphology/grammar_rules.py`, `linguistics/dialect_branch_classifier.py`
- **WA vs EA:** `docs/armenian_language_guids/WA_EA_LINGUISTIC_DISTINCTIONS.md`
- **Test reference:** `docs/armenian_language_guids/TEST_VALIDATION_ARMENIAN.md`
- **Phonetics:** `docs/armenian_language_guids/WESTERN_ARMENIAN_PHONETICS_GUIDE.md`, `ARMENIAN_QUICK_REFERENCE.md`

