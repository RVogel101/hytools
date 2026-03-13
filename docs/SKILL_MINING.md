# Skill Mining: docs/ → Agent Skills

Mined from `docs/` to identify procedures, conventions, and domain knowledge suitable for Cursor Agent Skills. Use this to create or extend `.cursor/skills/` in this repo.

---

## Skill format (reminder)

- **Location**: `.cursor/skills/<skill-name>/SKILL.md`
- **Frontmatter**: `name`, `description` (third person, WHAT + WHEN, trigger terms)
- **Body**: Concise instructions, checklists, examples; keep SKILL.md under ~500 lines; use `reference.md` for detail.

---

## 1. Development and running (HIGH — created)

| Source | Content | Skill candidate |
|--------|---------|------------------|
| `docs/development/DEVELOPMENT.md` | Quick start, pipeline commands, tests, code quality, troubleshooting | **armenian-corpus-development** — Run pipeline, tests, black/isort/mypy; fix import/MongoDB issues |
| `docs/STRUCTURE.md` | Package layout, architecture principles, adding new scrapers (4 steps) | Folded into same skill + add-new-scraper |
| `docs/IMPORT_REDIRECTS.md` | Flat packages only; no `armenian_corpus_core`; run commands | Same skill (import conventions) |

**Created**: `.cursor/skills/armenian-corpus-development/SKILL.md`

---

## 2. Adding a new scraper (HIGH — created)

| Source | Content | Skill candidate |
|--------|---------|------------------|
| `docs/STRUCTURE.md` | Pick subpackage → implement `run(config, use_mongodb)` → register in runner → add to mongodb_supported_modules | **add-new-scraper** — Step-by-step: subpackage, entry-point, runner registration, config |
| `docs/DATA_SOURCES_EXPANSION.md` | Scraper architecture: catalog-based, resume, WA filter, rate limit, retry; config shape `scraping.<source>: queries, max_results, apply_wa_filter` | Same skill (patterns + config) |
| `docs/DATA_SOURCES_API_REFERENCE.md` | Per-source API type, auth, params, config keys | Reference only; link from skill |

**Created**: `.cursor/skills/add-new-scraper/SKILL.md`

---

## 3. Western Armenian transliteration and validation (COVERED BY RULE)

| Source | Content | Note |
|--------|---------|------|
| `.cursor/rules/western-armenian-transliteration.mdc` | WA voicing, affricates, classical orthography, checklist | Already a workspace rule; no separate skill needed |
| `docs/armenian_language_guids/*` | Phonetics, grammar, quick reference, classical orthography | Authoritative; rule points to these |
| `docs/TEST_VALIDATION_ARMENIAN.md` | Test phrases, WA/EA markers, suffix/prefix reference | Validation reference; could be a small “Armenian test phrases” skill if needed |
| `docs/ARMENIAN_REGEX_REFERENCE.md` | Regex inventory by file, dialect labels, WA/EA patterns | Reference for regex work; optional skill “Armenian regex and dialect patterns” |
| `docs/phonetics_rule_gaps.md` | Voicing reversal table | Part of rule |

**Recommendation**: Keep relying on the existing rule; add a skill only if you want “generate test phrases” or “add/modify Armenian regex” workflows.

---

## 4. Data persistence and config (MEDIUM)

| Source | Content | Skill candidate |
|--------|---------|------------------|
| `docs/DATA_PERSISTENCE_AND_FILE_USAGE.md` | What persists where (local vs MongoDB), zero local storage config, delete_after_ingest, paths | **data-persistence-and-config** — When adding storage or paths: use config-driven paths, MongoDB-first; checklist for zero local |
| `docs/MONGODB_CORPUS_SCHEMA.md` | Document structure, collections, source key alignment with metadata_tagger | **mongodb-corpus-schema** — When writing to `documents`/catalogs: follow schema; align `source` with SOURCE_METADATA |

---

## 5. Scraping runner and scheduling (MEDIUM)

| Source | Content | Skill candidate |
|--------|---------|------------------|
| `docs/SCRAPING_RUNNER_AND_LOC.md` | Centralized runner, stage names, background modes (full vs LOC-only) | **scraping-runner** — Use `scraping.runner run`; stage names for `--only`/`--skip`; background via runner or `scraping.loc run --background` |
| `docs/LOCAL_SCHEDULER.md` | Cron and systemd examples for scraping, cleaning, augmentation, book catalog, author research | **local-scheduler** — When setting up cron/systemd: copy service/timer examples; set WorkingDirectory and config path |

---

## 6. Augmentation pipeline (MEDIUM)

| Source | Content | Skill candidate |
|--------|---------|------------------|
| `docs/AUGMENTATION_FAQ.md` | safe_generation, baseline_statistics vs metrics_pipeline, script roles, main flow, config flags | **augmentation-pipeline** — When changing augmentation: use safe wrapper when needed; know baseline vs per-text metrics; runner subcommands (run, metrics, estimate, status) |

---

## 7. Armenian tokenizer (LOW — reference only)

| Source | Content | Skill candidate |
|--------|---------|------------------|
| `docs/ARMENIAN_TOKENIZER.md` | extract_words: normalization (NFC, ligatures, lowercasing), regex, min_length, where used | Reference; link from code. Optional micro-skill “when to use extract_words vs raw regex” |

---

## 8. External APIs and permissions (LOW — reference)

| Source | Content | Skill candidate |
|--------|---------|------------------|
| `docs/DATA_SOURCES_API_REFERENCE.md` | Gallica, DPLA, Gomidas, Mechitarist, AGBU: API type, auth, config | Reference for implementing or debugging scrapers |
| `docs/DPLA_API_KEY.md` | Request DPLA key | Reference |
| `docs/GOMIDAS_BULK_PERMISSION.md`, `docs/MECHITARIST_PERMISSION_REQUEST.md`, etc. | Permission templates | Reference when requesting access |

---

## 9. Future improvements and audits (CONTEXT)

| Source | Content | Use |
|--------|---------|-----|
| `docs/FUTURE_IMPROVEMENTS.md` | Implementation status table, drift/metrics config, loanword/etymology/stem/transliteration ideas | When planning features or implementing config flags |
| `docs/DEVELOPMENT_PLAN_AUDIT.md` | Audit notes | Context only |

---

## Summary: created vs proposed

| Status | Skill name | Trigger / when to use |
|--------|------------|------------------------|
| **Created** | armenian-corpus-development | Run pipeline, tests, fix imports, understand package layout |
| **Created** | add-new-scraper | Add a new data source / scraper stage |
| Proposed | data-persistence-and-config | Adding storage, paths, or “zero local” setup |
| Proposed | mongodb-corpus-schema | Writing to documents/catalogs; aligning source keys |
| Proposed | scraping-runner | Choosing stages, background mode, runner vs single-stage |
| Proposed | local-scheduler | Setting up cron or systemd for pipeline |
| Proposed | augmentation-pipeline | Changing or debugging augmentation flow and metrics |
| Covered by rule | Western Armenian | Transliteration, phonetics, validation (use existing rule) |
| Reference only | DATA_SOURCES_API_REFERENCE, ARMENIAN_TOKENIZER, etc. | No skill; link from other skills or docs |

---

## How to add a proposed skill

1. Create `.cursor/skills/<skill-name>/SKILL.md` with frontmatter and concise body.
2. Add trigger terms to `description` (e.g. “Use when adding a new scraper or data source”).
3. Link to the mined doc(s) in a “References” section.
4. Optionally add `reference.md` for long content; keep SKILL.md under ~500 lines.
