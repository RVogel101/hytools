# Future Improvements (armenian-corpus-core)

Items tracked for data collection, scraping, corpus research, and related pipelines. Implemented features are documented in [IMPLEMENTATION_HISTORY.md](IMPLEMENTATION_HISTORY.md).

---

## Summary table (high-level status)

| Area / Project                                  | Status            | Priority      | Next steps                                                                                     |
|-------------------------------------------------|-------------------|---------------|------------------------------------------------------------------------------------------------|
| Phase 2 enhancement pipeline                    | In progress       | High          | Hybrid profile, incremental merge, exporters, robust tests (see docs/development/PHASE2_CHECKLIST.md) |
| Western Armenian audio for voice-generation     | Research / planned| Medium        | Finalize audio metadata schema; add optional audio track + ingestion scripts; pick 1–2 pilot sources (ReRooted, MWA/Vatican). |
| Loanword and etymology extensions               | Planned           | Medium        | Design minimal etymology/loanword schema; prototype stem catalog + transliteration helpers; wire into corpus metadata. |
| Etymology DB, stem catalog, transliteration     | Research complete | Medium        | Implement recommended pipeline (Wiktextract + Nayiri headwords); add small `etymology` collection and stem storage. |
| Transliteration / IPA / pronunciation guide    | Partially done     | Medium        | Unwritten ը (insert_schwa) and Western և/եւ implemented. Remaining: word break-up, վ vs ու passive-verb rule; see section below. |
| Latin → Armenian spelling consistency         | Planned           | Medium        | Check known words / reference lexicon for consistent classical spelling. |
| Western Armenian keyboard (Android)           | Planned           | Medium        | Build installable WA phone keyboard for Android (classical orthography). |
| HathiTrust bulk integration                     | Blocked / future  | Low           | Decide on HTRC membership or Hathifiles-only approach; if approved, implement `load_htrc_bulk()` and integration tests. |
| Internet Archive access constraints             | Policy note       | Low           | Keep as guardrail; only revisit if a rights-cleared IA workflow is explicitly requested.      |
| Gallica SRU access reliability                  | Future tweak      | Low/Medium    | Confirm UA and rate limits in `scraping/gallica.py`; add explicit 403 diagnostics and doc link to BnF support. |
| LOC web content (blogs / hub pages)             | Planned           | Medium        | Define seed URL list; implement `loc_web_articles` scraper with robots/TOS checks; add new `source` type in Mongo. |
| Grammar / dialect metrics                       | Planned           | Medium        | Specify metric set (e.g. GrammarDistanceIndex features); implement on a sample corpus; feed into dialect clustering. |
| **Reform ↔ Classical orthography converter**    | Planned           | Medium        | Build a bidirectional converter between Reformed (Soviet-era) Armenian orthography and Classical (Mashdotsian) orthography. Should handle all systematic spelling differences (e.g. -ութիւն → -ություն, -եալ → -ել, -ոյ → -ու, etc.) in both directions. Expose as `linguistics/orthography/reform_classical_converter.py` with `to_classical(text)` and `to_reform(text)` functions. Useful for cross-orthography corpus normalization, search, and deduplication. |
| **Eastern ↔ Western Armenian dialect converter** | Planned          | High          | Build a bidirectional rule-based converter between Eastern Armenian and Western Armenian. Must handle: (1) systematic voicing reversals (բ/պ, գ/կ, դ/տ, ձ/ծ, ջ/ճ), (2) morphological differences (verbal aspect markers, pronominal forms, postpositions vs. prepositions), (3) lexical substitutions (common word-level divergences). Expose as `linguistics/dialect/dialect_converter.py` with `to_western(text)` and `to_eastern(text)`. This is a research-grade tool — phonological rules must be verified against `docs/armenian_language_guids/` and `linguistics/phonetics/`. Should NOT be used silently in the pipeline; always surface source dialect in metadata. |
| **Corpus-wide normalized TTR pipeline**         | Planned           | Medium        | Raw TTR decreases with text length, making cross-document comparison unreliable. Planned: a corpus-wide pass that computes Standardized TTR (STTR, 100-token windows) for every document and stores the result in `metadata.sttr_normalized`. This gives a length-independent vocabulary richness score suitable for dialect comparison, register analysis, and augmentation quality tracking. Trigger: after `text_metrics` backfill is complete. |
| **Clause-count via finite-verb markers**        | Planned           | Low           | Current clause detection counts subordinating conjunctions (\u0578\u0580, \u056b\u0576\u0579, \u0565\u0569\u0567 etc.) as a proxy. A more accurate Armenian-specific approach is to count finite verb markers per sentence: WA uses \u056f\u0565/\u056f\u055a prefix or inflected suffixes (-\u0565\u0574/-\u0565\u057d/-\u0565/\u0563\u056f/-\u0565\u0576). Implement as an optional analysis mode requiring morphological POS tagging. |
| **Decomission metadata.dialect field**          | **Implemented**   | High          | All 7 scrapers stop writing `metadata.dialect`; 5 readers updated to derive from `metadata.language_code`; `metadata_tagger.py` cleaned; EDA notebook updated. Existing MongoDB docs still have the field — run `$unset` migration. |
| **Incremental `text_metrics` pipeline (`_update_text_metric`)** | Planned | Medium | `text_metrics_date` sentinel is now written per-doc when `metadata.text_metrics` and `metadata.loanwords` are first computed. Future work: build a dedicated `_update_text_metric` runner (or add a `--backfill-text-metrics` flag to `metadata_tagger`) that queries `{metadata.text_metrics_date: null, metadata.enrichment_date: {$exists: true}}` and processes only untagged docs. This lets the expensive `QuantitativeLinguisticsAnalyzer` + `analyze_loanwords` computations run incrementally as new documents arrive without re-processing the whole corpus. |
| **Missing URL backfill (wiki, culturax)**       | **Implemented**   | High          | wiki.py now constructs Wikipedia URLs from language_code + title; culturax.py passes `doc["url"]` through to MongoDB. Re-scraping needed to backfill existing docs. |
| **EDA short-text & missing-URL breakdowns**     | **Implemented**   | Medium        | Added notebook cells 18a (missing URL by source) and 18b (short text <100 chars by source) to `mongodb_eda.ipynb`. |
| Grammar logic scripts                           | Planned           | Medium        | Extend `linguistics/morphology` rules for gaps; add tests; update `phonetics_rule_gaps.md` with any new edge cases. |
| Book/manuscript catalog integration             | Planned           | Medium        | Connect catalog + `book_inventory` to drive archive_org/LOC/Hathi queries and dedup; implement a small pilot job. |
| New source – Gallica (BNF)                      | Implemented       | Medium        | Keep SRU config in sync with API docs; monitor errors; periodically refresh catalog and validate WA coverage. |
| New source – DPLA                               | Implemented       | Medium        | WA scoring added to pipeline (dialect classification on insert); API key required; review English/Armenia-related items. |
| New source – Gomidas Institute                  | Implemented       | Medium        | Run PDF→OCR pipeline periodically; validate OCR quality; update metrics on WA newspaper coverage.            |
| New source – Hamazkayin / Pakine                | **Implemented**   | High          | Scraper in `ingestion/acquisition/hamazkayin.py`; WP REST API + HTML fallback; pakine.net (literary) + hamazkayin.com (news). |
| New source – Mechitarist (Venice)               | Planned / external| Medium/Long   | Use MECHITARIST_PERMISSION_REQUEST.md to request access; if granted, implement/enable scraper.               |
| New source – AGBU Nubar (Paris)                 | Planned / external| Medium/Long   | Use AGBU_NUBARIAN_LIBRARY_PARTNERSHIP.md email; on approval, implement/enable scraper and catalog loader.    |
| New source – UK Centre for Western Armenian Studies (CFWAS) | Planned / external| Medium/Long | Follow DATA_SOURCES_EXPANSION.md; contact CFWAS (Memory Documentation Project) for transcript/text access; design ingest once terms are clear. |
| New source – National Library of Armenia (NLA)  | Planned / external| Medium/Long   | Do not scrape; contact NLA about research/bulk access to digitized/OCR’d content; design API/ingest only if permitted. |
| New source – British Library EAP (EAP613, EAP180) | Planned / external| Medium/Long | Use IIIF manifests; confirm reuse permissions with custodians; design image→OCR→ingest pipeline respecting terms. |
| New source – Zohrab Center (NYC)                | Planned / external| Medium/Long   | Contact center about digitized ecclesiastical texts; if allowed, plan scan/OCR ingest with WA tagging.       |
| Session carry-forward (EA subcategories, etc.)  | Planned           | Medium        | Backfill EA subcategory metadata; improve clustering evaluation; tune fallback crawl depth.   |
| **OCR: GPU / build vs collaborate**            | Very low priority | Very low      | Long-term: option to train own Armenian OCR model (PaddleOCR/EasyOCR); keep option to collaborate with existing projects (e.g. portmind/armenian-ocr, ArmCor for post-correction). See ARMENIAN_OCR_GPU_AND_QUALITY.md. |
| **OCR: per-page sidecar report**               | Optional          | Low           | Optional sidecar (JSON or CSV) from `ocr_pdf()` with per-page mean_confidence, char_count, word_count, skipped; machine-readable for low-yield detection. See ARMENIAN_OCR_GPU_AND_QUALITY.md §4.4. |
| **Newspaper article splitting helper**         | Planned           | Medium        | Design and implement a reusable helper for long Armenian newspapers (e.g. ՊԻՈՆԵՐ, Արեւելք) that splits IA issues into article-sized documents using header/date patterns and size limits; integrate with `scraping.archive_org` and other newspaper scrapers. Use **news_article_catalog** (RSS-derived titles/URLs) to better inform split boundaries and article titles when splitting full-issue OCR. |
| **Defunct newspapers → Wayback Machine**       | Planned           | Low/Medium    | If a newspaper is no longer operational, explore scraping archived versions via the Wayback Machine (e.g. archive.org/web) so we can still ingest historical issues. |
| English ↔ Western Armenian translation pipeline | High priority     | High          | Choose initial model(s); assemble WA–EN parallel data; implement back-translation + instruction-tuning pipeline and evaluation. |
| **New source – WA Pedagogical Curriculum**      | Planned / research| High          | Full WA curriculum: grammar lessons, reading texts, exercises, stories designed for diaspora WA learners → clean pedagogical WA prose with no parallel in existing pipeline. Scrape text + PDFs (OCR), catalogue audio/video assets. Identify source(s): AGBU AVC, Zarmanazan, Saturday-school textbooks, INALCO materials. Check licensing/permissions before scraping. |
| **B-1** Package __init__.py exports              | Done (cleaning, ocr) | Medium     | `cleaning/__init__.py` and `ocr/__init__.py` now export the requested symbols. Optionally add `__all__` to `scraping/__init__.py`. |
| **B-3** Tests for core scrapers                  | Not started       | Medium        | Mock HTTP for archive_org (pagination, download), loc (catalog, retry), wikisource (category pagination); unit tests for culturax streaming, wikipedia dump resolution. |
| **B-5** Top-level pipeline script                | Not started       | High          | Add a run_pipeline CLI (e.g. `ingestion/tools/run_pipeline.py` or repo root) with `--stage` (scrape, ocr, clean) and `--all`; delegate to `ingestion.runner`, `ocr`, `cleaning.runner`; support `--dry-run`. Training stage lives in WesternArmenianLLM. |
| **B-6** Western Armenian markers (language/WA classifier) | Partially done | High          | Expand WA/EA markers in `scraping/_helpers.py` to 25+; add EA-only negative markers; make threshold tunable in `config/settings.yaml`. `compute_wa_score` already returns float. |
| **B-6a** Centralized WA/EA marker source in helpers (`_CONSOLIDATED_RULES`) | Implemented | High | `cleaning/language_filter.py` now imports WA/EA marker sets, authors, cities, punctuation, and regex from `hytools.ingestion._shared.helpers`; local duplication removed; EA authors and WA publication cities names are now sourced centrally and ready for dialect-mix detection. |
| **B-7** Research pipeline validation             | In progress       | High          | Harden `ingestion/discovery/author_extraction.py` regex handling; add optional `--exclude-dirs` CLI to `ingestion/research_runner.py` (config already has `research.exclude_dirs`). Verify full pipeline run and outputs. |
| Wikipedia / data source mining                   | Planned           | Medium        | Parse document metadata for citations; build source catalog and provenance graph; output `data/source_catalog.json`, `data/source_provenance.jsonl`. |
| New source – Agos (agos.com.tr/am)               | **Implemented**   | High          | Standalone `requests` crawler in `ingestion/acquisition/agos.py`; crawls 10 category pages with `?p=N` pagination; registered in runner (`--only agos`). |
| New source – WesternArmeniaTV (society_wa)       | Planned           | High          | Investigate and scrape Western Armenian section at https://westernarmeniatv.com/society_wa/ (e.g., https://westernarmeniatv.com/society_wa/%d5%b0%d5%a1%d5%b5%d5%af%d5%a1%d5%af%d5%a1%d5%b6-%d5%ac%d5%a5%d5%bc%d5%b6%d5%a1%d5%b7%d5%ad%d5%a1%d6%80%d5%b0-%d5%b8%d5%b9-%d5%a9%d5%a7-%d5%a1%d6%80%d5%a5%d6%82%d5%a5%d5%ac%d5%a5%d5%a1%d5%b6-%d5%a1/) and align with WA scoring rules; also inspect English page for context. |
| WA pedagogical curriculum (diaspora schools)      | Research / planned| High          | Scrape full WA curriculum materials (grammar, reading, exercises, stories) from diaspora educational programs; PDFs through OCR; video/audio for future TTS/ASR; unique pedagogical WA prose not in any existing source. |

---

## Backlog items (from archived WA-LLM doc)

These items were migrated from `WesternArmenianLLM/docs/archive/root-docs-2026-03/ops/FUTURE_IMPROVEMENTS.md`. Paths below refer to **armenian-corpus-core** (no `src/`; packages at repo root: `cleaning/`, `ocr/`, `ingestion/` including discovery, enrichment, aggregation; research pipeline under `ingestion/`).

### B-1. Fill __init__.py stubs with proper exports

| Package      | Status           | Notes |
|-------------|------------------|--------|
| `cleaning/__init__.py` | **Done** | Exports `normalize`, `deduplicate_files`, `is_western_armenian`, `is_armenian`, `compute_wa_score`, `WA_SCORE_THRESHOLD`, plus tokenizer and author_database symbols. |
| `ocr/__init__.py`      | **Done** | Exports `ocr_pdf`, `preprocess`, `postprocess` from `ocr/pipeline.py`, `ocr/preprocessor.py`, `ocr/postprocessor.py`. |
| `ingestion/__init__.py` | **Documented**   | Ingestion package; use `ingestion.runner`, `ingestion.acquisition.*`, etc. |
| `rag/`, `serving/`     | **N/A**          | Not present in armenian-corpus-core; omit. |

---

### B-3. Tests for core scrapers

**Status:** Not started.  
**Priority:** Medium.

Existing: `tests/test_digital_library_scrapers.py` (LOC, archive_org, gallica, hathitrust, gomidas with mocked HTTP). Missing or to expand:

- **archive_org.py** — tests for search pagination and download (beyond current search mock).
- **loc.py** — catalog building and retry logic (current test covers search_items).
- **wikisource.py** — category pagination and text fetch (mocked).
- **culturax.py** — unit tests for streaming loader.
- **wikipedia.py** — dump resolution and date handling.

**Effort:** ~3 hours.

---

### B-5. Top-level pipeline orchestration script

**Status:** Not started.  
**Priority:** High.

No single script ties scrape → OCR → clean together. Desired interface:

```text
python -m ingestion.tools.run_pipeline --stage scrape --source loc   # or similar entry point
python -m ingestion.tools.run_pipeline --stage ocr
python -m ingestion.tools.run_pipeline --stage clean
python -m ingestion.tools.run_pipeline --all   # scrape + ocr + clean
```

Each stage should delegate to the relevant runner (`ingestion.runner`, OCR entry point, `cleaning.runner`), with progress logging, graceful handling of interruption, and `--dry-run`. The **train** stage lives in **WesternArmenianLLM** (e.g. `prepare_training_data`, `pretrain`, `instruct_finetune`); corpus-core focuses on data acquisition and cleaning.

**Effort:** ~2 hours.

---

### B-6. Expand Western Armenian markers (language/WA classifier)

**Status:** Partially done.  
**Priority:** High.

WA scoring lives in `scraping/_helpers.py`: `compute_wa_score()` (float), `is_western_armenian()`, `WA_SCORE_THRESHOLD`. Vocabulary, authors, and publication cities already provide many markers; EA reform and EA vocabulary subtract. `cleaning/language_filter.py` uses these helpers and adds author-aware checks.

**Remaining:**

- Expand to **25+** WA markers (vocabulary list in `_helpers` is already substantial; add any missing from vocabulary divergence lists).
- Add **negative markers**: explicit EA-only forms that auto-fail (e.g. գնաց, ֊ում suffix, reformed orthography).
- **Config threshold:** Make `WA_SCORE_THRESHOLD` (or a per-run threshold) tunable via `config/settings.yaml` (e.g. `cleaning.wa_score_threshold`).
- Optional: connect to `linguistics/metrics/corpus_vocabulary_builder.py` cache (EA-only words) for consistency.

**Effort:** ~1.5 hours.

---

### B-7. Stabilize research pipeline validation (Phase 3)

**Status:** In progress (modules implemented; validation and hardening ongoing).  
**Priority:** High.

- **ingestion/discovery/author_extraction.py** — Add defensive handling around all regex match/group usage so that missing groups do not cause hard failures; continue on per-file/per-pattern failure with structured logs. (One `try/except IndexError` exists for a single pattern; extend to other patterns.)
- **ingestion/research_runner.py** — Exclude dirs are already config-driven via `ingestion/_shared/research_config.py` (`exclude_dirs`, default `["augmented", "logs", "__pycache__"]`). Optional: add `--exclude-dirs` CLI argument to override config so that `python -m ingestion.research_runner --exclude-dirs augmented ...` works without editing YAML.
- **Validation gate:** Run  
  `python -m ingestion.research_runner --skip-enrichment --wikipedia-lookups 5`  
  (with config or CLI excluding `augmented`). Confirm outputs exist and contain data:  
  `data/author_profiles.jsonl`, `data/author_timeline.json`, `data/author_periods.csv`, `data/author_generations.json`, `data/coverage_gaps.json`, `data/acquisition_priorities.csv`.

**Effort:** ~1–2 hours for hardening and verification.

---

### Wikipedia / data source mining (future)

**Objective:** Extract and catalog data sources referenced in corpus documents.

- Parse document metadata for citations and references; extract Wikipedia links, academic sources, newspaper archives.
- Build a data provenance graph: document → cited_sources → source_metadata (publication year, location, author).
- Create a source catalog: URL / ISBN / Catalog ID, publication date, geographic origin, language variant (WA/EA), reliability/confidence score.
- **Outputs:** `data/source_catalog.json`, `data/source_provenance.jsonl`.
- **Use cases:** Audit corpus for bias; trace knowledge lineage; identify high-authority sources for expansion.

**Status:** Planned. Not yet implemented.

---

### Research pipeline implementation status (Phases 1–2 and 3)

**Location:** Author/book pipeline is under **armenian-corpus-core** `ingestion/` (discovery, enrichment, aggregation, research_runner, _shared/research_config).

**Phase 1–2 (book inventory and author research)** — Implemented:

- `ingestion/discovery/book_inventory.py` — Book entry data model and inventory manager.
- `ingestion/discovery/worldcat_searcher.py` — WorldCat API integration (and fallback data).
- `ingestion/discovery/book_inventory_runner.py` — CLI for inventory acquisition.
- `ingestion/discovery/author_research.py` — Author profile model and profile manager.
- Tests: `tests/test_book_inventory.py`, `tests/test_worldcat_searcher.py`, `tests/test_author_research.py` (when present in this repo).
- Outputs: MongoDB collections (book_inventory, author_profiles, etc.); optional file exports when MongoDB not used.

**Phase 3 (author extraction, enrichment, timeline, coverage)** — Implemented:

- `ingestion/discovery/author_extraction.py` — NER and pattern-based author extraction from corpus (book inventory, metadata, text patterns); dedup and name normalization; AuthorProfile generation.
- `ingestion/enrichment/biography_enrichment.py` — Wikipedia (hyw, hy, en) and manual database enrichment; confidence scoring.
- `ingestion/aggregation/timeline_generation.py` — Author lifespans, publication periods, period analysis, generation groupings, historical context.
- `ingestion/aggregation/coverage_analysis.py` — Author/period/genre/work coverage gaps; priority scoring; acquisition checklists.
- `ingestion/research_runner.py` — Orchestration CLI (extraction → enrichment → timeline → coverage); configurable phase skipping; uses `ingestion/_shared/research_config.py` for `exclude_dirs` and error thresholds.

**Outputs:** `data/author_profiles.jsonl`, `data/author_timeline.json`, `data/author_periods.csv`, `data/author_generations.json`, `data/coverage_gaps.json`, `data/acquisition_priorities.csv`, `data/high_priority_acquisitions.csv`.

**Next steps (from archived doc):** Run pipeline on full corpus; integrate with augmentation metrics; optional visualization dashboard; NER model for author extraction; expand manual biography database; author collaboration network analysis.

---

## Transliteration, IPA, and pronunciation guide (future enhancements)

**Goal:** Extend `linguistics/transliteration.py` and related docs so that Armenian ↔ Latin, Armenian → IPA, and pronunciation aids behave correctly for Western/Classical/Eastern and support full sentences.

### Pronunciation guide: word break-up

- **Build functionality** to break a word into parts as a pronunciation guide.
- **Examples:**  
  - տեսնել → տես-նէլ  
  - սպասել → (ը)սպ-ա-սել (unwritten schwa at start before սպ)  
  - մնալ → մ(ը)ն-ալ (unwritten schwa between consonants մ and ն)
- **Implementation:** Syllabification or rule-based split that inserts hyphenation and optional parenthesized unwritten ը where pronunciation requires it. Reference: `docs/armenian_language_guids/` for rules on epenthetic schwa (between two consonants; word-initial սպ, etc.).

### Digraph ու (classical / Western)

- In **traditional (classical) spelling**, which Western Armenian uses, **ու** is **context-specific**:  
  - Between consonants → "oo" (diphthong).  
  - Before a vowel → "v" sound (ւ as consonant).  
- **Implementation:** When converting Armenian → Latin or → IPA, check the character after **ու**: if it is a vowel, output "v" + the vowel’s romanization; otherwise output "ou" (or "oo") for the diphthong. Apply the same logic in reverse (Latin → Armenian): "ou"/"oo" → ու; "v" before vowel may need to stay as վ or context-dependent ւ depending on word shape.

### Latin → Armenian (reverse)

- **Dialect option:** Ensure Latin → Armenian supports **western**, **eastern**, and **classical** (already present; document clearly).
- **Western և in words:** Western Armenians typically **do not use the և symbol inside words**; use **եւ** (two characters). Use **և** only for the word meaning "and". When converting Latin → Armenian for Western, output **եւ** for "ev"/"yev" inside words, and **և** only when the token is the conjunction "and". **Implemented** in `linguistics/transliteration.py`: standalone "and"/"ev"/"yev" → և; in-word "ev"/"yev" → եւ.
- **վ vs ու for "v" at end of passive verb:** Research when to use **վ** vs **ու** for the "v" sound at the end of passive verbs in Western Armenian / classical orthography. Document findings in `docs/armenian_language_guids/` or `docs/development/TRANSLITERATION_IPA_MAPPING_REPORT.md` and implement a rule or heuristic if possible (e.g. passive participle ending -վ vs -ու by paradigm).

### Unwritten ը (schwa) in IPA and Latin

- **Armenian → IPA / Latin (Western):** Account for **unwritten ը** in the construction of IPA and of Latin romanization.  
  - **Between two consonants:** Insert epenthetic schwa (e.g. մնալ → մընալ in pronunciation, so IPA and optionally Latin show the schwa).  
  - **Word-initial սպ:** Rule that word-initial **սպ** is pronounced with an unwritten ը (e.g. սպասել → ըսպասել).  
- **Reference:** `docs/armenian_language_guids/` (WESTERN_ARMENIAN_PHONETICS_GUIDE.md, ARMENIAN_QUICK_REFERENCE.md, and any notes on epenthetic schwa). Add explicit rules to the guide if missing.  
- **Classical / Eastern:** Research whether similar unwritten schwa or prosthetic vowel rules exist in Classical and Eastern Armenian and add them to the transliteration/IPA logic and to the mapping report.

### Western Latin convention for ու

- For **Western** Armenian → Latin, use **"ou"** (or **"oo"**) for the **ու** diphthong (e.g. ջուր → chour / choor), not "u", to avoid collision with ը→u.  
- **Reverse:**  
  - **"u"** → **ը** (schwa).  
  - **"ou"** or **"oo"** → **ու**.

### Full text and sentences

- The current implementation is **built for full text**: it processes whatever string is passed (word, sentence, or paragraph) character-by-character and leaves non-Armenian characters unchanged. So **sentences and full-text transliteration are supported**; document this in the module docstring and in the Jupyter notebook.

### Jupyter notebook

- Provide a **Jupyter notebook** with examples to test: single words, sentences, and full-text Armenian → Latin, Latin → Armenian, and Armenian → IPA for western/eastern/classical. Include verification words and edge cases (ու, ը, և/եւ, unwritten schwa).

### Latin → Armenian: spelling consistency

- **Enhance Latin → Armenian** by checking candidate output against **known words** with similar spelling so that all words are spelled **consistently** according to documented, agreed-on spelling.
- **Implementation:** Maintain or link to a reference lexicon (e.g. Nayiri headwords, etymology collection, or curated word list in classical orthography). When converting a roman token to Armenian, look up the token or close matches in the reference; if a canonical spelling exists, prefer it over the raw reverse mapping. This reduces variation (e.g. եւ vs և in words) and aligns with project classical orthography.

### Western Armenian keyboard (Android)

- **Build a Western Armenian phone keyboard** as an installable option for **Android** users.
- **Scope:** Layout and key mapping for Western Armenian (classical orthography), optionally with long-press variants and punctuation. Distribute as an installable keyboard (e.g. via Play Store or APK) so users can type Western Armenian on their phones.
- **Reference:** Existing Armenian keyboard apps (Eastern/Western) and Android input method (IME) documentation; ensure layout follows agreed-on spelling (classical orthography, իւ, etc.).

---

## Western Armenian audio for voice-generation training

**Goal:** Identify and leverage existing Western Armenian (WA) audio for training or fine-tuning voice/TTS models, or for building a WA speech corpus aligned with this project’s text corpus.

### Summary of findings


| Source                                       | Type                  | Dialect                                | Hours / size                      | Access                                                                                                            | Notes                                                                                                                                                                                 |
| -------------------------------------------- | --------------------- | -------------------------------------- | --------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ReRooted Syrian Armenian Corpus**          | Speech (testimonials) | Western (Syrian Armenian)              | ~80 h transcribed                 | Public; GitHub (GPL-3.0)                                                                                          | Time-coded transcriptions; linguistics/NLP; [github.com/jhdeov/ReRooted-ArmenianCorpus](https://github.com/jhdeov/ReRooted-ArmenianCorpus), [rerooted.org](https://www.rerooted.org/) |
| **Modern Western Armenian (MWA) – research** | Aligned corpus        | Modern Western Armenian                | ~70 h (from ~230 h raw)           | Hugging Face (research release)                                                                                   | From Vatican Radio + ReRooted; part of multi-dialect ASR study (2026); check Hugging Face for `armenian` / `western` / `MWA`                                                          |
| **Mozilla Common Voice (Armenian)**          | Crowdsourced speech   | Mixed (EA + WA)                        | ~5 h (2023); goal 300 h           | [commonvoice.mozilla.org](https://commonvoice.mozilla.org)                                                        | WA under-represented (Wikipedia-heavy prompts); contribute/validate WA sentences and clips                                                                                            |
| **Armenian Voices (Dataset.am)**             | Recorded clips        | Armenian (dialect not specified)       | 12.46 h, 5,811 clips (~7.7 s avg) | [dataset.am](https://dataset.am/) – email for Corpus 2                                                            | Open voice dataset; confirm dialect tagging for WA subset                                                                                                                             |
| **Vatican News Armenian**                    | Radio/podcast         | Western (liturgical/diaspora)          | Ongoing                           | [vaticannews.va/hy](https://www.vaticannews.va/hy.html), podcast feeds                                            | Need scraping + ASR/alignment for training; licensing for redistribution unclear                                                                                                      |
| **Armenian Audiobooks (podcast)**            | Read-aloud WA         | Western                                | 20+ episodes                      | Apple Podcasts, Spotify (Kamee Abrahamian)                                                                        | Clear WA; permission needed for corpus use                                                                                                                                            |
| **ARA Armenian Radio Archive**               | Archive               | Mixed (historical)                     | Large                             | [armradioarchive.am](https://armradioarchive.am/)                                                                 | Digitized since 1937; songs, programs, talk; need dialect tagging and licensing                                                                                                       |
| **ArmTTS**                                   | TTS engine            | Eastern (Tigran/Nune); Armenian script | N/A (synthetic)                   | [armtts.online](https://armtts.online), GitHub (C++/iOS), Maven/CocoaPods                                         | Eastern voices + Hugging Face `eastern_armenian_tigran_nune`; useful for EA baseline; WA would need separate data/model                                                               |
| **Artsakh / Lori / Mush (Hugging Face)**     | Aligned ASR           | Artsakh, Lori, Mush                    | Part of 70 h multi-dialect        | e.g. [DALiH-ANR/artsakh_hy](https://huggingface.co/datasets/DALiH-ANR/artsakh_hy)                                 | Dialect-specific; complement WA with distinct regional varieties                                                                                                                      |
| **Chillarmo Armenian-speech-corpus**         | Speech corpus         | **Eastern**                            | 35,595 pairs, ~10.8 GB            | [Chillarmo/Armenian-speech-corpus](https://huggingface.co/datasets/Chillarmo/Armenian-speech-corpus) (Apache 2.0) | EA only; not WA but useful for multi-dialect or transfer learning                                                                                                                     |


### Recommendations

1. **Immediate:** Download and normalize **ReRooted** (GPL-3.0) and check Hugging Face for **MWA / Vatican-derived** releases for WA-aligned audio–text pairs.
2. **Community:** Contribute and validate **Common Voice** Armenian with WA prompts and recordings; request or add WA-specific tags/splits.
3. **Partnerships:** Inquire with **Vatican News**, **Armenian Audiobooks**, and **ARA** for licensing and bulk access (and, where needed, transcriptions) for WA voice training.
4. **Pipeline:** Add an optional “audio” or “voice” track in corpus-core: metadata schema for audio sources, links to text corpus (e.g. by script/source), and scripts to fetch or index ReRooted/Common Voice/Dataset.am with dialect labels.
5. **Research:** Reuse multi-dialect ASR work (e.g. Whisper/Seamless fine-tuning on 70 h aligned corpus) for WA-specific TTS data prep (alignment, segmentation, quality filters).

### References (indicative)

- ReRooted: [github.com/jhdeov/ReRooted-ArmenianCorpus](https://github.com/jhdeov/ReRooted-ArmenianCorpus), [rerooted.org](https://www.rerooted.org/)
- Common Voice Armenian: [ekeleshian.github.io/.../armenian-common-voice-frequently-asked-questions](https://ekeleshian.github.io/posts/armenian-common-voice-frequently-asked-questions/)
- Armenian dialect ASR (MWA, Vatican, ReRooted): *International Journal of Speech Technology* (2026), Springer; multi-dialect datasets on Hugging Face.
- ArmTTS: [armtts.online](https://armtts.online), [github.com/albert-grigoryan/ArmTTS-Cpp](https://github.com/albert-grigoryan/ArmTTS-Cpp)
- Armenian Voices: [dataset.am](https://dataset.am/)

---

## Loanword and etymology extensions

- **Etymology**: Track etymological origin per Armenian word; support multiple theories with credibility weights. Integrate Wiktionary, Nayiri, academic sources.
- **Stem catalog**: Build catalog of stem/root words; track roots in compound words (e.g. `ան-`, `-ութիւն`).
- **Transliteration for dictionary lookup**: WA/EA → English (romanization); EA → Cyrillic; WA → Arabic/French/Turkish; EA → Farsi; romanized → Armenian; Armenian → IPA (WA/EA).
- **Updatable loanword catalog**: File-based or DB-backed catalog; candidate extraction + human review.

See `**docs/ETYMOLOGY_STEM_TRANSLITERATION_STRATEGIES.md`** for strategies.

---

## Etymology DB, stem catalog, and transliteration (research summary)

**Goal:** Support loanword tracking, dictionary lookups, and corpus analysis. Feasibility-oriented summary.

### 1. Etymology database


| Approach                     | Pros                                              | Cons                                                      |
| ---------------------------- | ------------------------------------------------- | --------------------------------------------------------- |
| **Wiktionary / Wiktextract** | Structured dumps (JSONL); kaikki.org; no API key. | Armenian coverage partial; filter by language, map WA/EA. |
| **Nayiri**                   | Armenian-focused; stem dictionary (Atcharyan).    | API terms/rate limits unclear; may need partnership.      |
| **Custom curation**          | Full control; credibility weights.                | High effort; linguist input; maintenance.                 |


**Recommendation:** Start with Wiktextract/kaikki Armenian entries and Nayiri headword list. Add small `etymology` or `loanword_origin` collection; later Nayiri API if available.

### 2. Stem catalog


| Approach                        | Pros                                                      | Cons                                        |
| ------------------------------- | --------------------------------------------------------- | ------------------------------------------- |
| **Nayiri stemmer**              | Canonical form from inflected (e.g. կատուներուս → կատու). | May be EA-biased; API/export needed.        |
| **Rule-based suffix stripping** | No external dependency; repeatable.                       | WA/EA/Classical differ; over/understemming. |
| **ML stemmer**                  | Can learn WA-specific patterns.                           | Requires labeled data and training.         |


**Recommendation:** Nayiri for lookup when available; minimal rule-based stem list for frequent affixes; store stems in same schema as etymology.

### 3. Transliteration pipelines

Implement **Armenian (script) → ISO 9985 Latin** for dictionary keys and search. Add **Armenian → IPA** for WA and EA as separate modules. **Romanized → Armenian** as second phase with disambiguation. Store tables as data files (JSON/CSV); optional caching in MongoDB.

### 4. Data sources

- **Wiktionary / Wiktextract:** [https://kaikki.org/dictionary/Armenian/](https://kaikki.org/dictionary/Armenian/) ; [https://github.com/tatuylonen/wiktextract](https://github.com/tatuylonen/wiktextract)
- **Nayiri:** [https://www.nayiri.com/](https://www.nayiri.com/) (Developers section); Atcharyan stem dictionary
- **ISO 9985:** ISO 9985:2026; transliteration reference tables

---

## HathiTrust (remaining work)

- **Current:** Scraper uses catalog search and Data API; catalog/status in MongoDB. Bibliographic fallback when full text unavailable; stub `load_htrc_bulk()`.
- **Remaining:** Full HTRC bulk integration (Extracted Features or full-text packages) requires HTRC membership/agreement.

---

## Internet Archive access constraints (future enhancement)

- Borrow-only / rights-restricted items on archive.org return HTTP 401/403 for text downloads (e.g. DjVuTXT). These should be treated as out-of-scope for the default scraper: you cannot (and should not) bypass them without logging in via a browser-style flow and ensuring full compliance with archive.org’s Terms of Service.
- If we ever decide to pursue those titles, it should be a separate, explicitly consented workflow (e.g. browser automation tied to a human account, with strict rate limits and manual review), not part of the normal corpus build.

---

## Gallica SRU access reliability (future enhancement)

- Ensure the Gallica scraper sends a clear, descriptive User-Agent and uses very conservative rates (e.g. 1–2 requests/second or slower).
- When Gallica returns 403 for SRU calls, manually test a simple SRU query in a browser from the same machine (e.g. `https://gallica.bnf.fr/SRU?version=1.2&operation=searchRetrieve&query=(dc.language any "arm") and (dc.type any "monographie")&maximumRecords=1&startRecord=1`). If the browser also sees 403, it is almost certainly an IP/network/policy issue, not scraper code.
- If 403 persists from the browser, contact BnF via their API/support channels, explaining the research use-case and asking whether (a) SRU requires registration or an API key, (b) the current IP/range is blocked or needs whitelisting, and/or (c) a different endpoint (e.g. Catalogue général SRU URL) is preferred for automated use.

---

## LOC web content (blogs / hub pages) as separate source (future enhancement)

- Some LOC slugs in the catalog (e.g. `articles-and-essays`, `related-resources`, `4-corners-international-collections-program-calendar-...`, Armenian-program blog posts) are **web pages on loc.gov**, not catalog items exposed via the LOC JSON item API. The current `loc` scraper correctly gets 404 for those when it calls the item endpoint and skips them.
- If we want that text anyway, we should add a **separate pipeline for LOC web content**, distinct from the catalog-based `loc` stage:
  - Seed: a curated list of URLs (e.g. Armenian blog posts, program calendars, “Armenian Memorial Books at the Library of Congress”, Armenian-American song pages).
  - Scraper: standard HTML scraper (requests + BeautifulSoup) that works off `loc.gov` article URLs, not the JSON item API.
  - Compliance: observe `robots.txt` and any separate TOS for `loc.gov` web properties (which may differ from the catalog API).
  - Storage: insert into `documents` with a separate `source` (e.g. `loc_web_articles`), so catalog-based `loc` items and web-article content are distinguishable in the corpus.

---

## WA dialect classifier audit (backtest)

- The `compute_wa_score` heuristic in `ingestion/_shared/helpers.py` has never been evaluated against labeled ground-truth data.
- **Task:** Assemble a small labeled test set — ~100 documents confirmed WA and ~100 confirmed EA (e.g. from known WA newspapers vs. Azatutyun / Armenian Wikipedia). Run `compute_wa_score` on each and compute precision/recall/F1 and optimal threshold.
- This will reveal whether threshold=5.0 is well-calibrated, which marker families drive false positives/negatives, and whether the cap-at-10 per marker is appropriate.
- **Output:** A notebook or script in `notebooks/` + summary in `docs/development/`.
- **Priority:** Medium — affects audit reliability for the entire training pipeline.

---

## Grammar / dialect

- Quantitative grammar-distance metrics (inflectional profiles, analytic/synthetic load, paradigm consistency, Composite GrammarDistanceIndex).
- Evaluation and integration into clustering; fine-grained dialect subcategories + DBSCAN; feature engineering; backfill `dialect_subcategory`.

## Grammar logic scripts

- Extend inflectional and morphological rules in `linguistics/morphology`.
- Improve paradigm consistency checks and analytic/synthetic load metrics.
- Add validation and test coverage for grammar rules.
- Document rule gaps and edge cases in `docs/phonetics_rule_gaps.md`.

---

## New sources

- **Book/manuscript catalog integration:** Use catalogs + ook_inventory (see docs/MONGODB_CORPUS_SCHEMA.md and integrations/database/corpus_schema.py) to seed and refine queries for rchive_org, loc, hathitrust; e.g. use inventory titles/authors/years to build targeted search terms, avoid duplicate pulls, and prioritize high-value WA/rare items.
- **Gallica, DPLA, Gomidas:** Implemented. See `docs/DATA_SOURCES_API_REFERENCE.md`.
- **Hamazkayin / Pakine:** ✅ Implemented. `ingestion/acquisition/hamazkayin.py` scrapes pakine.net (literary magazine — prose, poetry, criticism, translations) and hamazkayin.com (cultural news). WordPress REST API preferred, HTML fallback. Registered in runner.py; config under `scraping.hamazkayin`.
- **Mechitarist (Venice), AGBU Nubar (Paris):** Stub scrapers in `scraping/mechitarist.py` and `scraping/agbu.py`; no public API—partnership or bulk export required. Permission templates: `docs/MECHITARIST_PERMISSION_REQUEST.md`, `docs/AGBU_NUBARIAN_LIBRARY_PARTNERSHIP.md`. When access is granted, set `catalog_path` or `api_base` + `api_key` and implement catalog loader in the stub.
- **Haigazian University (Beirut):** WA academic institution; library holds periodicals, dissertations, WA-language publications. Contact for digital access or research partnership.
- **Zoryan Institute:** Oral history transcripts, genocide testimonies, scholarly publications with significant WA content. Contact for research data partnership.
- **NAASR (Belmont, MA):** National Association for Armenian Studies & Research; publishes Journal of Armenian Studies, maintains archives. Survey publications and contact for bulk access.
- **Armenian Film Foundation:** Documentary subtitle/transcript archives, narrations in WA. Contact for text access to subtitle files and transcripts.
- **ARS / Hamazkayin cultural archives:** Organizational archives — internal publications, meeting minutes, cultural event programs. Contact chapters for digitized materials.

### Data sources expansion — tracking table

Planned data-expansion projects for the Western Armenian corpus. Full detail: **`docs/development/DATA_SOURCES_EXPANSION.md`** and **`docs/development/requests_guides/`**.

| Project | Status | Notes |
|--------|--------|--------|
| **Gallica (BNF)** | ✅ Implemented | SRU API; `scraping/gallica.py` |
| **Gomidas Institute** | ✅ Implemented | Newspapers; `scraping/gomidas.py`; bulk permission draft in `docs/development/requests_guides/GOMIDAS_BULK_PERMISSION.md` |
| **British Library EAP** | ⏳ Planned | EAP613 (113 newspapers), EAP180 (*Nor dar*); IIIF access at eap.bl.uk; reuse may require custodian permission; IIIF/download tools available |
| **Clark University — Guerguerian Archive** | ⏳ Planned | Armenian *Takvim-i Vekayi*, 1919 tribunal minutes; indexed digitized materials; contact for access |
| **National Library of Armenia (NLA)** | ⏳ Permission / contact | 6M+ digitized pages, DSpace, Union Catalog; no public API; do not scrape; contact for bulk/research (+37460 623513) |
| **Nayiri / COWA** | ⏳ Planned | Western Armenian corpus (beta), nayiri.com/text-corpus; check terms for bulk or API |
| **EANC** | ⏳ Optional | Eastern Armenian; for comparison/dialect filtering only, not primary WA source |
| **Matenadaran (Yerevan)** | ⏳ Permission | Manuscripts; some digitized as images; permission/partnership typically required |
| **Armenian Museum of America** | ⏳ Planned | Scanned documents; contact for access |
| **Mekhitarist Vienna branch** | ⏳ Planned | Additional to Venice; permission required |
| **St. James Armenian Monastery (Jerusalem)** | ⏳ Planned | Manuscripts; permission required |
| **AGBU Nubarian / AGBU archives** | ⏳ Partnership | Periodicals, 1,400 collections; draft email in `docs/development/requests_guides/AGBU_NUBARIAN_LIBRARY_PARTNERSHIP.md` |
| **Zohrab Center (NYC)** | ⏳ Planned | Ecclesiastical texts, some digitized; contact for access |
| **Calouste Gulbenkian Foundation** | ⏳ Planned | Lisbon, Armenian collection; contact for access |
| **UCLA Armenian Studies** | ⏳ Planned | PDFs, dissertations, periodicals; survey for data access |
| **Columbia Armenian Studies** | ⏳ Planned | Rare books, some digitized; survey for data access |
| **Harvard Widener** | ⏳ Planned | Armenian holdings; HathiTrust overlap—add dedup when integrating |
| **University of Michigan Armenian Studies** | ⏳ Planned | Program + possible digitized holdings; survey |
| **NAASR (Belmont, MA)** | ⏳ Planned | National Association for Armenian Studies & Research; publications, periodical archives, some digitized; survey and contact for bulk or research partnership |
| **Haigazian University (Beirut)** | ⏳ Planned | Library & archives; WA academic publications, periodicals, student theses; contact for digital access or partnership |
| **Zoryan Institute** | ⏳ Planned | Oral history transcripts, genocide testimonies, scholarly publications; significant WA content; contact for research partnership |
| **Armenian Film Foundation** | ⏳ Planned | Subtitle/transcript archives; documentary narrations in WA; contact for text access to subtitle files |
| **ARS / Hamazkayin cultural archives** | ⏳ Planned | Armenian Relief Society + Hamazkayin organizational archives; internal publications, meeting minutes, cultural event programs; contact for digital access |
| **Armenian studies programs worldwide** | ⏳ Survey | Sorbonne, Oxford, etc.; survey for data sources |
| **Europeana** | ⏳ Planned | EU aggregator, Armenian filter, mixed formats; API available |
| **DPLA** | ✅ Implemented | US aggregator, api.dp.la/v2/items; API key in config; `scraping/dpla.py` |
| **WorldCat** | ⏳ Planned | `worldcat_searcher.py` exists; wire to drive LOC/IA/Hathi lookups + dedup |
| **Österreichische Nationalbibliothek** | ⏳ Planned | Austrian National Library, Armenian manuscripts |
| **Bayerische Staatsbibliothek** | ⏳ Planned | Munich, Oriental collections |
| **Leiden University Library** | ⏳ Planned | Armenian studies collection |
| **UK Centre for Western Armenian Studies (CFWAS)** | ⏳ Contact | Memory Documentation Project (interviews/transcriptions); contact for research access to transcripts; no scrape without permission |

---

## Session carry-forward

- Populate EA subcategory dirs, metadata backfill, clustering evaluation, improve fallback crawl depth.

---

## English ↔ Western Armenian translation (high priority)

**Rationale:** (1) **Back-translation pipeline** — WA → English → WA for diverse synthetic training data. (2) **Instruction tuning** — Include Western Armenian in instructions/responses for better WA instruction-following.

**Instruction language:** For instruction tuning, include WA in the mix: translate English templates to WA, generate WA instructions via LLM, or use English instructions + WA responses.

### Strategy comparison


| Strategy                                                  | Pros                                       | Cons                                                        |
| --------------------------------------------------------- | ------------------------------------------ | ----------------------------------------------------------- |
| **1. Use existing OPUS/MarianMT (hy↔en)**                 | Fast; Helsinki-NLP `opus-mt-hy-en`.        | “hy” typically Eastern; WA differs; en→hy not single model. |
| **2. Fine-tune MarianMT on WA–English**                   | Focused NMT; ~50k+ pairs.                  | Need parallel data; GPU; separate NMT stack.                |
| **3. Fine-tune LLM for translation**                      | One model for en↔WA.                       | Overfitting risk; compute; data mix.                        |
| **4. NMT back-translation + LLM instruction translation** | Clear separation.                          | Two systems to maintain.                                    |
| **5. Extend SIGUL 2024 WA–English NMT**                   | First open WA–English corpus (~52k pairs). | Model may not be public; BLEU modest.                       |


### Feasibility

- **Data:** WA–English parallel is low-resource; SIGUL 2024 ~52k open pairs; transfer from EA helps but does not replace WA-specific data.
- **Back-translation:** Feasible with any en↔WA system; recommend filtering (human or metric).
- **Instruction tuning:** Feasible; even small WA instruction data helps.

### Recommended direction

- **Short term:** Use hy↔en (e.g. opus-mt-hy-en) for WA→en; add en→hy for first-pass en→WA; back-translate with provenance and filtering.
- **Medium term:** Obtain or reproduce SIGUL 2024 WA–English data/model; fine-tune NMT for WA↔en; use for back-translation and instruction-template translation.
- **Instruction tuning:** Include WA instructions (translated templates or LLM-generated) and WA responses.

### Parallel data from bilingual news sources

Several news sites (Horizon Weekly, Agos, Civilnet, Hetq, Armenpress) publish both Armenian and English versions of articles. The news scraper currently targets Armenian-language URLs. Once the Armenian corpus is populated, re-scrape the English versions of these sites and align articles by URL slug or publication date to build WA–EN / EA–EN parallel corpora. This is a low-cost source of aligned translation pairs for the translation development project.

---

## Western Armenian pedagogical curriculum (new source — high priority)

**Rationale:** WA diaspora school curricula contain grammar lessons, reading texts, graded exercises, short stories, and exam materials written specifically for WA learners. This is **clean, pedagogical Western Armenian prose** — structured, graded by level, and covers core grammar explicitly. No existing pipeline source provides this; it fills a unique gap between literary/news text and conversational data.

### Content types to acquire

| Type | Format | Ingestion approach |
|------|--------|--------------------|
| Grammar lessons / textbooks | PDF, scanned images | OCR pipeline (`ocr/`) → MongoDB |
| Reading texts / stories | PDF, HTML | Scrape or OCR; text extraction |
| Exercises / worksheets | PDF | OCR; structure detection (Q&A pairs) |
| Audio recordings (readings, pronunciation) | MP3, WAV | Download + metadata; future ASR/TTS |
| Video lessons | MP4, YouTube | Download metadata + subtitles; transcript extraction |
| Exam materials | PDF | OCR; extract Q&A format for instruction tuning |

### Candidate sources (to investigate)

- **ARS (Armenian Relief Society)** — WA curriculum used in Armenian day schools across the diaspora
- **AGBU (Armenian General Benevolent Union)** — Virtual Academy online WA courses, learning apps
- **Hamazkayin educational wing** — School textbooks and cultural education materials
- **Zartonk Media / Zulal** — Modern WA learning materials
- **UCLA / Columbia / INALCO** — University-level WA course materials (textbooks, readings)
- **Calouste Gulbenkian Foundation** — Published WA textbooks and grammar books
- **Haigazian University (Beirut)** — WA educational publications
- **Armenian Virtual College (AVC)** — Online WA courses with structured curricula

### Implementation plan

1. **Inventory**: Catalog all known WA curricula and educational publishers; record URLs, access method, licensing
2. **Web scrape**: For sites with online content (AVC, AGBU virtual, etc.) — build dedicated scrapers
3. **PDF download + OCR**: For textbooks/worksheets — download PDFs, run through `ocr/` pipeline
4. **Audio/video**: Download media files + transcripts/subtitles; store metadata for future ASR/TTS work
5. **Structure extraction**: Parse exercises into Q&A pairs for instruction-tuning data
6. **Metadata**: Tag each document with level (beginner/intermediate/advanced), content type, source curriculum

### Why this matters for the LLM

- **Grammar grounding**: Explicit grammar rules in training data help the model learn WA structure
- **Graded complexity**: Beginner→advanced progression provides natural curriculum for the model
- **Exercise format**: Q&A pairs from exercises are directly usable for instruction tuning
- **Pedagogical register**: Clean, formal WA prose complements news/literary/web text
- **Audio/video**: Future multimodal or TTS/ASR training data

---

