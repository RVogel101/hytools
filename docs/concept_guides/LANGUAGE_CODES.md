# Armenian Language Codes (ISO 639 / BCP 47)

Use these codes consistently in `metadata.language_code` and documentation. The pipeline uses them across scrapers (LOC, IA, DPLA, Wikisource, etc.) and in `metadata_tagger`.

| Code | ISO 639 | Usage |
|------|---------|-------|
| **hy**  | 639-1 | General Armenian when dialect is unspecified or undetermined (fallback) |
| **hye** | 639-3 | Eastern Armenian (Republic of Armenia, Iran, Russia, etc.) |
| **hyw** | 639-3 | Western Armenian (diaspora: Lebanon, Turkey, USA, etc.) |
| **hyc** | 639-3 | Classical Armenian (Grabar) — used by classifier and classical-identification rules |
| **eng** | 639-3 | English (for DPLA and mixed WA/English sources) |

**Dialect + language_code conventions**

- Scrapers and `metadata_tagger` set both:
  - `metadata.dialect` ∈ {`western_armenian`, `eastern_armenian`, `mixed`, `unknown`}
  - `metadata.language_code` ∈ {`hyw`, `hye`, `hyc`, `hy`, `eng`, …}
- When the dialect classifier is confident Western: `dialect="western_armenian"`, `language_code="hyw"`.
- When confident Eastern: `dialect="eastern_armenian"`, `language_code="hye"`.
- For clearly classical / liturgical texts: `dialect` variants under `Dialect.CLASSICAL_ARMENIAN`, `language_code="hyc"`.
- When the source only says “Armenian” or is ambiguous: `dialect="unknown"` or best-guess, `language_code="hy"`.
- Non-Armenian but related content (e.g. English DPLA items about Armenia): `language_code="eng"` with appropriate `source_type` / `writing_category`.

**References:** [ISO 639-3](https://iso639-3.sil.org/), [BCP 47](https://www.rfc-editor.org/info/bcp47), [W3C Choosing Language Tags](https://www.w3.org/International/questions/qa-choosing-language-tags).
