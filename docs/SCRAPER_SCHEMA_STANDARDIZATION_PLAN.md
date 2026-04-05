# Scraper Output Schema Standardization Plan

**Status**: IMPLEMENTED
**Date**: 2026-03-06

## Problem Statement

The 19 active scrapers in `hytools/ingestion/acquisition/` each emit records with
ad-hoc field names and inconsistent metadata nesting.  This makes downstream
queries, deduplication, and dialect-branch filtering fragile.

### Key Inconsistencies Observed

| Issue | Variants Found | Files Affected |
|-------|---------------|----------------|
| Language code field | `source_language_code`, `internal_language_code`, `url_lang`, `language` | 14 scrapers |
| URL field | `url`, `source_url`, `metadata.url` | 12 scrapers |
| Publication date | `publication_date`, `published_date`, `published_at`, `publication_date_raw` | 6 scrapers |
| WA confidence score | `wa_score` present in 4 scrapers, absent in 11 | archive_org, agos, hamazkayin, opus |
| Metadata nesting | Flat top-level vs nested `metadata{}` sub-dict | Varies per scraper |
| Source identifier | `source_id`, `source`, `source_name`, `source_family` | All scrapers |
| Content hash | `sha1(text)` in `insert_or_skip`, but naming varies | All scrapers |

## Existing Shared Types

The codebase already has two relevant schemas that are **not used at insert time**:

1. **`core_contracts.DocumentRecord`** — frozen dataclass with `document_id, source_family, text, title, source_url, content_hash, char_count, internal_language_code, internal_language_branch, metadata`.

2. **`_shared.metadata.TextMetadata`** — 23-field dataclass with enums for `SourceType`, `ContentType`, `WritingCategory`, `InternalLanguageCode`, `InternalLanguageBranch`, `Dialect`, `DialectSubcategory`, `Region`.

Both are well-designed but unused by the actual scraper insert path.

## Proposed Solution

### Phase 1 — Canonical `ScrapedDocument` dataclass

Create a **single insert-time schema** that every scraper builds before calling
the shared insert helper.  This schema bridges the gap between raw scrape
output and the existing `DocumentRecord` contract.

```python
# hytools/ingestion/_shared/scraped_document.py

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, Optional

@dataclass
class ScrapedDocument:
    """Canonical schema that every scraper must produce before insert."""

    # ── Required ──────────────────────────────────────────────────
    source_family: str              # e.g. "archive_org", "agos", "nayiri"
    text: str                       # full text content

    # ── Identity ──────────────────────────────────────────────────
    title: Optional[str] = None
    source_url: Optional[str] = None
    content_hash: Optional[str] = None  # computed by insert helper if None

    # ── Language classification ────────────────────────────────────
    source_language_code: Optional[str] = None   # ISO 639-3 from provider (hyw/hye/en)
    internal_language_code: Optional[str] = None  # computed: hy / eng
    internal_language_branch: Optional[str] = None  # computed: hye-w / hye-e / eng
    wa_score: Optional[float] = None              # WA confidence [0.0, 1.0]

    # ── Provenance ────────────────────────────────────────────────
    publication_date: Optional[str] = None  # ISO 8601 string
    extraction_date: str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    catalog_id: Optional[str] = None       # archive.org ID, LCCN, HTID, etc.

    # ── Classification ────────────────────────────────────────────
    source_type: Optional[str] = None       # SourceType enum value
    content_type: Optional[str] = None      # ContentType enum value
    writing_category: Optional[str] = None  # WritingCategory enum value

    # ── Extensible metadata ───────────────────────────────────────
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_insert_dict(self) -> dict:
        """Convert to the dict shape expected by MongoDB insert."""
        d = asdict(self)
        # Flatten 'extra' into a 'metadata' sub-dict for backward compat
        metadata = d.pop("extra", {})
        for key in ("source_language_code", "internal_language_code",
                     "internal_language_branch", "wa_score",
                     "catalog_id", "source_type", "content_type",
                     "writing_category", "publication_date"):
            val = d.pop(key, None)
            if val is not None:
                metadata[key] = val
        d["metadata"] = metadata
        return d

    def to_document_record(self) -> "DocumentRecord":
        """Upcast to the core_contracts.DocumentRecord."""
        from hytools.core_contracts.types import DocumentRecord
        return DocumentRecord(
            document_id=self.content_hash or "",
            source_family=self.source_family,
            text=self.text,
            title=self.title,
            source_url=self.source_url,
            content_hash=self.content_hash,
            char_count=len(self.text),
            internal_language_code=self.internal_language_code,
            internal_language_branch=self.internal_language_branch,
            metadata=self.extra,
        )
```

### Phase 2 — Adapt the shared insert helpers

Update `save_text()` / `insert_or_skip()` (in `_shared/helpers.py`) to accept
a `ScrapedDocument` instance **or** the current positional args for backward
compatibility:

```python
def save_text(doc_or_client, *args, **kwargs):
    if isinstance(doc_or_client, ScrapedDocument):
        return _save_scraped_document(doc_or_client, **kwargs)
    # legacy positional path — unchanged
    return _save_text_legacy(doc_or_client, *args, **kwargs)
```

### Phase 3 — Migrate scrapers one-by-one

Each scraper builds a `ScrapedDocument(...)` before calling the insert helper.
Migration order (by test coverage / risk):

| Priority | Scraper | Reason |
|----------|---------|--------|
| 1 | `archive_org` | Highest volume, well-tested |
| 2 | `wiki` | High volume, stable |
| 3 | `news` | 3 sub-runners, most complex |
| 4 | `culturax` | HF streaming, checkpoint logic |
| 5 | `opus` | 12 parallel corpora |
| 6-19 | Remaining | Alphabetical order |

Each migration is a single-scraper PR with:
- Replace ad-hoc dict building → `ScrapedDocument(...)`
- Verify existing tests still pass
- Add one test asserting `to_insert_dict()` output shape

### Phase 4 — Validation at insert time

Add a lightweight `validate()` method to `ScrapedDocument`:

```python
def validate(self) -> list[str]:
    """Return list of warnings (empty = valid)."""
    warnings = []
    if not self.text.strip():
        warnings.append("empty text")
    if self.source_language_code and self.source_language_code not in KNOWN_CODES:
        warnings.append(f"unknown source_language_code: {self.source_language_code}")
    if self.wa_score is not None and not (0.0 <= self.wa_score <= 1.0):
        warnings.append(f"wa_score out of range: {self.wa_score}")
    return warnings
```

The insert helper calls `validate()` and logs warnings without blocking inserts.

## Field Mapping Reference

How each scraper's current fields map to `ScrapedDocument`:

| Current Field | → ScrapedDocument Field | Notes |
|---------------|------------------------|-------|
| `source` / `source_name` / `source_id` | `source_family` | Normalize to snake_case identifiers |
| `title` | `title` | No change |
| `text` / `content` | `text` | No change |
| `url` / `source_url` | `source_url` | Consolidate |
| `metadata.source_language_code` | `source_language_code` | Promote to top level |
| `metadata.internal_language_code` | `internal_language_code` | Promote to top level |
| `metadata.wa_score` | `wa_score` | Promote to top level |
| `metadata.archive_id` / `htid` / `lccn_id` / `ark` | `catalog_id` | Unified catalog reference |
| `metadata.published_date` / `published_at` / `publication_date_raw` | `publication_date` | Normalize to ISO 8601 |
| `metadata.writing_category` | `writing_category` | No change |
| `metadata.*` (remaining) | `extra` | Passthrough bucket |

## Backward Compatibility

- `to_insert_dict()` produces the exact same dict shape currently stored in MongoDB.
- No MongoDB migration needed — new documents look identical to old ones.
- Existing query code continues working unchanged.
- The `extra` dict preserves scraper-specific fields (e.g. `dpla_id`, `pages_downloaded`).

## Estimated Effort

| Phase | Scope | Risk |
|-------|-------|------|
| Phase 1 | 1 new file (~80 lines) + tests | Low |
| Phase 2 | 1 file edit (helpers.py) | Low |
| Phase 3 | 19 scraper files, ~5-15 lines each | Medium (regression risk) |
| Phase 4 | 1 method addition + test | Low |

## Open Questions

1. **Should `wa_score` be computed at insert time for ALL scrapers?** Currently
   only 4 of 19 scrapers compute it.  Adding it universally would improve
   filtering but costs ~2ms per document.

2. **Should `TextMetadata` be deprecated in favor of `ScrapedDocument`?**
   `TextMetadata` has 23 fields with rich enum types; `ScrapedDocument` is
   simpler.  They could coexist (TextMetadata for analytics, ScrapedDocument for
   ingestion) or be merged.

3. **Should the `nayiri` scraper conform?** It uses a separate `LexiconEntry`
   schema for dictionary data, which is fundamentally different from corpus
   documents.  Recommendation: keep `nayiri` on `LexiconEntry`, exclude from
   this migration.
