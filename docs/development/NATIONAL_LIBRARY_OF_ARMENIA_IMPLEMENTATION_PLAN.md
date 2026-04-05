# National Library of Armenia Integration Plan

## Goal

Integrate the National Library of Armenia (NLA) into hytools in a way that is technically reliable, operationally polite, and legally conservative.

The phrase "pull their whole database of digital records" should be treated as two separate acquisition problems:

1. The NLA digital repository on DSpace, where public metadata and public file links are exposed.
2. The NLA-linked Koha catalog properties, which are bibliographic discovery systems and, in some cases, union catalogs that include many institutions beyond NLA itself.

The recommended plan is to treat the DSpace repository as the primary automation target and to treat the Koha properties as metadata-seeding or permission-gated targets.

---

## Verified Surface Map

### 1. Main NLA site

- Site: `https://nla.am/en_US`
- Verified links from the main site point to:
  - `https://armunicat.nla.am`
  - `https://haygirk.nla.am`
  - `https://tert.nla.am`
  - `https://dspace.nla.am`
- Public contact details on the site include `+37460 623513/0` and `armnationallibrary@gmail.com`.

### 2. Digital repository

- UI: `https://dspace.nla.am`
- Backend: `https://api.nla.am/server`
- Verified backend root: `https://api.nla.am/server/api`
- Reported software/version at the API root: `DSpace 7.3`

### 3. Public DSpace endpoints confirmed during research

- `GET https://api.nla.am/server/api`
  - Public root endpoint listing available REST resources.
- `GET https://api.nla.am/server/api/discover/search/objects?query=*`
  - Public search/discovery endpoint.
  - Returned paginated embedded item metadata.
  - Returned `totalElements: 13072`, `totalPages: 654`, `size: 20` in this research session.
- `GET https://api.nla.am/server/api/core/communities`
  - Public community listing.
  - Returned `totalElements: 39`.
- `GET https://api.nla.am/server/api/core/collections`
  - Public collection listing.
  - Returned `totalElements: 65`.
- `GET https://api.nla.am/server/opensearch/search?format=atom&query=*`
  - Public Atom feed.
  - Returned `opensearch:totalResults` of `12968` in this research session.

### 4. Public item/file behavior confirmed during research

- Example public item page:
  - `https://dspace.nla.am/handle/123456789/6062`
- Verified on that public page:
  - file listing
  - direct download link
  - file size
  - author, publisher, abstract, description, subject, URI, collection
- Example file exposed on the page:
  - `abs772_simonyan-simoni_ocr.pdf (8.96 MB)`

### 5. OAI-PMH behavior

- `GET https://api.nla.am/server/oai/request?verb=Identify`
  - Works.
  - Reports repository name `DSpace NLA`.
  - Reports protocol `2.0`.
  - Reports earliest registered date `2022-08-03 06:22:13`.
- `GET https://api.nla.am/server/oai/request?verb=ListMetadataFormats`
  - Works.
  - Exposes multiple metadata formats including `oai_dc`, `marc`, `mods`, `ore`, `mets`, `dim`, `xoai`, `qdc`, `etdms`, `didl`, `rdf`, `uketd_dc`.
- `GET https://api.nla.am/server/oai/request?verb=ListSets`
  - Works.
  - Exposes 14 sets, including `National Library of Armenia`, `NLA Publications`, `Dissertation`, `Thesis`, `Armenian Book`, `Periodicals Yearbook`.
- `ListIdentifiers` and `ListRecords` requests returned `No matches for the query` during this research session, both unscoped and scoped.

Conclusion: OAI-PMH is present but should not be treated as operational for harvesting until NLA confirms the intended endpoint, indexing state, and supported harvesting workflow.

### 6. DSpace rights/access signals observed

- The public discover endpoint exposes a `has_content_in_original_bundle` facet.
- In this research session it returned:
  - `true: 12965`
  - `false: 3`
- Some DSpace communities expose explicit open-access signals in metadata:
  - `Theses & Abstracts` community includes `dc.rights = Open access`.
  - `NLA Publications` community includes `dc.rights = Open access`.
  - `Bulletin of Armenian Libraries` description states that the whole content is publicly available.

### 7. Koha properties linked by NLA

- Union catalog: `https://armunicat.nla.am`
  - Koha-based.
  - Aggregates many Armenian libraries, not just NLA.
- Armenian Book: `https://haygirk.nla.am`
  - Koha-based.
  - Bibliographic database for Armenian and Armenian-related books.
  - Says materials may be used for personal, academic, and informational purposes with mandatory reference to NLA databases.
  - Says a digital copy is available when a record has a `Read Online` link.
- Continuing Resources: `https://tert.nla.am`
  - Koha-based.
  - Union catalog of Armenian continuing resources from 1794 to the present.
  - Says issues are available digitally under `Read Online` when present.

### 8. Robots and crawl-policy signals

- `https://nla.am/robots.txt`
  - Essentially open / empty.
- `https://dspace.nla.am/robots.txt`
  - DSpace default robots policy.
  - Disallows `/search`, `/browse/*`, `/statistics`, and various user/admin paths.
  - Includes warnings against aggressive site-copying and recursive download behavior.
- `https://tert.nla.am/robots.txt`
  - Explicitly disallows `curl`, `wget`, `python-requests`, many AI bots, and `User-agent: *`.
  - This should be treated as a hard stop for automated harvesting there.
- `https://armunicat.nla.am/robots.txt` and `https://haygirk.nla.am/robots.txt`
  - Publish rights-oriented content-signal text in robots.
  - Because those signals were not fully machine-readable in this research pass, do not assume permission for automated collection beyond ordinary human browsing.

### 9. Policy quality caveat

- `https://dspace.nla.am/info/end-user-agreement`
  - Returned placeholder lorem ipsum text.
- `https://dspace.nla.am/info/privacy`
  - Returned placeholder lorem ipsum text.

Conclusion: do not treat the DSpace UI legal pages as authoritative policy text. Use written permission from NLA for any bulk bitstream acquisition.

---

## Recommended Acquisition Boundary

### Safe first target

Automate against the NLA DSpace backend only:

- `api.nla.am/server/api/discover/search/objects`
- `api.nla.am/server/api/core/communities`
- `api.nla.am/server/api/core/collections`
- public item pages and public bitstream links only where rights are explicit or permission is granted

### Use with caution

- `api.nla.am/server/oai/request`
  - Keep as an optional future path, not the primary implementation, until NLA confirms why record listing currently returns no matches.
- `api.nla.am/server/opensearch/search`
  - Useful as a fallback enumerator or validation path.

### Do not automate in phase one

- `armunicat.nla.am`
  - It is a union catalog across multiple institutions.
- `haygirk.nla.am`
  - It is a bibliographic database with some digital-copy links, but no verified public bulk API.
- `tert.nla.am`
  - Robots policy explicitly disallows broad automated access.

### Out of scope for this first implementation plan

- Separate deep reverse-engineering of `haygirk.nla.am` digital-copy linkage patterns.
- Separate periodical-download workflow for `tert.nla.am`.
- Any attempt to mirror all Koha-backed records or all union-catalog entries.

---

## Recommended Permission Stance

Even though the DSpace metadata endpoints are public, a full-database pull should still begin with a written permission request to NLA.

Ask NLA to confirm all of the following:

1. Whether automated metadata harvesting from `api.nla.am/server` is allowed for research.
2. Whether bulk bitstream download is allowed for communities marked `Open access`.
3. Whether there is a preferred bulk export format such as MARCXML, MODS, DIM, CSV, or a database dump.
4. Whether OAI-PMH is intended to be publicly harvestable and, if so, which metadataPrefix and set strategy should be used.
5. Whether the Koha properties may be harvested programmatically at all, or should only be used interactively.
6. Whether NLA wants a dedicated user agent string, contact email, IP allowlist, or crawl schedule.
7. Whether NLA can provide a separate list of communities or collections that are fully open for downstream research reuse.

---

## Recommended Technical Strategy

### Primary strategy: metadata-first DSpace harvest

Use the DSpace discover API as the canonical enumerator.

Why:

- It is publicly accessible without login.
- It returns embedded item metadata.
- It returns pagination data and facets.
- It exposes links to the underlying item, bundles, thumbnails, and owning collection.
- In this research session, direct `core/items` listing returned 401 while `discover/search/objects` worked anonymously.

### Secondary strategy: public file backfill

After metadata harvest, follow item links to determine whether a file should be downloaded.

For each discovered item:

1. Persist the embedded metadata from the discover endpoint.
2. Follow `indexableObject.self` for the canonical item URI.
3. Follow `owningCollection` and `accessStatus`.
4. Follow `bundles` and only process original bitstreams when either:
   - the collection/community is explicitly open access, or
   - NLA has granted written permission.
5. Store the bitstream URL, name, size, MIME type, checksum if available, and rights signal.

### Fallback strategy: Atom feed validation

Use `server/opensearch/search?format=atom&query=*` to validate high-level counts and to cross-check whether discover pagination missed anything.

### Optional future strategy: OAI after manual confirmation

Only switch to OAI-PMH as the main harvester after one of these is true:

- NLA confirms the correct OAI base URL and harvest method.
- NLA fixes the current `No matches for the query` behavior.
- A manual validation run returns real records from `ListIdentifiers` or `ListRecords`.

---

## Hytools Implementation Plan

### Proposed files

- `hytools/ingestion/acquisition/nla.py`
- `tests/test_nla.py`
- Optional later split if scope grows:
  - `hytools/ingestion/acquisition/nla_dspace.py`
  - `hytools/ingestion/acquisition/nla_catalog.py`

### Proposed config block

```yaml
scraping:
  nla:
    enabled: false
    ui_base_url: https://dspace.nla.am
    api_base_url: https://api.nla.am/server
    metadata_mode: discover
    metadata_only: true
    require_explicit_open_access: true
    allow_bitstreams: false
    page_size: 20
    requests_per_second: 0.5
    max_concurrency: 1
    retry_backoff_seconds: [5, 15, 60, 300]
    checkpoint_path: data/retrieval/nla_checkpoint.json
    include_community_handles: []
    include_collection_handles: []
    contact_email: armnationallibrary@gmail.com
    user_agent: hytools NLA harvester (research contact required)
```

### Proposed source identifiers

- `source = nla_dspace`
- `source_detail = nla_dspace_discover`
- Optional future values:
  - `nla_haygirk`
  - `nla_tert`
  - `nla_armunicat`

### Metadata fields to persist

- DSpace UUID
- Handle
- Item URL
- Community UUID / handle / title
- Collection UUID / handle / title
- `dc.title`
- `dc.contributor.author`
- `dc.date.issued`
- `dc.date.accessioned`
- `dc.language.iso`
- `dc.subject`
- `dc.description`
- `dc.description.abstract`
- `dc.rights`
- `dc.identifier.uri`
- `dc.publisher`
- `lastModified`
- `inArchive`
- `discoverable`
- `withdrawn`
- `has_content_in_original_bundle`
- `accessStatus`
- bitstream metadata when allowed

### Recommended ingestion flow

#### Step 1: topology sync

- Enumerate communities from `api/core/communities`.
- Enumerate collections from `api/core/collections`.
- Build a local map of community UUID -> handle/title and collection UUID -> handle/title.
- Mark communities with explicit `dc.rights = Open access`.

#### Step 2: page through discover results

- Iterate `api/discover/search/objects?query=*` page by page.
- Persist the raw embedded item metadata immediately.
- Save checkpoints after every page.
- Capture total counts from the page block for auditability.

#### Step 3: enrich each item

- Follow `indexableObject.self`.
- Follow `owningCollection` and `accessStatus`.
- Resolve bundle links only when a file backfill is allowed.

#### Step 4: selective bitstream download

- Default behavior: do not download bitstreams unless the target collection is explicitly approved.
- When allowed:
  - prefer original PDF / image / archive objects
  - store filename, size, MIME type, URL, and retrieval timestamp
  - hash the payload after download for dedupe and resume

#### Step 5: incremental refresh

- Use `lastModified` and `dc.date.accessioned` for change detection.
- Re-run metadata sync first.
- Only revisit item details when the stored metadata hash or lastModified value changes.

---

## Courtesy Rules for a Full-Dataset Pull

The implementation should assume that NLA is a public-memory institution, not a commodity web source.

### Default courtesy profile

- 1 metadata request at a time
- 0.5 requests/second baseline
- 5-10 seconds between bitstream downloads
- immediate backoff on 429, 403, 500, 502, 503, 504
- automatic pause after repeated server errors
- checkpoint every page and every downloaded file
- identify the harvester with a real contact email

### Escalation rules

- If NLA responds and gives stricter limits, their limits override this plan.
- If NLA gives a bulk export, prefer that over crawling.
- If NLA asks for off-hours harvest windows, schedule them.
- If NLA asks for metadata-only ingest, keep file download disabled.

### Avoid these behaviors

- Do not recursively mirror the DSpace UI.
- Do not crawl `/search` or `/browse/*` on the DSpace UI, because robots disallows them.
- Do not use `wget --mirror` or equivalent.
- Do not bulk-harvest `tert.nla.am`.
- Do not bulk-harvest `armunicat.nla.am` as if it were NLA-only content.
- Do not assume placeholder DSpace policy pages equal consent for bulk download.

---

## Phased Rollout

### Phase 0: permission and validation

- Send NLA a research-access request.
- Confirm allowed surfaces, rates, and reuse scope.
- Run a 100-item metadata-only dry run.

### Phase 1: DSpace metadata sync

- Ship a metadata-only `nla` acquisition stage.
- Persist community, collection, and item topology.
- Add a dashboard/audit summary with counts by community, language, subject, and file availability.

### Phase 2: rights-aware bitstream backfill

- Enable downloads only for explicitly approved communities.
- Start with communities that expose `Open access`.
- Add resume, checksum, and file-verification support.

### Phase 3: Koha-assisted seeding

- If NLA approves it, use `haygirk` and `armunicat` only for bibliographic enrichment, missing-item discovery, and targeted follow-up.
- Keep them out of the default crawler path.

### Phase 4: OAI reassessment

- Re-test OAI-PMH after NLA feedback.
- If functional, compare discover-vs-OAI completeness and performance.
- Switch to OAI only if it is both permitted and operationally better.

---

## Risks and Open Questions

### Verified risks

- OAI appears partially exposed but not currently yielding records.
- Direct `api/core/items` listing was not consistently anonymously readable in this research pass.
- DSpace legal pages are placeholders, so they do not provide trustworthy reuse guidance.
- Koha properties are not equivalent to a public bulk-download API.
- The union catalog includes many non-NLA institutions and therefore raises ownership and permission questions.

### Questions to resolve with NLA

1. Is `api.nla.am/server/api/discover/search/objects` approved for full metadata harvest?
2. Which communities are officially open for bulk file download?
3. Is there a preferred export mechanism instead of API crawling?
4. Why does OAI return metadata formats and sets but no records?
5. Are `haygirk` and `armunicat` allowed for programmatic metadata collection?
6. Is `tert.nla.am` intentionally closed to automated agents?

---

## Recommended Decision

Proceed with an NLA DSpace integration plan, but do it in this order:

1. Ask permission for a research harvester and for bulk file access.
2. Build a metadata-first DSpace stage around `discover/search/objects`, `core/communities`, and `core/collections`.
3. Restrict file download to explicit open-access communities or written approval.
4. Treat Koha properties as separate projects, not part of the first full-database pull.
5. Treat OAI as a future optimization, not a current dependency.

This is the lowest-risk path that still gives hytools a real, scalable way to ingest NLA digital records.