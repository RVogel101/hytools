# Morphological Suffix and Prefix Tracking

## Tracked Suffixes

The `linguistics.metrics.text_metrics` module tracks suffixes in `MorphologicalMetrics`:

| Suffix | Armenian | Role | Dialect Signal |
|--------|----------|------|----------------|
| -եմ | em | Western 1st singular present | Western (e.g. բերեմ "I bring") |
| -իմ | im | Possessive "my" (pre-noun) | Western — not verb suffix; իմ = "my" |
| -ում | um | Eastern imperfective/present | Eastern (e.g. բերում եմ "I bring"); not used in Western |
| -ան | an | Various (plural, 3rd person) | Shared |
| -ել | el | Infinitive | Shared (e.g. գրել "to write") |
| -իլ | il | Infinitive (passive verb form) | Western only (e.g. խօսիլ "to speak") |

**Dialect notes:**
- In **Eastern** Armenian, "I bring" = բերում եմ (berum yem).
- In **Western** Armenian, "I bring" = բերեմ (berem).
- -իմ in Western means "my" (possessive, can be dropped when implied); not a 1st singular verb ending.
- -ում is Eastern; Western uses **կոր** (gor) for present continuous (e.g. with կը/կ՚).
- -իլ is Western-only infinitive; -ել is shared.

**Value of these statistics:** The ratio of -եմ (WA) vs -ում (EA) is a dialect marker. -իլ presence indicates Western Armenian. -իմ as word-final on verbs was a misclassification; in correct WA, -իմ is possessive "my".

## Tracked Prefixes

Prefixes are tracked when `compute_metrics_on_ingest` or morphological analysis is enabled:

| Prefix | Armenian | Romanization | Role | Dialect |
|--------|----------|--------------|------|---------|
| կը | gu | gu | Present tense marker | Western |
| կ՚ | g' | g' | Elided before vowel | Western |
| պիտի | bidi | bidi | Future marker | Western |
| չ | ch | ch | Negative (word-initial) | Western |

See `linguistics.metrics.text_metrics.MorphologicalMetrics` and `scraping._helpers` for implementation.

## Use in WesternArmenianLLM Training

Functions suitable for import in WesternArmenianLLM:

- **`linguistics.metrics.text_metrics.QuantitativeLinguisticsAnalyzer`** — Full metric card (lexical, syntactic, morphological, orthographic, contamination, quality).
- **`linguistics.metrics.text_metrics.TextMetricCard`**, **`MorphologicalMetrics`** — Dataclasses for structured metrics.
- **`linguistics.metrics.validate_augmentation_output`** — Validate WA output (used by Phase 1 SafeAugmentationWrapper).
- **`linguistics.metrics.vocabulary_filter.WesternArmenianVocabularyFilter`** — Eastern vocabulary detection.
- **`cleaning.language_filter.is_western_armenian`**, **`compute_wa_score`** — WA classification.
