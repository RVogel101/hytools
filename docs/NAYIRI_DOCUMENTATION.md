# Nayiri Public Data Documentation

This document consolidates the Nayiri developer documentation URLs and the extracted data model/schema/details for the lexicon and corpus datasets.

Sources used:
- http://www.nayiri.com/developers?l=en
- http://www.nayiri.com/nayiri-armenian-lexicon?l=en
- http://www.nayiri.com/nayiri-armenian-lexicon-data-model?l=en
- http://www.nayiri.com/nayiri-armenian-lexicon-file-format?l=en
- http://www.nayiri.com/nayiri-armenian-lexicon-data-schema-reference?l=en
- http://www.nayiri.com/text-corpus?l=en&action=showOverview
- http://www.nayiri.com/nayiri-armenian-text-corpus-data-set?l=en
- http://www.nayiri.com/nayiri-armenian-text-corpus-concepts?l=en
- http://www.nayiri.com/nayiri-armenian-text-corpus-file-structure?l=en
- http://www.nayiri.com/nayiri-armenian-text-corpus-document-data-store?l=en
- http://www.nayiri.com/nayiri-armenian-text-corpus-authors-data-store?l=en
- http://www.nayiri.com/nayiri-armenian-text-corpus-publications-data-store?l=en
- http://www.nayiri.com/nayiri-armenian-text-corpus-markup-language?l=en

---

## 1. Dataset size & metadata

### Lexicon current release (2026-02-15-v1)
- 7,076 Lexemes
- 7,931 Lemmas
- 1,491,045 Word Forms
- 709 Inflections
- In addition: sample subset 20 Lexemes / ~3,600 Word Forms / 700+ Inflections.

Nayiri lexicon metadata fields:
- `version` (YYYY-MM-DD-vN)
- `license` (CC BY 4.0)
- `publisher` (Nayiri Institute)
- `author`, `contactEmail`, `website`, `sponsorship`, etc.
- Stats: `numLexemes`, `numLemmas`, `numWordForms`, `numInflections`.

### Corpus current release (2026-02-25-v2)
- 396 Documents
- 21 Publications
- 100 Authors
- 170,745 Tokens

Corpus is described as beta, growing, and primarily Western Armenian (WA). 

---

## 2. Lexicon JSON model

### Root-level object
- `lexemes` (array of Lexeme)
- `inflections` (array of Inflection objects)
- `metadata` (metadata object described above)

### Lexeme object
- `lexemeId` (string, 4-digit base64url key)
- `description` (human description, includes lemma list and English gloss)
- `lemmaType` (`NOMINAL`, `VERBAL`, `UNINFLECTED`)
- `lemmas` (array of Lemma)

### Lemma object
- `lemmaId` (string, 5-digit base64url key)
- `lemmaString` (canonical form, e.g. ճշդել)
- `partOfSpeech` (NOUN/VERB/etc)
- `lemmaDisplayString` (human description with gloss)
- `numWordForms` (int)
- `wordForms` (array of WordForm)

### WordForm object
- `s` (string word form, inflected surface)
- `i` (string Inflection ID reference)

### Inflection object
- `inflectionId` (string, 4-digit base64url key)
- `lemmaType` (NOMINAL/VERBAL/UNINFLECTED)
- `displayName` (localized object: `hy`, `en`)
- `verbalInflectionClass` (for verbs)
- `verbPolarity` (POSITIVE/NEGATIVE)
- `verbTense` / `verbMood` / `grammaticalPerson` / `grammaticalNumber` / `grammaticalCase` / `grammaticalArticle` (where applicable)

### What is captured
- complete lexemic hierarchy
- lemma & PoS disambiguation
- all inflections mapped by ID (shared reference object)
- word forms with morphological reference
- dictionary metadata, including counts and authorship

---

## 3. Corpus model and file structure

### Document Data Store format
- One file per document, named `<Document ID>.txt`.
- File has metadata block (key=value lines), blank line, marker `BEGIN_DOCUMENT_CONTENT`, then text content in NML.

#### Required metadata fields
- `id` (6-digit base64url unique identifier)
- `writtenLanguageVariant` (WA/Ea/EA_RO etc)

#### Optional metadata fields
- `publicationId`, `authorId`, `yearPublished`, `monthPublished`, `dayPublished`, `title`, `subTitle`, `category`, `url`, `scanUrl`
- `isManuallyStemmedAndTokenized` (bool)
- `usernameCreatedBy`, `creationTime`, etc.

### Authors Data Store
- `authors.properties` file with key=JSON Author object.
- Author object fields: `name`, `url`, `yearOfBirth`, `yearOfDeath`, `notes`.

### Publications Data Store
- `publications.properties` file with key=JSON Publication object.
- Publication fields: `name`, `url`, `location`, `yearFounded`, `yearCeasedPublication`, `notes`.

### categorical and dataset metadata
- core dataset is 396 docs, 100 authors, 21 pubs for COWA.

---

## 4. Nayiri Markup Language (NML)

### Purpose
- support explicit tokenization, lemmatization, POS tagging in corpus text.
- designed to represent mnemonic morphological annotation for training and search.

### explicit tokenization syntax
- `[[any word form]]` creates token.
- tokens map to word forms in lexicon.

### explicit lemmatization
- `[[word form >>> lemma]]` or `[[word form >>> lemma@POS]]`.
- shorthand `.` means lemma is same as word form.

### POS tagging
- `[[word form >>> lemma@POS]]`.
- supported POS codes: NOUN/PRONOUN/VERB/ADJECTIVE/ADVERB/CONJUNCTION/INTERJECTION/ARTICLE/DETERMINER/ADPOSITION (+ aliases)

### examples and disambiguation
- `[[որ >>> որ@PRO]]` vs `[[որ >>> որ@CON]]`
- `[[այս >>> այս@PRO]]` vs `[[այս >>> այս@DET]]`

---

## 5. Data assumptions vs hytools pipeline

### Lexicon ingestion
- hytools currently imports lexicon fields: lexemeId, lemmaId, lemmaString, pos, wordForms, resolved inflections, definition.
- metadata fields in JSON may include more dataset-level fields and currently stored under `metadata.nayiri_metadata`.
- If additional fields are needed (e.g. `numLemmas`, `numWordForms`), they are currently available in `metadata`. hytools can read these for validation count checks.

### Corpus ingestion
- hytools imports documents into main document collection with `source="nayiri_wa_corpus"` and includes `author`, `publication`, and metadata.
- It does not store `data-store` per-file URL directly (path is stored in `metadata.nayiri.file`).

### Missing data gap check
- `authors.properties` and `publications.properties` are scoped and may not be imported into dedicated collections in hytools currently. The ingestion path maps author/publication IDs to names but does not necessarily keep the complete object stores. If you need complete `Author` and `Publication` records, add a watcher or secondary import to collections.
- `Document` model's all metadata fields are supported by raw text files; hytools should preserve them in metadata but verify no fields are dropped (e.g., yearPublished or scanUrl) depending on `insert_document` implementation.

---

## 5.1 Nayiri Lexicon ↔ hytools mapping
Nayiri schema (raw file) | hytools `nayiri_entries` fields | notes
---|---|---
Root `lexemes[]` | iterated as lexeme objects | lexeme grouped entries
`lexeme.lexemeId` | `lexeme_id` | directly copied
`lexeme.description` | not mapped | gap: human description lost
`lexeme.lemmaType` | not mapped | gap: appears in inflection/lemma only
`lexeme.lemmas[]` | one document per lemma | each lemma upserted as a separate entry
`lemma.lemmaId` | `lemma_id` | directly copied
`lemma.lemmaString` | `headword` | directly copied (canonical form)
`lemma.partOfSpeech` | `part_of_speech` | directly copied
`lemma.lemmaDisplayString` | not mapped | gap: descriptive label lost
`lemma.numWordForms` | not mapped (computed) | gap: stored counts not preserved
`lemma.wordForms[][].s` | `word_forms` (list) | mapped values
`lemma.wordForms[][].i` | used as key to resolve to `inflections` | resolved objects stored
`lexicon.inflections[]` | `inflections_map` -> stored in `inflections` field | global inflection objects attached to each entry via reference ID
`inflection.inflectionId` | by ID resolution only | not persisted as separate table in doc, it's embedded if selected
`inflection.lemmaType` | preserved inside resolved object | yes
`inflection.displayName` | preserved inside resolved object | yes
`inflection.verbalInflectionClass` | preserved inside resolved object | yes (if present)
`inflection.verbPolarity` | preserved inside resolved object | yes
`inflection.verbTense` | preserved inside resolved object | yes
`inflection.verbMood` | preserved inside resolved object | yes
`inflection.grammaticalPerson` | preserved inside resolved object | yes
`inflection.grammaticalNumber` | preserved inside resolved object | yes
`inflection.grammaticalCase` | preserved inside resolved object | yes
`inflection.grammaticalArticle` | preserved inside resolved object | yes
`lexicon.metadata` | `metadata.nayiri_metadata` | entire metadata object is copied as-is (version, license, attribution, publisher, sponsorship, author, contactEmail, website, numLexemes, numLemmas, numWordForms, numInflections)
`lemma.definitions` or `lemma.definition` | `definition` | inserted as string or JSON stringified
Entry-level derived fields | `entry_id` constructed as `nayiri:{lexeme_id}:{lemma_id or hash}` | ensures uniqueness even if lemma_id absent
`content_sha1` | `content_sha1` | SHA-1 of definition text
`metadata.source` | `nayiri` | constant label

### Example (from sample JSON)
- `lexemeId`=4ZXN, `lemmaId`=4ZXN5, `lemmaString`='զսպումն', `partOfSpeech`='NOUN', wordForms ['զսպումէն','զսպումով'], inflections resolved to objects AASA and AACg, and metadata version '2026-02-07-v1'.
- hytools stores in `nayiri_entries` as:
  - `entry_id`='nayiri:4ZXN:4ZXN5'
  - `headword`='զսպումն'
  - `part_of_speech`='NOUN'
  - `word_forms`=['զսպումէն','զսպումով']
  - `inflections`=[{...AASA...},{...AACg...}]
  - `definition` (raw or stringified from `lemma.definitions`)
  - `metadata.nayiri_metadata` includes version/license/publisher, etc.

## 5.2 Nayiri Corpus ↔ hytools mapping
Nayiri corpus raw file metadata | hytools doc `client.insert_document` fields | notes
---|---|---
`id` | stored indirectly via `title` (filename, e.g., JXPzhQ.txt) and potentially text IDs | no explicit field `id` in document, if required can be added round trip
`writtenLanguageVariant` | in `metadata.nayiri.writtenlanguagevariant` | preserved as lower-case key by parser
`publicationId` | looked up in `publications_map`, stored as `publication` top-level and in `metadata.nayiri.publicationid` | `publication` is JSON string from publications.properties or ID fallback
`authorId` | looked up in `authors_map`, stored as `author` top-level and in `metadata.nayiri.authorid` | `author` is JSON string from authors.properties or ID fallback
`yearPublished` | `metadata.nayiri.yearpublished` | preserved string from properties parser
`monthPublished` | `metadata.nayiri.monthpublished` | preserved
`dayPublished` | `metadata.nayiri.daypublished` | preserved
`title` | `metadata.nayiri.title` | preserved
`subTitle` | `metadata.nayiri.subtitle` | preserved
`category` | `metadata.nayiri.category` | preserved
`url` | `metadata.nayiri.url` | preserved
`scanUrl` | `metadata.nayiri.scanurl` | preserved
`isManuallyStemmedAndTokenized` | `metadata.nayiri.ismanuallystemmedandtokenized` | preserved
`usernameCreatedBy` | `metadata.nayiri.usernamecreatedby` | preserved
`creationTime` | `metadata.nayiri.creationtime` | preserved
`usernameLastModifiedBy` | `metadata.nayiri.usernamelastmodifiedby` | preserved
`lastModifiedTime` | `metadata.nayiri.lastmodifiedtime` | preserved
`BEGIN_DOCUMENT_CONTENT` divider | not stored; split content into text body | content is `text` parameter
document content (with NML tags) | `text` | raw annotated content
`file path` per member | `metadata.nayiri.file` | added by code

### Authors Data Store
Nayiri author properties | hytools processing
---|---
`name` | via `authors_map[authorId]`, used as document `author` value when exists
`url` | preserved in JSON string in `authors.properties` value; hytools currently does not parse into separate fields
`yearOfBirth` / `yearOfDeath` / `notes` | preserved in JSON string only, not separated into collection fields

### Publications Data Store
Nayiri publication properties | hytools processing
---|---
`name` | via `publications_map[publicationId]`, used as document `publication` value
`url` | preserved in JSON string value
`location` | preserved in JSON string value
`yearFounded` / `yearCeasedPublication` / `notes` | preserved in JSON string value

## 5.3 Nayiri Markup Language (NML) behavior
- `[[token]]` (explicit token) in corpus text is preserved literally in `text` field.
- `[[wform >>> lemma]]` lemmatization hints remain in `text` field; no parsing to structured tokens in current pipeline.
- `[[wform >>> lemma@POS]]` POS tags remain as raw text; downstream NML parser may be required for structured use.

## 5.4 Observed gaps (needs action)
- `lexeme.description`, `lemmaDisplayString`, and `lemma.numWordForms` are not stored in `nayiri_entries`.
- global lexicon `inflections` are flattened into each lemma as resolved list; because only resolved inflection objects are stored, `inflectionId` is retained only by object content, not by reference list.
- `publication` and `author` references are currently stored as raw JSON strings; not normalized to separate collections by default.
- Document `id` is not mapped to an explicit field in `insert_document`; only filename/title is used.
- Some metadata keys may be lowercased by parser (`writtenLanguageVariant` -> `writtenlanguagevariant`).
- NML markup is preserved as free text in `text`, so functions needing token-level structured NML should parse explicitly in ingest pipeline.

---

## 6. Counts check for verification

From documentation:
- Lexicon: 7,076 lexemes, 7,931 lemmas, 1,491,045 word forms, 709 inflections.
- Corpus: 396 documents, 100 authors, 21 publications, 170,745 tokens.

In your pipeline:
- After lexicon import, verify `db.nayiri_entries.countDocuments()` and compare to lexeme+lemma counts for sanity.
- After corpus import, query `db.documents.countDocuments({source:'nayiri_wa_corpus'})` and `db.authors`, `db.publications` (if added) to verify the numbers.

---

From documentation:
- Lexicon: 7,076 lexemes, 7,931 lemmas, 1,491,045 word forms, 709 inflections.
- Corpus: 396 documents, 100 authors, 21 publications, 170,745 tokens.

In your pipeline:
- After lexicon import, verify `db.nayiri_entries.countDocuments()` and compare to lexeme+lemma counts for sanity.
- After corpus import, query `db.documents.countDocuments({source:'nayiri_wa_corpus'})` and `db.authors`, `db.publications` (if added) to verify the numbers.

---

## 7. Summary and recommendations

- Yes, there is difference `nayiri_entries` (lexicon) vs corpus documents.
- Keep lexicon out of training sets by filtering `source != 'nayiri_wa_corpus'` and/or using dedicated collections.
- For dictionary truth, query `nayiri_entries` and avoid mixed corpus ingestion.
- Consider author/publication collection reads if you need the full metadata.
- Need day-to-day validation code to ensure original counts and missing fields.

---

## 8. Index entry

`docs/INDEX.md` should include:
- `docs/NAYIRI_DOCUMENTATION.md — extracted Nayiri docs, schema, counts, concepts, and pipeline gap analysis`
