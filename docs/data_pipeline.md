# hytools Data Pipeline (Mongo → clean + dedupe)

## Goal
Provide a single, canonical pipeline for extracting and preparing Armenian text data so that all downstream consumers (including `WesternArmenianLLM`) can rely on high-quality preprocessed data.

## Source filter
Start from MongoDB documents with a strict language tag filter:
- `internal_language_tag == "hye-w"` (Western Armenian)

## Pipeline stages
1. **Mongo extract**: query source collections for the desired records, include metadata fields (source, date, doc_id).
2. **Language tagging**: run `hytools.linguistics.language_tagging.classify_text_to_internal_tags` or equivalent.
3. **Content filtering**:
   - remove non-Armenian or irrelevant documents
   - drop documents failing `internal_language_tag` checks
   - apply quote/metadata stripping and text normalization
4. **Deduplication**:
   - normalize text for dedupe key
   - compare by hash, source+date, and exact text match
   - de-duplicate across chronological and source-redundant content
5. **Eastern audit (optional)**:
   - perform specialized checks for Eastern Armenian contamination
   - mark suspicious documents for manual review
6. **Output**:
   - structured clean dataset (e.g., `jsonl` with stable IDs)
   - metrics/report (count before/after, dupes removed, filtered by language)

## Consumer requirement
Data consumer pipelines (e.g., WesternArmenianLLM) should expect prefiltered `hye-w` corpus and should not re-run the same logic themselves in general.

## Data provenance and metadata
Cleaned pipeline output documents must include:
- `metadata.source_pipeline_version` (e.g. `1.0`)
- `metadata.language_tagging_version` (e.g. `v1`)
- `metadata.dedupe_hash` (normalized-text SHA256 key)
- `metadata.normalized_content_hash` (for generation consistency)

Any downstream code using this dataset should keep these fields and propagate them through training artifacts.

