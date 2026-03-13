# Book and Manuscript Title Identification

This document explains how the book inventory process distinguishes **book/manuscript titles** from other named entities (person names, places, churches, animals, etc.) when scanning corpus text.

---

## The Problem

Armenian text contains many capitalized or prominent phrases that are **not** book titles:

| Type | Examples (Armenian) | Why it's not a book |
|------|--------------------|---------------------|
| **Person names** | Վահան Թեքեյան, Զապել Եսայեան | Author names, not titles |
| **Places** | Պէյրութ, Իսթանպուլ, Հալէպ | Geographic locations |
| **Churches** | Սուրբ Խաչ, Սուրբ Աստուածածին | Religious buildings |
| **Institutions** | Մխիթարեան, Նուպարեան | Schools, libraries |
| **Animals** | (context-dependent) | Rare in title context |
| **Dates/periods** | 1915, Մեծ Եղեռն | Historical references |

A naive approach (e.g. "first line with Armenian script") produces many false positives.

---

## Identification Strategies

### 1. Context Markers (High Confidence)

Phrases that **precede** or **follow** a candidate strongly indicate a book/manuscript:

| Marker (Armenian) | Romanization | Meaning | Example |
|------------------|--------------|---------|---------|
| կարդացած եմ | kardatsats em | "I have read" | կարդացած եմ «Վահէն» |
| կարդալ | kardal | "to read" | «Տաղերգութիւն» կարդալ |
| գիրք | girkʿ | "book" | «Գիրք Տաղեր» |
| ձեռագիր | dzeragir | "manuscript" | ձեռագիր «Մատեան» |
| հրատարակուած | hratarakvats | "published" | «Պատմութիւն» հրատարակուած |
| գրած | grats | "wrote" | «Նահատակ» գրած |
| գիրքը | girkʿë | "the book" | «Գիրքը» |
| մատեան | matian | "manuscript/codex" | «Մատեան Տաղեր» |

**Regex pattern**: Look for `«...»` or `"..."` after these markers, or for markers before a candidate phrase.

### 2. "Book of" / "Collection of" Patterns (High Confidence)

Titles often start with:

| Pattern | Armenian | Example |
|---------|----------|---------|
| "The book of" | Գիրք, Գիրքը | Գիրք Տաղեր |
| "Collection of" | Ժողովածու | Ժողովածու Բանաստեղծութեանց |
| "History of" | Պատմութիւն | Պատմութիւն Հայոց |
| "Poems of" | Տաղեր, Տաղերգութիւն | Տաղերգութիւն Վահէն |
| "Works of" | Երկեր | Երկեր Զապել Եսայեանի |

### 3. Author–Book Correlation (Medium Confidence)

If we know which books an author wrote (from WorldCat, Wikipedia, manual DB), a phrase that matches a known title by a detected author is high confidence.

Example: If "Վահան Թեքեյան" appears in the text and we have a title "Վահէն" in our author–book DB, then "Վահէն" in context is likely the book.

### 4. Structural Cues

- **Quotation marks**: `«...»` (Armenian guillemets) or `"..."` often wrap titles.
- **Position**: Titles often appear at the start of a document, in headers, or in bibliographies.
- **Length**: Book titles are typically 2–80 characters; single words are often names.

### 5. Exclusion: Named Entity Filtering

To reduce false positives, we **exclude** candidates that match:

| Entity type | Detection method |
|-------------|------------------|
| **Person names** | Known author list, "Վրդ." (Reverend), "Դոկ." (Doctor), Armenian name patterns |
| **Places** | Gazetteer of Armenian place names (Պէյրութ, Իսթանպուլ, Երեւան, etc.) |
| **Churches** | "Սուրբ" + name, "Վանք", "Եկեղեցի" |
| **Institutions** | "Մխիթարեան", "Նուպարեան", "Դպրոց", "Գրադարան" |

---

## Implementation Approach

1. **MongoDB scan**: Iterate documents; use `title` field when present; extract from `text` when needed.
2. **Context regex**: Build patterns for "read in", "the book of", "published", etc.
3. **Exclusion lists**: Maintain lists of common person names, places, churches (from cleaning/author_database, gazetteers).
4. **Scoring**: Assign confidence (0–1) based on:
   - Context marker present: +0.4
   - "Book of" / "Collection of" pattern: +0.3
   - Quotation marks: +0.2
   - Length 5–60 chars, Armenian ratio > 0.6: +0.1
   - Matches known NER (person, place, church): -0.5
5. **Threshold**: Only add to inventory if confidence ≥ 0.5.

---

## Data Source: MongoDB

The book inventory scans **MongoDB** (not file directories). All scrapers write
to MongoDB; there are no persistent `data/raw`, `data/cleaned`, or `data/filtered`
directories. Use ``--scan-mongodb`` with the book inventory runner.

---

## Future Enhancements

- **NER model**: Train or use a multilingual NER to tag person, location, org; exclude those.
- **Author–book DB**: Expand from WorldCat; use for correlation.
- **Wikipedia/Wikisource**: Cross-check candidate titles against known Armenian works.
