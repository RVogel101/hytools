# Nayiri Testing / Mocking Audit

Generated: 2026-03-24

Summary
- Purpose: enumerate tests that use mocking, in-memory ZIP/JSON data, or tmp_path fixtures relevant to Nayiri and acquisition tooling.
- Action: review the listed tests when you decide whether to keep mocks, replace them with integration tests, or point them at stable test fixtures.

Files identified (high-level)

- tests/test_nayiri_parsing.py
  - Uses parsing helpers and previously built in-memory ZIP bytes via `io.BytesIO` / `zipfile.ZipFile` and a `DummyResp`. Current tests were updated to call `parse_lexicon_data` and `parse_corpus_member` directly (no network, no ZIP files).
  - Recommendation: keep helper-based tests for fast unit coverage; add a small integration test that runs against a test MongoDB if/when you want to verify end-to-end.
- tests/test_nayiri_integration.py
  - New integration test uses mocked `requests.get` and in-memory zip archives for `import_lexicon_from_url` and `import_corpus_from_url`, with fake MongoDB collection objects.
  - This validates the current non-scraping Nayiri pipeline and adds coverage for config-driven ingestion.

- tests/test_author_research.py
  - Mocks `hytools.ingestion._shared.helpers.open_mongodb_client` via `patch(...)` to avoid hitting a real MongoDB instance.
  - Recommendation: either keep the mock for unit tests or provide a test MongoDB URI in CI for integration runs.

- tests/test_digital_library_scrapers.py
  - Multiple `@patch(...)` usages mocking `requests.get`, `requests.Session`, and acquisition helper functions (archive_org, gallica, hathitrust, gomidas). These tests intentionally isolate network I/O.
  - Recommendation: leave as-is for unit tests; add separate integration recipes if you want to exercise real downloads (respecting target site policies).

- tests/test_frequency_aggregator.py
  - Uses `monkeypatch.setattr(...)` to replace internal helpers/clients for deterministic behavior.
  - Recommendation: maintain for unit coverage.

- tests/test_dialect_pair_metrics.py, tests/test_variant_pairs_helper.py
  - Use `tmp_path` to create disk-backed temporary files (JSON/JSONL) for tests.
  - Recommendation: disk-backed tmp files are fine and allowed per your rule (they are not permanent sample files). Keep or convert to fixtures as needed.

Notes & next steps
- I scanned the `tests/` folder for patterns: `monkeypatch`, `patch(`, `requests.get`, `io.BytesIO`, `zipfile.ZipFile`, `writestr(`, `DummyResp`, and `tmp_path`.
- If you want a stricter policy, I can produce a per-file snippet report (exact lines and surrounding context) to help you audit each mock usage.

Suggested triage options
- Keep unit tests that mock network/DB but add a small separate integration test suite that targets a disposable test MongoDB and recorded sample files (if you later approve sample files).
- Or keep current mocks and rely on `parse_*` helpers (now present in `hytools/ingestion/acquisition/nayiri.py`) to validate parsing logic without network.

---

If you want the detailed per-file snippets exported as CSV or included here, let me know and I will add them.
