# Armenian-Corpus-Core — Development Plan Audit

**Audit date:** 2026-03-08  
**Scope:** Project goals, roadmap phases, current implementation state, gaps, and recommended next steps.

---

## 1. Project Goals (Canonical)

From README, INDEX, and FUTURE_IMPROVEMENTS:

| Goal | Source |
|------|--------|
| **Single source of truth** for core contracts, extraction pipeline, normalization | README |
| **Scrape Western (and Eastern) Armenian text** from the internet → MongoDB | README |
| **Extraction pipeline:** Import Anki → Validate → Detect near-duplicates → Materialize dialect views → Build frequency list → Summarize corpus | README |
| **All stages read/write MongoDB** — no intermediate CSV/JSONL for pipeline data | README, FUTURE_IMPROVEMENTS |
| **Support WesternArmenianLLM** — training data consumed from MongoDB | README, MOVED_FROM_WA_LLM |
| **Linguistics & dialect:** WA/EA classification, phonetics, loanword tracking, possible loanwords (dictionary-backed), dialect distance, validation | FUTURE_IMPROVEMENTS, LOANWORD_TRACKING_ANALYSIS |
| **Per-document metrics on ingest** (TextMetricCard, loanwords, possible_loanwords) when config enabled | FUTURE_IMPROVEMENTS (implemented) |
| **CI/CD:** Automated scraping on schedule + manual dispatch; artifacts to MongoDB / GitHub | .github/workflows, ARMENIAN_CORPUS_CORE_AUDIT_REPORT |
| **Research & augmentation:** Book inventory, author research, coverage, augmentation runner, metrics, drift detection | MOVED_FROM_WA_LLM, FUTURE_IMPROVEMENTS |

---

## 2. Roadmap vs. Current State

### Phase 1 (Foundation) — README “Current - Batch 7”

| Item | Status | Notes |
|------|--------|------|
| Package scaffolding (pyproject.toml, setuptools) | ✅ Done | Flat packages: scraping, cleaning, core_contracts, linguistics, ocr, research, augmentation, integrations |
| Extraction tool registry | ✅ Done | `scraping/registry.py` with ExtractionToolSpec; used by tests/docs; runner uses `_build_stages()` directly |
| CI/CD workflow | ✅ Done | `.github/workflows/scraping.yml` — weekly/daily/manual; MongoDB service; runner |
| Pipeline orchestration | ✅ Done | `scraping/runner.py` — run/status/list, --only/--skip/--group, background mode |
| Move core contracts to central package | ✅ Done | `core_contracts/` (types, hashing); used by scraping/mappers, data_sources, tests |

**Phase 1 verdict:** Complete. README can be updated to mark “Move core contracts” as done.

---

### Phase 2 (Enhancement) — README

| Item | Status | Notes |
|------|--------|------|
| Implement `hybrid` profile for statistical conflict resolution | ✅ Done | `frequency_aggregator.py` supports `hybrid_profile` config; tested in `test_frequency_aggregator.py::test_hybrid_profile_affects_weights` |
| Incremental merge (only re-process changed records) | ✅ Done | `incremental_merge.py` stage with delta + bootstrap modes; 4 tests covering add/update/delete/scope-change |
| Format exporters (parquet, HuggingFace datasets) | ✅ Done | `corpus_export.py` exports Parquet, HF datasets, and deterministic release splits; tested in `test_doctor_and_corpus_export.py` |
| Comprehensive test suite | ✅ Done | 57+ test files; CI workflow `.github/workflows/ci.yml` runs `pytest tests/ -v` on push/PR across Python 3.10–3.12 |

**Phase 2 verdict:** Core items implemented. Remaining work is integration-test proof and operational rollout; see `docs/development/FEATURE_COMPLETENESS_CHECKLIST.md`.

---

### Phase 3 (Distribution) — README

| Item | Status | Notes |
|------|--------|------|
| Publish to PyPI / internal package repo | ❌ Not started | |
| Documentation site | ❌ Not started | Wiki URL in pyproject; no generated docs |
| Performance benchmarks | ❌ Not started | |

**Phase 3 verdict:** Not started; appropriate for later.

---

## 3. Implementation Summary by Area

### 3.1 Scraping & Data Acquisition

| Component | Status | Notes |
|-----------|--------|-------|
| wikipedia_wa, wikipedia_ea, wikisource | ✅ | In runner; MongoDB-supported |
| archive_org, hathitrust, gallica, loc | ✅ | LOC has status command; HathiTrust 403 without research access |
| newspaper, ea_news, rss_news | ✅ | EA news fallbacks and tests in place |
| culturax, english_sources | ✅ | |
| nayiri, gomidas, mss_nkr, ocr_ingest | ✅ | |
| worldcat_searcher | ✅ | main() only; in runner |
| cleaning (run_mongodb) | ✅ | Stage in runner |
| metadata_tagger, frequency_aggregator | ✅ | |
| export_corpus_overlap_fingerprints | ✅ | main(); in runner |
| import_anki_to_mongodb | ✅ | main(); extraction group |
| validate_contract_alignment | ✅ | run() + main(); extraction |
| materialize_dialect_views | ✅ | run(); extraction |
| summarize_unified_documents | ✅ | run(); extraction |

All extraction stages in README exist and are registered in `runner._build_stages()`.

### 3.2 Core Contracts & Extraction

| Component | Status | Notes |
|-----------|--------|------|
| core_contracts.types | ✅ | DocumentRecord, LexiconEntry, PhoneticResult, DialectTag |
| core_contracts.hashing | ✅ | normalize_text_for_hash, sha256_normalized |
| scraping.registry | ✅ | Tool specs for extraction tools; not used by runner for execution |
| scraping.mappers, data_sources | ✅ | Use core_contracts |

### 3.3 Linguistics & Dialect

| Component | Status | Notes |
|-----------|--------|------|
| WA/EA classifier (compute_wa_score, dialect_classifier) | ✅ | _helpers + linguistics.dialect_classifier; EA indefinite article, egg/vocab |
| Phonetics (IPA, difficulty) | ✅ | linguistics.phonetics |
| Loanword tracker (known + possible) | ✅ | linguistics.loanword_tracker; ingestion metadata when metrics on |
| Dialect distance, dialect_pair_metrics, clustering | ✅ | |
| Text metrics (quantitative linguistics) | ✅ | Lexical, syntactic, morphological, orthographic, etc. |
| Validation (augmentation output, classical spelling) | ✅ | linguistics.metrics.validation |
| Classical Armenian (hyc) | ❌ | In FUTURE_IMPROVEMENTS |
| Nayiri-backed possible_loanwords | 🟡 | Placeholder is_known_word; wire to Nayiri when available |

### 3.4 Ingest & Metrics

| Component | Status | Notes |
|-----------|--------|------|
| insert_or_skip + document_metrics | ✅ | TextMetricCard + loanwords + possible_loanwords when compute_metrics_on_ingest |
| run_ingestion (JSONL → MongoDB) | ❌ Removed | Removed; uses local JSONL and is no longer supported |
| Drift detection on ingest | ❌ | FUTURE_IMPROVEMENTS — pending baseline + ingest hook |
| Metrics pipeline (augmentation) | ✅ | MongoDB-only; augmentation_metrics |

### 3.5 OCR, Research, Augmentation

| Component | Status | Notes |
|-----------|--------|------|
| OCR pipeline (Tesseract, preprocessor, cursive) | ✅ | ocr/pipeline, preprocessor, tesseract_config |
| Research (author, biography, coverage, book inventory) | ✅ | ingestion/ (discovery, enrichment, aggregation, research_runner); book inventory MongoDB when configured |
| Augmentation runner, strategies, safe_generation, metrics_pipeline | ✅ | |
| Drift detection (module) | ✅ | augmentation.drift_detection; not wired to ingest |
| Metrics visualization | ✅ | Optional; FUTURE_IMPROVEMENTS notes legend/empty-slice warnings |

### 3.6 CI/CD & Docs

| Component | Status | Notes |
|-----------|--------|------|
| GitHub Actions scraping workflow | ✅ | Scheduled + manual; MongoDB; artifacts |
| Test workflow (pytest on push/PR) | ✅ | `.github/workflows/ci.yml` — push/PR on main; Python 3.10–3.12 matrix |
| docs/ (INDEX, STRUCTURE, FUTURE_IMPROVEMENTS, etc.) | ✅ | Large doc set; STRUCTURE describes subpackages that don’t exist (scraping is flat) |

---

## 4. Gaps and Inconsistencies



1. **README roadmap**  
   - Phase 1 and Phase 2 markers were stale. → **Fixed April 2026.**

2. **docs/STRUCTURE.md**  
   - Describes scraping subpackages (wikimedia/, digital_libraries/, news/, etc.). Actual layout is flat (`scraping/*.py`). Either refactor into subpackages or update STRUCTURE to match reality.

3. ~~**Tests not in CI**~~ → **Resolved.** `.github/workflows/ci.yml` now runs `pytest tests/ -v` on push/PR.

4. **Runner vs. registry**  
   - Runner builds stages in code (`_build_stages()`); registry holds tool metadata but is not used for execution. Document that registry is for discovery/metadata only.

5. **MOVED_FROM_WA_LLM**  
   - Refers to `armenian_corpus_core/`; real packages are under `hytools/`. Update doc to match pyproject layout.

6. ~~**Optional Phase 2 items**~~ → **Resolved.** Hybrid profile, incremental merge, and format exporters are implemented and tested.


---

## 5. What Needs to Be Done (Prioritized)

### High priority (align with stated goals)


1. ~~**Update README**~~ → **Done April 2026.** Phase markers updated.

2. ~~**Add test workflow**~~ → **Done.** `.github/workflows/ci.yml` runs pytest on push/PR.

3. **Align docs with code**  
   - Update STRUCTURE.md to describe the flat scraping layout (or plan a subpackage refactor).  
   - Update MOVED_FROM_WA_LLM to use actual package names.

### Medium priority (roadmap and maintainability)

4. ~~**Phase 2 — Incremental merge**~~ → **Done.** `incremental_merge.py` with delta + bootstrap; tested.

5. ~~**Phase 2 — Format exporters**~~ → **Done.** `corpus_export.py` with Parquet, HF, and release split support.

6. **Drift detection on ingest / pipeline monitoring**  
   - Baseline comparison and persisted drift alerts now exist in `ingestion/aggregation/drift_detection.py`; remaining work is deeper ingest-time hooks if per-document drift screening becomes necessary.

### Lower priority (from FUTURE_IMPROVEMENTS)

7. **Classical Armenian (hyc)**  
   - Extend dialect classifier and materialize_dialect_views.

8. **Word frequencies with metadata facets**  
   - Schema and aggregation for author/region/time/sub-dialect.

9. **Target-weighted frequency aggregation**  
   - Config and logic for target source-type mix.

10. **LOC / HathiTrust / research pipeline**  
    - Adaptive rate limiting, HathiTrust bulk/API, research pipeline hardening (per FUTURE_IMPROVEMENTS).

11. **Loanword & etymology**  
    - Nayiri-backed possible_loanwords; file-based loanword catalog; transliteration and IPA (all in FUTURE_IMPROVEMENTS).

---

## 6. Summary Table

| Area | Done | In progress | Not started |
|------|------|-------------|-------------|
| Phase 1 (foundation) | 5/5 | 0 | 0 |
| Phase 2 (enhancement) | 4/4 (hybrid, merge, exporters, tests) | Integration proof + CI gates | — |
| Phase 3 (distribution) | 0 | 0 | PyPI, docs site, benchmarks |
| Scraping & extraction | Full pipeline + registry | — | — |
| Core contracts | types, hashing, usage | — | — |
| Linguistics & dialect | WA/EA, loanwords, possible_loanwords, metrics | Nayiri for possible_loanwords | Classical (hyc) |
| Ingest & metrics | document_metrics, loanwords, possible_loanwords | — | Drift on ingest |
| CI/CD | Scraping workflow + test workflow | — | — |

**Bottom line (updated April 2026):** Phases 1 and 2 are implemented. The main remaining gaps are: (1) integration-test proof for incremental merge and deterministic export, (2) unified review layer operationalization, (3) catalog-driven acquisition loop, and (4) drift detection wiring. See `docs/development/FEATURE_COMPLETENESS_CHECKLIST.md` for the concrete exit-criteria checklist.
