# Current Working Backlog (armenian-corpus-core)

This is the single current working backlog for the repository and should be kept short and actionable.

## Phase 2 priority tasks

1. Hybrid profile for `frequency_aggregator` and corpus harmonization.
2. Incremental merge stage in ingestion pipeline.
3. Export formats for frequency data (parquet and HuggingFace datasets).
4. Comprehensive test suite for pipeline and language branch filtering.
5. Docs cleanup (README phase status, one canonical quick start, backlog summarization).

## Ongoing support tasks

- Drift detection via ingestion metrics.
- Loanword tracker + etymology DB integration.
- Source coverage and pipeline observability dashboard.

## Ownership

- `hytools/ingestion/aggregation` and `hytools/ingestion/runner`: implementation.
- `docs/development/CURRENT_BACKLOG.md`: backlog tracking.
- `tests/`: validation and guardrails.
