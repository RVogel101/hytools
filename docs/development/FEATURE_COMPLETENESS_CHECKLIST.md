# Feature-Completeness Checklist

Concrete exit criteria for declaring the hytools corpus pipeline **feature-complete**.  
Each gate has a testable pass/fail condition. Mark `[x]` only when the exit criterion is met.

Last updated: April 2026

---

## Gate 1 — Config & Runner Operational Rollout

> **Goal:** A single `python -m hytools.ingestion.runner run --config config/settings.yaml` works end-to-end with no manual fixups.

- [x] `python -m hytools.ingestion.runner doctor --config config/settings.yaml` reports **zero errors**.
- [x] DPLA stage is explicitly `enabled: false` in config (or a real API key is supplied and the stage succeeds).
- [x] All post-processing stages (`metadata_tagger`, `frequency_aggregator`, `incremental_merge`, `word_frequency_facets`, `drift_detection`, `corpus_export`) have explicit `enabled: true/false` in `config/settings.yaml` — no implicit transition defaults.
- [x] `python -m hytools.ingestion.runner list --config config/settings.yaml` reports the configured stage plan and matches the canonical runner registry.

**Exit criterion:** `doctor` clean + one successful full-pipeline dry-run.

---

## Gate 2 — Aggregation Hardening (Phase 2)

> **Goal:** Frequency pipeline is provably incremental, deterministic, and CI-covered.

- [x] `frequency_aggregator` full rebuild produces correct weighted counts (test: `test_hybrid_profile_affects_weights`).
- [x] `incremental_merge` applies new-document deltas without double-counting (test: `test_incremental_merge_updates_changed_documents_without_double_counting`).
- [x] `incremental_merge` replaces a document's contribution when its text changes (test: `test_incremental_merge_replaces_existing_document_contribution`).
- [x] `incremental_merge` reconciles deleted documents (test: `test_incremental_merge_reconciles_deleted_documents`).
- [x] `incremental_merge` reconciles documents that leave branch scope (test: `test_incremental_merge_reconciles_documents_that_leave_branch_scope`).
- [x] `hybrid_profile` mode applies WA-score weighting and records metadata (test: `test_hybrid_profile_affects_weights`).
- [x] `corpus_export` produces deterministic Parquet and release splits with stable sort and seed-based bucketing (test: `test_deterministic_release_splits`).
- [x] An integration test proves a full rebuild → delta ingest → re-run cycle is idempotent on the same data (`tests/test_integration_aggregation.py`).
- [x] CI workflow runs `pytest tests/` on push/PR (`ci.yml` — test job).

**Exit criterion:** All items checked; CI green on main.

---

## Gate 3 — Unified Review & Audit Layer

> **Goal:** All low-confidence or policy-rejected items land in one queryable review queue.

- [x] `review_queue.py` schema supports OCR and non-OCR items (fields: `queue_source`, `stage`, `reason`, `priority`).
- [x] `maybe_enqueue_language_review()` routes borderline dialect classifications to the queue.
- [x] `should_enqueue_low_confidence_classification()` detects ambiguous WA/EA results.
- [x] At least 3 ingestion stages (metadata_tagger, web_crawler, news) call `maybe_enqueue_language_review` or `enqueue_for_review` on applicable items.
- [x] A CLI or script can list / triage items in the review queue (`python -m hytools.ingestion.review list`, `mark-reviewed`).
- [x] Dialect/lexical heuristics that currently live only in code are documented in a persistent data file (YAML or JSON) referenced by the classifier.

**Exit criterion:** Review queue populated by real pipeline stages; triage command works.

---

## Gate 4 — Research Pipeline Validated

> **Goal:** Author extraction → enrichment → timeline → coverage runs cleanly on the full corpus and produces actionable outputs.

- [x] `research_runner` orchestrates all four phases with configurable skipping.
- [x] `author_extraction` extracts names via NER and regex patterns.
- [x] Tests pass for `research_runner` CLI overrides and argument parsing.
- [x] `author_extraction` has uniform `try/except` around all regex group accesses (no hard failures on variant metadata).
- [x] A full research-pipeline run completes against the live corpus and persists non-empty MongoDB outputs for profiles, timeline, period analysis, generation report, coverage gaps, and acquisition priorities.
- [x] Research outputs are referenced in at least one downstream step (coverage and acquisition summaries are surfaced by `runner dashboard`).
- [x] Operator surfaces expose itemized acquisition / coverage / review browsing via the linked dashboard detail page.

**Exit criterion:** Clean run on full corpus; MongoDB outputs are non-empty and dashboard surfaces render actionable summaries.

---

## Gate 5 — Catalog-Driven Acquisition & Dedup

> **Goal:** Book inventory and author metadata drive targeted queries and prevent duplicate ingestion.

- [x] `book_inventory.py` data model and inventory manager implemented.
- [x] `worldcat_searcher.py` search + fallback list implemented.
- [ ] WorldCat module updated for API 2.0 or explicitly documented as fallback-only (API 1.0 EOL 2024-12-31).
- [ ] `book_inventory_runner` can ingest LOC / Archive.org / Hathi catalog results and merge them into the inventory.
- [x] A dedup check compares `content_hash` of new acquisitions against existing corpus documents before insert.
- [x] Coverage dashboard shows % of inventory items present in corpus.
- [x] Coverage/acquisition rows carry source-target hints so the dashboard can drive the next catalog backfill cycle.

**Exit criterion:** At least one catalog-driven acquisition cycle completed; dedup prevented at least one duplicate.

---

## Gate 6 — Export & Release Determinism

> **Goal:** `runner release` produces byte-identical outputs given the same corpus state.

- [x] `corpus_export.py` sorts rows by content hash and uses seed-based split bucketing.
- [x] Release includes manifest, checksum, and dataset card.
- [x] An integration test exports the same synthetic corpus twice and asserts byte-identical Parquet output (`tests/test_integration_aggregation.py`).
- [x] CI runs the deterministic export test.

**Exit criterion:** Deterministic export test green in CI.

---

## Gate 7 — CI / Automated Quality Gates

> **Goal:** Every push to `main` runs the full test suite; failures block merge.

- [x] `.github/workflows/ci.yml` exists with `pytest tests/ -v` on push/PR.
- [x] CI matrix covers Python 3.10, 3.11, 3.12.
- [x] CI includes the integration tests from Gates 2 and 6.
- [x] CI fails if any test fails (no `continue-on-error` on `test` job).

**Exit criterion:** CI green for 3 consecutive pushes to main.

---

## Gate 8 — Doc Accuracy

> **Goal:** Roadmap docs match the codebase — no stale "not started" claims for implemented features.

- [x] `docs/audit_reports/DEVELOPMENT_PLAN_AUDIT.md` Phase 2 section reflects that hybrid profile, incremental merge, and format exporters are implemented.
- [x] `docs/development/PHASE2_CHECKLIST.md` items 1–3 are marked done or updated with current status.
- [x] `README.md` Phase 2 roadmap section shows implemented items as ✅.
- [x] `docs/development/FUTURE_IMPROVEMENTS.md` summary table is consistent with `CURRENT_BACKLOG.md`.

**Exit criterion:** A grep for "Not started" in the items listed above returns zero false positives.

---

## Sequencing (recommended order)

1. Gate 1 (config rollout) — unblocks all runner-based work
2. Gate 8 (doc accuracy) — prevents mis-prioritization
3. Gate 7 (CI gates) — catches regressions early
4. Gate 2 (aggregation hardening) — integration tests close the proof gap
5. Gate 6 (export determinism) — release safety net
6. Gate 4 (research validation) — hardening before expansion
7. Gate 3 (review layer) — operational review workflow
8. Gate 5 (catalog acquisition) — targeted source expansion

---

## Post-feature-complete (expansion phase)

These are **not** gates but the next priorities once all gates above are green:

- Western Armenian pedagogical materials (new corpus family)
- English ↔ Western Armenian translation pipeline
- Advanced linguistic analysis and dialect calibration
- Western Armenian audio / TTS pilot
- Loanword / etymology pipeline (Wiktextract + Nayiri)
