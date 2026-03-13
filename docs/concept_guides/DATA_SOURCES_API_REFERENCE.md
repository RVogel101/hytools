# Data Sources: API Documentation Summary

Reference for external APIs and access methods used by armenian-corpus-core scrapers. Use this when requesting API keys or integrating new sources.

---

## Gallica (BnF) — **Implemented**

**Status:** Implemented in `scraping/gallica.py`. No API key required.

### API type

- **SRU (Search/Retrieve via URL)** — protocol version 1.2  
- **Endpoint:** `https://gallica.bnf.fr/SRU`  
- **Documentation:** [API Gallica – BnF](https://api.bnf.fr/fr/api-gallica-de-recherche), [Protocole SRU](https://www.bnf.fr/fr/protocole-sru-formuler-une-recherche)

### Parameters

| Parameter         | Required | Description |
|------------------|----------|-------------|
| `version`        | Yes      | `1.2` |
| `operation`      | Yes      | `searchRetrieve` |
| `query`          | Yes      | CQL expression (e.g. `(dc.language any "arm") and (dc.type any "monographie")`) |
| `maximumRecords` | No       | 0–50, default 15 |
| `startRecord`    | No       | Pagination start (1-based) |
| `collapsing`     | No       | Aggregate multi-volume (default `true`) |

### Query language (CQL)

- **Relations:** `all` (all words), `any` (any word), `adj` (exact phrase)
- **Fields:** `dc.language`, `dc.type`, `dc.subject`, `metadata`, etc.
- **BnF language code for Armenian:** `arm` (in `dc.language`)

### Response

- XML with Dublin Core / SRU elements; `srw:numberOfRecords` for total; each `record` contains `recordData` with `title`, `identifier` (ARK), `creator`, `date`.

### Full-text

- OCR text: `https://gallica.bnf.fr/ark:/12148/{ark}.texte` (HTML or plain; strip tags if needed).

### Config

- `config["scraping"]["gallica"]["queries"]` — list of CQL strings  
- `config["scraping"]["gallica"]["max_results"]` — max items per query (default 200)

---

## DPLA (Digital Public Library of America) — **Implemented**

**Status:** Implemented in `scraping/dpla.py`. **API key required.**

### API type

- **REST JSON API** — v2  
- **Base URL:** `https://api.dp.la/v2`  
- **Documentation:** [DPLA Developers – Requests](https://pro.dp.la/developers/requests), [Technical Documentation](https://pro.dp.la/developers/technical-documentation)

### Authentication

- **API key:** Required on every request.  
- **Request a key:** `POST https://api.dp.la/v2/api_key/YOUR_EMAIL@example.com`  
- **Usage:** `?api_key=YOUR_32_CHAR_KEY` or set `config["scraping"]["dpla"]["api_key"]` or env `DPLA_API_KEY`.  
- See `docs/development/requests_guides/DPLA_API_KEY.md` and `docs/development/requests_guides/request_dpla_api_key.ps1` / `request_dpla_api_key.sh`.

### Items resource

- **URL:** `https://api.dp.la/v2/items`  
- **Parameters:** `page`, `page_size` (max 500), `sourceResource.language.name`, `sourceResource.type`, `q` (full-text search).

### Response structure

- `docs` — array of items; each has `id`, `sourceResource` (title, description, language, type, format, creator), `isShownAt`, `object`, `dataProvider`.

### Config

- `config["scraping"]["dpla"]["api_key"]` or `DPLA_API_KEY`

---

## Gomidas Institute — **Implemented**

**Status:** Implemented in `scraping/gomidas.py`. No API; HTML scraping.

### Access type

- **Website scraping** — no public REST API.  
- **Resources page:** `https://www.gomidas.org/resources.html`  
- **Discovery:** Parse HTML, collect links that match Armenian/newspaper/PDF keywords; follow links to PDFs.

### Implementation notes

- Catalog built by scraping `resources.html` with BeautifulSoup; PDFs downloaded and run through `ocr/pipeline.py` for text; text ingested to MongoDB.  
- **Rate limiting:** 2 s delay between requests (`_REQUEST_DELAY`).  
- **Bulk permission:** See `docs/GOMIDAS_BULK_PERMISSION.md` if you need formal bulk access.

### Config

- No API key. Enable via `config["scraping"]["gomidas"]["enabled"]` if present in runner.

---

## Mechitarist Library (San Lazzaro, Venice) — **Not started (stub ready)**

**Status:** Stub in `scraping/mechitarist.py`. No public API; partnership/permission required.

### Access type

- **Online catalog:** https://catalog.mechitar.org/ (Calfa partnership; searchable manuscript database).  
- **No public REST API** — the catalog is a web application, not an open API.  
- **Library contact:** library@mechitar.org; catalog site: https://www.orlazaroarmeno.it/

### What exists

- ~1,500+ Armenian printed works (17th–20th c.); manuscript catalog with 2,000+ records (catalog.mechitar.org).  
- Permission template: `docs/MECHITARIST_PERMISSION_REQUEST.md`.

### Stub implementation

- `scraping/mechitarist.py` provides `run(config)` and a CLI. When no catalog source is configured, it logs that Mechitarist requires permission/export and exits.  
- **When you have access:** Set `config["scraping"]["mechitarist"]["catalog_path"]` to a path to a bulk export (e.g. JSON/CSV), or `config["scraping"]["mechitarist"]["api_base"]` and `api_key` if they provide an API later. The stub is structured so you can plug in a catalog loader and ingest loop.

### Config (for when access is granted)

- `config["scraping"]["mechitarist"]["catalog_path"]` — path to bulk export file (JSON/JSONL/CSV)  
- `config["scraping"]["mechitarist"]["api_base"]` — optional future API base URL  
- `config["scraping"]["mechitarist"]["api_key"]` — optional future API key  

---

## AGBU Nubar Library (Paris) — **Not started (stub ready)**

**Status:** Stub in `scraping/agbu.py`. No public API; partnership/on-site access.

### Access type

- **Website:** https://bnulibrary.org — digitized collections, periodicals, archives.  
- **No public REST or bulk-download API** — access is by appointment and partnership.  
- **Contact:** Via site contact form or AGBU (https://agbu.org) for partnership inquiries.

### What exists

- 43,000+ printed books, 800,000+ archival documents, 1,400 periodicals; Western Armenian diaspora focus.  
- Partnership model (e.g. Calfa): library supplies images/metadata; partner supplies OCR/corpus building.  
- See `docs/AGBU_NUBARIAN_LIBRARY_PARTNERSHIP.md`.

### Stub implementation

- `scraping/agbu.py` provides `run(config)` and a CLI. When no data source is configured, it logs that AGBU requires partnership and exits.  
- **When you have access:** Set `config["scraping"]["agbu"]["catalog_path"]` or `export_path` to a bulk export, or `api_base` + `api_key` if they provide an API. The stub is ready for a catalog loader and ingest loop.

### Config (for when partnership yields data)

- `config["scraping"]["agbu"]["catalog_path"]` or `export_path` — path to bulk export  
- `config["scraping"]["agbu"]["api_base"]` — optional future API base URL  
- `config["scraping"]["agbu"]["api_key"]` — optional future API key  

---

## Summary

| Source      | API / access           | Key required | Implemented | Notes                          |
|------------|------------------------|--------------|-------------|--------------------------------|
| Gallica    | SRU (no key)          | No           | Yes         | CQL queries, ARK .texte        |
| DPLA       | REST v2               | Yes          | Yes         | Request key via POST           |
| Gomidas    | HTML scraping        | No           | Yes         | PDF + OCR                      |
| Mechitarist| None (catalog only)   | N/A          | Stub        | Permission/export needed       |
| AGBU       | None (partnership)   | N/A          | Stub        | Partnership/export needed      |
