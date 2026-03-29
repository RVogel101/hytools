# Nayiri Pipeline (hytools)

## Overview

`hytools/ingestion/acquisition/nayiri.py` is the sanctioned Nayiri data ingestion module. It no longer scrapes Nayiri site directly; it downloads official release archives and imports lexicon/corpus content into MongoDB.

This doc outlines:
- configuration keys
- process steps
- MongoDB schemas
- dependencies
- audit checks

---

## Configuration (`config/settings.yaml`)

Required keys:
- `cache_dir` (e.g., `cache`)
- `scraping.nayiri.enabled: true`
- `scraping.nayiri.lexicon_url`: URL to Nayiri lexicon ZIP
- `scraping.nayiri.corpus_url`: URL to Nayiri corpus ZIP
- `scraping.nayiri.lexicon_keep_zip`: false (default)
- `scraping.nayiri.corpus_keep_zip`: false (default)

Example:

```yaml
paths:
  cache_dir: "cache"

scraping:
  nayiri:
    enabled: true
    lexicon_url: "https://www.nayiri.com/nayiri-armenian-lexicon-2026-02-15-v1.json.zip"
    corpus_url: "https://www.nayiri.com/nayiri-corpus-of-western-armenian-2026-02-25-v2.zip"
    lexicon_keep_zip: false
    corpus_keep_zip: false
```

---

## Pipeline steps

### 1. `run(config)`
- Reads `scraping.nayiri.mode` (`lexicon` or `corpus`, default `lexicon`).
- Opens MongoDB via `open_mongodb_client(config)`.
- Calls `import_lexicon_from_url` or `import_corpus_from_url`.

### 2. `import_lexicon_from_url(config, client)`
- Downloads zip to `cache_dir/nayiri_lexicon.zip`.
- Finds first JSON inside archive.
- Loads JSON and iterates lexemes / lemmas.
- Inserts into `nayiri_entries` collection.
- Optional filename cleanup based on `lexicon_keep_zip`.

### 3. `import_corpus_from_url(config, client)`
- Downloads zip to `cache_dir/nayiri_corpus.zip`.
- Reads `authors.properties`, `publications.properties` maps.
- Processes `data-store/*` files, parse metadata + content with `_parse_properties_and_content`.
- Inserts with `client.insert_document(source="nayiri_wa_corpus", ...)`.
- Optional filename cleanup based on `corpus_keep_zip`.

---

## MongoDB schema

### `metadata` (global stage tracking)
- `stage`: `nayiri`
- `status`: `ok` | `error` etc.
- `done`: list of processed item ids/marker keys
- `timestamp`: epoch
- `updated_at`: UTC datetime

### `nayiri_entries` (lexicon)

Fields:
- `entry_id`: `nayiri:{lexeme_id}:{lemma_id|hash}`
- `lexeme_id`, `lemma_id`
- `headword`
- `part_of_speech`
- `word_forms` (list)
- `inflections` (resolved list or None)
- `definition` (string)
- `content_sha1`
- `metadata.source` = `nayiri`
- `metadata.nayiri_metadata` = whatever top-level metadata exists

### corpus docs via `client.insert_document` (likely `documents` collection)

Fields:
- `source`: `nayiri_wa_corpus`
- `title`
- `text`
- `author`
- `metadata.nayiri.file` (original filename)
- `metadata.nayiri.*` extra metadata field values
- `metadata.publication`

---

## No scraping and no local intermediate files

- the only local output is cached zip archive files in `cache_dir`.
- these are deleted unless keep flags are true.

---

## Upstream/internal dependencies

- `requests` for HTTP download
- `zipfile` for archive extraction
- `json` for lexicon parsing
- `hytools.ingestion._shared.helpers.open_mongodb_client`
- `client.insert_document` for corpus document ingestion

---

## Audit and testing guidance

- existing testing audit doc: `docs/NAYIRI_TESTING_MOCKING_AUDIT.md`
- add integration test for local zip fixtures (see tests/test_nayiri_integration.py)
- ensure metadata document updates in `client.metadata` happen.
- data distinctions:
  - dictionary entries: `nayiri_entries`
  - corpus documents: via `client.insert_document` entity in main doc collection

---

## Ready to run checklist

- `config/settings.yaml` has `scraping.nayiri` block and `cache_dir`.
- Mongo reachable.
- `requests` installed.
- call from script or API:

```python
from hytools.ingestion.acquisition.nayiri import run
run(config)
```

---

## Additional notes

This pipeline is intentionally designed to be non-scraping and fully auditable with metadata collection. It should not create stable arbitrary files in repo directories during normal execution.
