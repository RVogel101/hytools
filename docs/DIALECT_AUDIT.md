# Dialect Tagging Audit — Detailed Report

Generated: 2026-03-23

Purpose
-------
This document lists every located occurrence of the substring "dialect" (case-insensitive) across the workspace at the time of the audit, describes where the tag/value originates (assigned/generated vs referenced), and recommends precise in-place actions to remove legacy `dialect` tagging in favor of `internal_language_code` and `internal_language_branch` derived only from author writings.

Note: I did not modify files except for `hytools/hytools/cleaning/author_database.py` where I removed automatic region-based inference and added a comment explaining the new rule (authors remain unclassified unless writing samples exist). That change is noted below.

Executive summary
-----------------
- Found occurrences across code, tests, docs, notebooks and generated results. Examples:
  - Core types/enums: `Dialect`, `DialectTag` (types and exports)
  - Cleaning pipeline: `language_filter.py`, `author_database.py` (inference)
  - Augmentation/linguistics modules: `dialect_distance`, clustering, pair metrics
  - Tests referencing dialect fields and files named with `dialect_*`
  - Notebooks and results containing `metadata.dialect` or `dialect` keys
- Action required (high level):
  1. Replace runtime/metadata assignments of `dialect` with `internal_language_code` and/or `internal_language_branch` derived only from textual evidence.
  2. Deprecate or remove `Dialect` / `DialectTag` types after migrating callers and tests.
  3. Update dashboards/notebooks/results and any downstream queries that reference `metadata.dialect`.
  4. Enforce this policy in materialization and aggregation jobs (see `materialize_dialect_views.py`) so source-provided tags are recorded but not auto-promoted.

Policy statement
----------------
Corpus dialect is derived strictly from text model results (`internal_language_branch`), no source-language fallback for corpus labels. Source-language tags may be stored as separate metadata (e.g. `metadata.source_language_code`) for provenance, but they must not overwrite or substitute text-derived branch tags.

Dialect deprecation pipeline
---------------------------
- Add a CI audit check script to fail when new code writes `metadata.dialect` or imports `DialectTag` directly from `core_contracts`.
- Deprecate `DialectTag` in `core_contracts/__init__.py` (non-exported) and provide migration guidance to use `internal_language_code` and `internal_language_branch`.
- Port `hytools/ingestion/enrichment/materialize_dialect_views.py` to strict branch mapping (already done).
- Update `hytools/ingestion/aggregation/summarize_unified_documents.py` and similar scripts to read `dialect_view` or `internal_language_branch` and not `metadata.dialect`.
- Add docs and audit reminders in `DIALECT_AUDIT.md` and `docs/ARCHITECTURE.md`.

Findings (file-by-file)
-----------------------

Below each entry I list: file path, type (code/test/doc/data/notebook), whether the occurrence is an assignment (produces dialect), a usage/reference, or documentation/example, and recommended inline action.

1) `hytools/hytools/cleaning/author_database.py`
- Type: code (module)
- Occurrences:
  - `class Dialect(Enum)` — defines `WESTERN_ARMENIAN`, `EASTERN_ARMENIAN`, `MIXED`, `UNKNOWN` (types/enum)
  - `infer_dialect_from_region(region:...) -> Dialect` — function that maps GeographicRegion → Dialect (producer)
  - `dialect: Dialect | None = None` field on `AuthorRecord` dataclass (metadata field)
  - Previously: `__post_init__` auto-computed `self.dialect = infer_dialect_from_region(primary_region)` → THIS AUTO-INFERENCE HAS BEEN REMOVED.
- Origin: produced locally by the module via `infer_dialect_from_region` and originally applied at `AuthorRecord.__post_init__`.
- Recommendation:
  - Remove `Dialect` enum or mark deprecated.
  - Stop calling `infer_dialect_from_region` (already removed from __post_init__). Where other modules call it, remove those calls.
  - Add `internal_language_code: str | None` and `internal_language_branch: str | None` fields to `AuthorRecord` if needed; do NOT infer them from geography—populate only from textual analysis modules.

2) `hytools/hytools/cleaning/language_filter.py`
- Type: code
- Occurrences:
  - Docstrings and variables describing `dialect_mismatch`, reading `author_record.dialect`, and comparing to detected text dialect (e.g., `if dialect is not None and is_wa and dialect == Dialect.EASTERN_ARMENIAN:`).
- Role: This module checks for dialect mixing; it reads `author_record.dialect` and compares to the text's detected dialect value.
- Recommendation:
  - Change reads of `author_record.dialect` → read `author_record.internal_language_branch` or `internal_language_code` (depending on your canonical choice).
  - Replace code that compares against `Dialect.EASTERN_ARMENIAN`/`WESTERN_ARMENIAN` with comparisons against branch/code values (e.g., `'hye'` / `'hyw'` or whichever normalized labels you adopt).
  - If the module uses a classifier that returns a text-level label, ensure it returns the new canonical fields and update the comparison logic.

3) `hytools/hytools/core_contracts/types.py` and `hytools/hytools/core_contracts/__init__.py`
- Type: code (types & exports)
- Occurrences:
  - `DialectTag` (type exported)
  - Type docstrings describing dialect classification for text and lexicon records.
- Role: central contract for messages and records — other modules import `DialectTag`.
- Recommendation:
  - Replace `DialectTag` type with a new `LanguageTag` or `InternalLanguageTag` reflecting `internal_language_code`/`internal_language_branch` fields; update import sites.
  - Provide a small compatibility shim for a transitional period (e.g., accept either field and convert) to reduce breakage.

4) `hytools/tests/test_integration.py` and other tests under `hytools/tests/` (e.g., `test_dialect_distance.py`, `test_dialect_pair_metrics.py`, `test_augmentation_validation.py`)
- Type: tests
- Occurrences:
  - Tests import `DialectTag` and construct sample records with `dialect_tag=DialectTag.WESTERN_ARMENIAN` or check `dialect`-named output files.
  - Test file names and saved artifacts have `dialect_*` in them (e.g. `dialect_pair_metrics.jsonl`).
- Role: validate behavior — they will fail until migrations occur.
- Recommendation:
  - Update test fixtures to use `internal_language_code` / `internal_language_branch` instead of `dialect_tag` fields.
  - Rename saved artifact filenames to avoid `dialect_` prefix where appropriate and update tests accordingly.

5) `hytools/README.md` and documentation files (`docs/adapter_layer_plan.md`, `docs/dependency_map.txt`, `docs/concept_guides/AUGMENTATION_FAQ.md`, `docs/armenian_language_guids/ARMENIAN_REGEX_REFERENCE.md`)
- Type: docs
- Occurrences:
  - Multiple references to dialect scoring, dialect purity, dialect benchmark scripts, and mapping by dialect.
- Role: guidance and developer-facing docs.
- Recommendation:
  - Update docs to describe `internal_language_code` and `internal_language_branch` as canonical fields.
  - Replace references to dialect scoring with branches/codes and update CLI examples.

6) `WesternArmenianLLM/examples/metadata_tagging_example.py`
- Type: example code
- Occurrences:
  - Example uses `dialect` in metadata and logger lines such as `logger.info(f"  dialect: {wa_wiki.dialect.value}")` and `generate_dialect_report()`.
- Recommendation:
  - Update example to demonstrate `internal_language_code`/`branch` usage and `generate_language_report()` (new name) that aggregates by code/branch.

7) Generated/result data: `WesternArmenianLLM/results/dialect_subcategory_clusters_smoke.json` and similar result files
- Type: generated data
- Occurrences:
  - Keys like `"dialect": "eastern"` and `"dialect_subcategory": "unknown"`.
- Role: downstream artifacts (reports, analytics, smoke tests)
- Recommendation:
  - Regenerate artifacts after code migration. For now, treat these files as stale and update consumers to read `language_code` / `language_branch` keys instead.

8) Notebooks: `hytools/notebooks/mongodb_eda.ipynb`, `hytools/notebooks/transliteration_demo.ipynb` and others
- Type: notebooks / exploratory analyses
- Occurrences:
  - Visualizations and queries reference `metadata.dialect` and show dialect distributions.
- Role: analysis and dashboards
- Recommendation:
  - Update notebooks to query `metadata.internal_language_code` and `metadata.internal_language_branch` and regenerate visualizations.

9) Linguistics/augmentation modules: `hytools/linguistics/dialect/*`, `augmentation/dialect_*`, `augmentation/benchmark_dialect_distance.py`, `augmentation/calibrate_distance_weights.py`
- Type: code (algorithms and benchmarking)
- Occurrences:
  - Module names and functions reference dialect distance/clustering and produce dialect-specific metrics.
- Role: compute dialect distances and produce metrics used by augmentation.
- Recommendation:
  - Rename modules and refactor outputs to be language-branch aware; replace `dialect` tokens in outputs with canonical codes/branches.
  - If `dialect` appears in public CLI names, provide compatibility flags mapping old names to new names for a transition period.

10) Other places (quick list)
- `hytools/README.md` — references to `dialect_tag` and `Materialize Dialect Views`.
- `hytools/notebooks/mongodb_eda.ipynb` — queries and EDA lines that reference `metadata.dialect` (these are explicit and need to be updated).

Change impact and migration plan (recommended order)
-------------------------------------------------
1. Define canonical fields and types
   - Add `internal_language_code: str | None` and `internal_language_branch: str | None` to central core contract types (e.g., `hytools/hytools/core_contracts/types.py`).
   - Provide clear allowed values (ISO-ish codes or project-specific branch names), document them.

2. Stop production of `dialect`
   - Remove all producers/assignments that create `metadata.dialect` or `author.dialect` (e.g., `infer_dialect_from_region`, materialize views that tag `dialect_view`).
   - I removed the `AuthorRecord.__post_init__` inference in `author_database.py` to prevent geography-based inference.

3. Migrate consumers
   - Update `language_filter.py` and other modules to read the new fields. Avoid any fallback to geography; if no sample exists, treat as unclassified.
   - Update tests, examples, notebooks, and dashboards.

4. Deprecate + remove types
   - Add deprecation warnings for `Dialect` / `DialectTag` exports, provide a conversion shim for a transition (optional).
   - After full migration and CI green, remove the enums and dialect-named artifacts.

5. Regenerate artifacts and run tests
   - Run the test suite, update failing tests, and regenerate any saved JSON results, reports, dashboards, and notebooks.

Risk assessment
---------------
- High risk areas:
  - Tests and CI will break until test fixtures are updated (they currently assert `dialect` fields).
  - Downstream dashboards and notebook analyses that query `metadata.dialect` will show stale or missing data.
- Mitigation:
  - Provide compatibility shims that map `dialect`→`internal_language_branch` where possible during migration.
  - Run the migration in a dedicated branch, update a small set of modules and tests first, then expand.

What I changed already
---------------------
- `hytools/hytools/cleaning/author_database.py`: removed `AuthorRecord.__post_init__` auto-inference of `dialect` from regions and added a comment directing the project to use `internal_language_code` / `internal_language_branch` populated from textual samples only.

Next steps (pick one)
---------------------
- Option A — Full automated replace: I can replace all `dialect` assignments and types across the codebase with the new fields, update import sites, and run tests. (This is invasive; will require iterative fixes.)
- Option B — Phased migration: create compatibility shims, update central types and a small set of critical producers/consumers (e.g., `author_database`, `language_filter`, core contracts), then run tests and expand.
- Option C — Manual review + PR: I produce a patch per file with suggested edits (no automatic run), so you can review each change before applying.

If you want me to continue, tell me which option (A/B/C) and whether to create a migration branch and run the test suite after changes.

Appendix: full file index I scanned
----------------------------------
- hytools/hytools/cleaning/author_database.py — code, producer (was auto-inferring)
- hytools/hytools/cleaning/language_filter.py — code, consumer (reads author.dialect)
- hytools/hytools/core_contracts/types.py — code, type definitions (`Dialect`, `DialectTag`)
- hytools/hytools/core_contracts/__init__.py — exports `DialectTag`
- hytools/README.md — docs referencing `dialect_tag` and materialize views
- hytools/docs/adapter_layer_plan.md — docs referencing dialect distance & scoring
- hytools/docs/dependency_map.txt — dependency references to dialect modules
- hytools/docs/concept_guides/AUGMENTATION_FAQ.md — docs referencing dialect purity
- hytools/docs/armenian_language_guids/ARMENIAN_REGEX_REFERENCE.md — guides referencing dialect-labeled regex
- hytools/tests/test_dialect_distance.py — test file
- hytools/tests/test_dialect_pair_metrics.py — test file
- hytools/tests/test_augmentation_validation.py — test file with dialect specific cases
- hytools/tests/test_integration.py — imports `DialectTag` and uses it in fixtures
- hytools/notebooks/mongodb_eda.ipynb — notebooks querying `metadata.dialect`
- hytools/notebooks/transliteration_demo.ipynb — notebook mentioning Dialect
- WesternArmenianLLM/examples/metadata_tagging_example.py — example using `dialect` metadata
- WesternArmenianLLM/results/dialect_subcategory_clusters_smoke.json — generated results with `dialect` keys

---

If you'd like, I can now begin Option B (phased migration):
1) Add `internal_language_code` and `internal_language_branch` to `hytools/hytools/core_contracts/types.py` with minimal backward-compatible mapping functions.
2) Update `hytools/hytools/cleaning/language_filter.py` to reference the new fields.
3) Update tests in `hytools/tests/` to use the new fields and run the test suite to collect failures.

Tell me which option you prefer and whether to proceed; I will not modify more files until you confirm.