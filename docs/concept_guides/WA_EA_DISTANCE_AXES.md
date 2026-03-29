# WA/EA Distance Measurement Axes

This document defines the measurement axes for calculating the quantitative differences between Western Armenian (WA) and Eastern Armenian (EA). Each axis is normalized to a [0..1] scale and contributes to the composite distance index.

## Measurement Axes

### 1. Phonetic Distance
- **Definition**: Measures the differences in pronunciation between WA and EA.
- **Methodology**:
  - Normalize texts to NFC.
  - Convert to IPA using `hytools.linguistics.transliteration.to_ipa`.
  - Compute Levenshtein distance on IPA transcriptions.
  - Aggregate results using mean, standard deviation, median, and percentiles.
- **Deliverable**: `analysis/wa_ea_phonetic_metrics.csv`

### 2. Lexical Distance
- **Definition**: Measures the differences in vocabulary usage between WA and EA.
- **Methodology**:
  - Generate token frequency distributions.
  - Align tokens by lemma or dictionary.
  - Compute shared percentage, Jensen-Shannon divergence, and OOV cross-evaluation.
  - Optionally compute semantic distance using embeddings (e.g., fastText).
- **Deliverable**: `analysis/wa_ea_lexical_metrics.csv`

### 3. Orthographic Distance
- **Definition**: Measures the differences in spelling and orthographic conventions between WA and EA.
- **Methodology**:
  - Apply rule-based conversions (WA → EA and EA → WA).
  - Measure edit distance for converted texts.
  - Compute WA/EAlike token percentages and feature counts for classical vs. reformed markers.
- **Deliverable**: `analysis/wa_ea_orthographic_metrics.csv`

### Orthographic Rule Set

#### Classical vs. Reformed Markers
| Classical | Reformed | Description |
|-----------|----------|-------------|
| **իւ**    | **յու**  | Diphthong (e.g., [ʏ]) |
| **եա**    | **յա**   | Digraph (long /a/ or similar) |
| **ոյ**    | **ու**   | Diphthong oy |
| **եւ**    | **և**    | ew digraph |

#### Methodology for Analysis
1. **Rule-Based Conversion**:
   - Convert classical markers to reformed equivalents and vice versa.
   - Measure edit distance between converted texts.
2. **Token Analysis**:
   - Compute WA/EAlike token percentages.
   - Count occurrences of classical and reformed markers.
3. **Deliverable**:
   - Generate `analysis/wa_ea_orthographic_metrics.csv` with metrics.

## Methodology Documentation

### Overview
This document outlines the methodology for computing the Western Armenian (WA) and Eastern Armenian (EA) distance metrics. The analysis includes three primary axes:

1. **Phonetic Distance**: Measures differences in phonetic transcription and difficulty.
2. **Lexical Distance**: Analyzes the presence of WA-specific lexical markers.
3. **Orthographic Distance**: Compares classical and reformed orthographic patterns.

### Composite Distance Index
The composite distance index is calculated as a weighted sum of the three axes:

- **Phonetic**: 40%
- **Lexical**: 30%
- **Orthographic**: 30%

### Benchmarking
The composite index is benchmarked against predefined thresholds:

- **Low**: < 0.2
- **Medium**: 0.2 - 0.5
- **High**: 0.5 - 0.8
- **Very High**: > 0.8

### Reproducibility
All metrics are serialized to JSON and CSV formats for reproducibility. Scripts are provided for standalone execution.

## Next Steps
- Implement workflows for each axis.
- Validate results against benchmark datasets.
- Combine axes into a composite distance index.