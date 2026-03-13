# News and RSS Catalog

How the news acquisition pipeline works, how to run it, and the schema for the **news_article_catalog** and tagged documents.

---

## Overview

The **news** stage (`ingestion.acquisition.news`) does two things:

1. **Diaspora newspapers** (Aztag, Horizon, Asbarez): Selenium-based scraping of full issues.
2. **RSS-based news**: A single process that (1) updates **news_article_catalog** from all configured RSS feeds—**including the same diaspora newspapers** (Aztag, Horizon, Asbarez) via their RSS feeds—then (2) scrapes full article text for each catalog entry that does not yet have a `document_id`, inserts into **documents**, and links the catalog to the document.

RSS feeds provide titles, summaries, and URLs—not full article text. The catalog stores one document per article URL; when the same article appears in multiple feeds, we keep one catalog entry and record all source names in `sources` and `feed_urls`. Full article text is stored only once in **documents**; the catalog’s `document_id` points to that document.

---

## How to run

### Prerequisites

- **MongoDB** running and configured in `config/settings.yaml` (or env) under `database.mongodb_uri` and `database.mongodb_database`.
- **Python** with dependencies installed (`pip install -r requirements.txt` or project install).

### Run the full pipeline (including news)

From the project root (armenian-corpus-core):

```bash
python -m ingestion.runner run
```

### Run only the news stage

```bash
python -m ingestion.runner run --only news
```

### Run everything except news

```bash
python -m ingestion.runner run --skip news
```

### Configuration

News is enabled when any of `newspapers`, `eastern_armenian`, or `rss_news` is enabled in config. RSS catalog behavior is under `scraping.rss_news`:

| Key | Default | Description |
|-----|--------|-------------|
| `enabled` | — | If true, RSS catalog + scrape-from-catalog run when the news stage runs. |
| `populate_catalog` | `true` | When true: (1) update news_article_catalog from all RSS sources, (2) scrape each new article and set `catalog.document_id`. When false, legacy feed-only path (if still present). |
| `sources` | (all) | Optional list of source names to include; if omitted, all entries from `ALL_RSS_SOURCES` are used. |
| `request_delay` | (internal default) | Seconds between HTTP requests to avoid overloading feeds/sites. |

Example in `config/settings.yaml`:

```yaml
scraping:
  rss_news:
    enabled: true
    populate_catalog: true
    # sources: ["Armenian Weekly", "EVN Report"]  # optional: limit to these
```

---

## Tagging (language_code, content_type, writing_category)

Catalog entries and the documents written from them carry detailed tags for filtering and downstream pipelines.

### Catalog fields (news_article_catalog)

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | Canonical article URL (one catalog doc per URL). |
| `title` | string | From RSS. |
| `summary` | string | From RSS. |
| `published_at` | datetime/string | Publication date if provided. |
| `category` | string | e.g. `news`, `analysis`, `diaspora`, `international`. |
| `tags` | array | Feed/item tags. |
| **`language_code`** | string | Primary language for this URL from the first source (ISO 639-3/BCP 47): `hy`, `hyw`, `hye`, `eng`, `und`. |
| **`source_language_codes`** | array | All distinct language codes from feeds that referenced this URL (e.g. `["hy", "eng"]` if both Armenian and English feeds list it). |
| **`content_type`** | string | Always `article` for RSS-sourced items. |
| **`writing_category`** | string | Same as `category` (news, analysis, diaspora, international, etc.). |
| `sources` | array | Names of RSS sources that listed this URL. |
| `feed_urls` | array | RSS feed URLs that listed this URL. |
| `document_id` | string \| null | ObjectId (as string) of the representative document in **documents**, or null if not yet scraped. |

See **docs/concept_guides/LANGUAGE_CODES.md** for allowed `language_code` values (hy, hyw, hye, hyc, eng, etc.).

### Document metadata (documents written from catalog)

When an article is scraped and inserted via `insert_or_skip`, the following are set in `metadata` (plus standard fields like `url`, `date_scraped`, `word_count`, etc.):

| Field | Description |
|-------|-------------|
| `source_type` | `"news"` |
| `category` | From catalog (e.g. news, diaspora). |
| `published_at` | From catalog. |
| `tags` | From catalog. |
| `rss_sources` | List of RSS source names. |
| **`language_code`** | Primary language (from catalog). |
| **`source_language_codes`** | All language codes from catalog (feeds that referenced this URL). |
| **`content_type`** | From catalog (e.g. `article`). |
| **`writing_category`** | From catalog (e.g. news, analysis). |

Downstream (e.g. metadata_tagger, dialect views) can use `metadata.language_code` and `metadata.writing_category` for filtering and analytics.

---

## RSS media sources (full list)

Every outlet whose RSS feed is consumed by the news stage. **Type:** Diaspora (Armenian diaspora outside Armenia/Artsakh), Republic (Armenian state / Armenia-based), International (non-Armenian, keyword-filtered or Armenia-focused).

**Republic of Armenia sources:** When a site offers both Armenian and another language (e.g. English), scraping **always opts for the Armenian feed** so that content is in Armenian. All Republic-of-Armenia Armenian content is tagged **hye** (Eastern Armenian). Diaspora Armenian is **hyw** (Western Armenian).

| Source | Type | Country | Region | Likely language | Main URL |
|--------|------|---------|--------|-----------------|----------|
| Aztag | Diaspora | Lebanon | Middle East | hyw | https://aztagdaily.com |
| Horizon Weekly | Diaspora | Canada | North America | hyw | https://horizonweekly.ca |
| Asbarez | Diaspora | USA | North America | hyw | https://asbarez.com |
| Armenian Weekly | Diaspora | USA | North America | hyw | https://armenianweekly.com |
| Massis Post | Diaspora | USA | North America | hyw | https://massispost.com |
| Armenian Mirror-Spectator | Diaspora | USA | North America | hyw | https://mirrorspectator.com |
| Agos | Diaspora | Turkey | Middle East | eng | https://www.agos.com.tr |
| Armenpress | Republic | Armenia | South Caucasus | eng | https://armenpress.am |
| Azatutyun (RFE/RL) | Republic | Armenia | South Caucasus | hye | https://www.azatutyun.am |
| Hetq | Republic | Armenia | South Caucasus | eng | https://hetq.am |
| Panorama.am | Republic | Armenia | South Caucasus | hye | https://www.panorama.am |
| EVN Report | Republic | Armenia | South Caucasus | eng | https://evnreport.com |
| OC Media | Republic | Georgia (Caucasus) | South Caucasus | eng | https://oc-media.org |
| Civilnet | Republic | Armenia | South Caucasus | eng | https://www.civilnet.am |
| Google News - Armenia | International | — | Aggregator | eng | https://news.google.com |
| Al Jazeera | International | Qatar | Middle East | eng | https://www.aljazeera.com |
| Al-Monitor | International | USA | Middle East focus | eng | https://www.al-monitor.com |
| BBC World | International | UK | Global | eng | https://www.bbc.co.uk/news/world |
| France 24 | International | France | Global | eng | https://www.france24.com |
| Deutsche Welle | International | Germany | Global | eng | https://www.dw.com |
| Euronews | International | Europe | Global | eng | https://www.euronews.com |

---

## RSS source list and per-source language_code

Each entry in `ALL_RSS_SOURCES` (in `ingestion/acquisition/news.py`) can define:

- `name`, `url`, `rss`, `category`
- **`language_code`**: default language for items from that feed: **hye** (Republic of Armenia Armenian), **hyw** (diaspora Western Armenian), **eng**, or **hy** (undetermined).

**Republic of Armenia:** For sites that offer both Armenian and another language (e.g. Panorama.am), the scraper uses the **Armenian** feed (e.g. `?lang=hy` or the non-`/en/` path) and tags content **hye**. Diaspora Armenian sources use **hyw**. English-only Republic feeds (e.g. Armenpress English, Hetq English) stay **eng**. This drives the catalog’s `language_code` and `source_language_codes` and thus the document’s `metadata.language_code` / `metadata.source_language_codes`.

---

## MongoDB collections

- **news_article_catalog**: One document per article URL; indexes on `url` and `document_id` (non-unique).
- **documents**: One full-text document per article URL; linked from catalog via `document_id`. Standard enrichment (metrics, drift check) runs on insert when configured.

See **docs/concept_guides/MONGODB_CORPUS_SCHEMA.md** for the full **documents** and catalog schema.

---

## Related docs

- **SCRAPER_IMPLEMENTATION_STATUS.md** — Status of all scrapers including news and RSS.
- **LANGUAGE_CODES.md** — Canonical language codes (hy, hyw, hye, eng, etc.).
- **MONGODB_CORPUS_SCHEMA.md** — Full schema for documents and catalogs.
- **DEVELOPMENT.md** — General development and test run instructions.
