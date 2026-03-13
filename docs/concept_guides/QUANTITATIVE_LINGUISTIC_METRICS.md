# Quantitative Linguistic Metrics for Comparative Analysis

## Standard Metrics for Dialect/Variant Comparison

### 1. LEXICAL DIVERSITY & RICHNESS

#### Type-Token Ratio (TTR)
- **What it measures**: Vocabulary richness / diversity
- **Formula**: Total unique words / Total words
- **Range**: 0-1 (higher = more diverse)
- **Use case**: Detect if a text uses repetitive vocabulary (potential indicator of Eastern vs Western)
- **Implementation**: `unique_tokens / total_tokens`
- **Limitation**: Decreases with text length (use normalized versions for comparisons)

#### Standardized Type-Token Ratio (STTR)
- **What it measures**: TTR normalized for text length
- **Formula**: Calculates TTR over consecutive 100-token windows, then averages
- **Use case**: Compare vocabularies of texts of different lengths
- **Better than**: Raw TTR for comparison across variable-length texts

#### Yule's K Measure
- **What it measures**: Vocabulary repetitiveness
- **Formula**: K = 10,000 × (V₁ - V₂) / N²
  - V₁ = sum of (frequency × frequency)
  - V₂ = number of unique words
- **Range**: Lower values = more repetitive
- **Use case**: Dialect signature detection (some dialects repeat constructions more)

#### Honore's Statistic (H)
- **What it measures**: Vocabulary richness accounting for frequency distribution
- **Better for**: Longer texts where TTR becomes unreliable
- **Formula**: H = 100 × log(N) / (1 - V₁/V)

### 2. SYNTACTIC COMPLEXITY METRICS

#### Average Sentence Length (ASL)
- **What it measures**: Syntactic complexity indicator
- **Formula**: Total words / Total sentences
- **Use case**: Detect stylistic differences between dialects
- **Range**: Typically 15-25 words in standard texts
- **Limitation**: Dialects may naturally have different pacing

#### Clause Count / Clauses per Sentence
- **What it measures**: Syntactic richness
- **Formula**: Total clauses / Total sentences
- **Use case**: Detect if dialect prefers simple vs complex sentence structures

#### Flesch-Kincaid Grade Level
- **What it measures**: Text readability/complexity
- **Formula**: 0.39 × (words/sentences) + 11.8 × (syllables/words) - 15.59
- **Use case**: Compare formal vs informal register between dialects

### 3. MORPHOLOGICAL METRICS

#### Affix Frequency Analysis
- **What it measures**: Usage patterns of prefixes/suffixes
- **Implementation**: Count morphological markers per word
- **Use case**: Critical for Western vs Eastern Armenian
  - Eastern: uses -եմ suffix for 1st singular, Western: -իմ
  - Track frequency of specific morphological patterns
- **Example**:
  - Suffix -եմ frequency (Eastern marker)
  - Suffix -իմ frequency (Western marker)
  - Suffix -ում frequency (shared but different contexts)

#### Morpheme Richness
- **What it measures**: How many different morphemes in text
- **Use case**: Detect if dialect uses richer morphological variation

### 4. PHONOMETRIC/ORTHOGRAPHIC METRICS

#### Character N-gram Frequency
- **What it measures**: Common character sequences
- **Use case**: Detect orthographic patterns (classical vs reformed)
  - Western Armenian retains: եա, իւ, ո, ե
  - Eastern reformed: removed some combinations
- **Implementation**: Track 2-3 character sequences

#### Grapheme (Letter) Frequency Distribution
- **What it measures**: Which letters appear most often
- **Use case**: Orthographic signatures
  - Different dialects may show different letter frequencies
- **Implementation**: Simple frequency count of each Armenian letter

### 5. SEMANTIC/VOCABULARY METRICS

#### Cosine Similarity (Vector Space Model)
- **What it measures**: Semantic similarity between texts
- **Formula**: cos(θ) = (A·B) / (|A| × |B|)
- **Use case**: Compare if two texts are semantically similar
- **Range**: 0-1 (1 = identical, 0 = unrelated)
- **Implementation**: TF-IDF vectors or word embeddings

#### Euclidean Distance
- **What it measures**: Distance between texts in semantic space
- **Use case**: Cluster detection (which texts are similar?)
- **Range**: Higher = more different

#### Kullback-Leibler (KL) Divergence
- **What it measures**: How different two probability distributions are
- **Use case**: Compare word frequency distributions between dialects
- **Range**: 0 = identical distributions, higher = more different
- **Formula**: KL(P||Q) = Σ P(x) × log(P(x) / Q(x))

#### Levenshtein Distance
- **What it measures**: Minimum edits to transform one string to another
- **Use case**: Compare variant word forms
  - Example: distance between "բերեմ" and "բերիմ"
- **Range**: 0 = identical, higher = more different

### 6. DISCOURSE/PRAGMATIC METRICS

#### Lexical Cohesion Score
- **What it measures**: How well vocabulary connects across sentences
- **Use case**: Detect discourse style differences
- **Implementation**: Count word repetitions, synonyms across sentences

#### Pronoun Frequency
- **What it measures**: Pronoun usage patterns
- **Use case**: Some dialects prefer more/fewer pronouns
- **Track**: հն (he), նա (she), ես (I), դուք (you formal) frequencies

#### Transitivity Score
- **What it measures**: Distribution of transitive vs intransitive verbs
- **Use case**: Detect action-oriented vs state-oriented discourse
- **Implementation**: Manual or dictionary-based verb classification

### 7. INFORMATION THEORY METRICS (ENTROPY)

#### Shannon Entropy (H)
- **What it measures**: Linguistic unpredictability/diversity
- **Formula**: H = -Σ p(x) × log₂(p(x))
- **Range**: Higher = more unpredictable/diverse
- **Use case**: Compare how "random" vs "formulaic" each dialect is

#### Perplexity
- **What it measures**: How well a language model predicts text
- **Formula**: PP = 2^(-1/N ∑ log₂ P(w_i))
- **Use case**: If WA model, how much does EA text perplex it?
- **Interpretation**: Low perplexity = well-predicted (likely from training distribution)

### 8. STATISTICAL COMPARISON METRICS

#### Chi-Square Test (χ²)
- **What it measures**: Difference between observed and expected frequencies
- **Use case**: Is frequency distribution significantly different?
- **Example**: Test if verb suffix frequencies differ between dialects
- **Output**: p-value (< 0.05 = significant difference)

#### T-Test
- **What it measures**: Significant difference between two mean values
- **Use case**: Compare mean sentence length, TTR between dialects
- **Output**: p-value (< 0.05 = significant difference)

#### Fisher's Exact Test
- **What it measures**: Significance of associations in 2x2 tables
- **Use case**: Is a word/feature significantly more Eastern or Western?

### 9. DIALECT-SPECIFIC METRICS

#### Phonetic Distance
- **What it measures**: How different pronunciations are
- **Formula**: Edit distance on phoneme sequences
- **Use case**: Detect if orthographic variation signals phonetic difference
- **Relevant for**: Armenian where orthography ≠ pronunciation

#### Code-Switching Index
- **What it measures**: How much text mixes dialects
- **Formula**: (# of dialect-marked words) / Total words
- **Use case**: Detect dialect mixing or contamination
- **For you**: Track -եմ vs -իմ ratio as mixing indicator

#### Variant Ratio
- **What it measures**: Ratio of variant word forms
- **Formula**: (Count of Eastern form) / ((Eastern form + Western form))
- **Use case**: Track contamination level
- **Example**: `(eastern_variant_count) / (eastern_variant_count + western_variant_count)`

#### Dialect Orthographic Expansion Delta (NEW)
- **What it measures**: How much longer one dialect spelling is for the same lemma.
- **Formula**: `letter_delta = len(eastern_form) - len(western_form)`
- **Use case**: Quantify Soviet reform-driven expansion/compression for aligned word pairs.
- **Examples**:
  - Pair-level: apply `letter_delta` to each aligned WA/EA variant pair
  - Corpus-level: mean/median `letter_delta` over all aligned variant pairs
- **Interpretation**:
  - Positive delta: Eastern form tends to use more letters
  - Negative delta: Western form tends to use more letters
  - Near zero: no systematic expansion difference

#### Dialect Whitespace Load Delta (NEW)
- **What it measures**: Change in spacing burden between equivalent dialect forms.
- **Formula**: `space_delta = spaces(eastern_form) - spaces(western_form)`
  - Where `spaces(x)` counts literal space characters in a multi-token form.
- **Use case**: Capture analytic constructions that introduce extra spacing in one dialect.
- **Examples**:
  - `"բերել ես"` vs `"բերեցի"` gives positive `space_delta` for Eastern analytical form
  - Pair-level and corpus-level aggregation over aligned equivalents
- **Interpretation**:
  - Positive delta: Eastern equivalent is more space-heavy
  - Negative delta: Western equivalent is more space-heavy
  - Combined with `letter_delta`, gives a compact orthographic load profile

#### Orthographic Load Index (NEW)
- **What it measures**: Combined impact of letter and whitespace expansion.
- **Formula**: `orthographic_load = alpha * letter_delta + beta * space_delta`
- **Default weights**: `alpha=1.0`, `beta=2.0` (space changes weighted higher)
- **Use case**: Single scalar feature for model input and drift tracking dashboards.
- **Note**: Tune `alpha`/`beta` empirically against downstream task quality.

### 10. DISTRIBUTIONAL SEMANTIC METRICS

#### Word Embedding Distance
- **What it measures**: Semantic distance in learned vector space
- **Libraries**: Word2Vec, GloVe, FastText
- **Use case**: Detect if Eastern and Western versions are semantically distant
- **Range**: 0-2 (lower = closer meaning)

#### Similarity-based Measures
- **Jaccard Similarity**: |A ∩ B| / |A ∪ B|
  - Useful for comparing vocabulary overlap between texts
  - Range: 0-1 (1 = identical sets)
  
- **Dice Coefficient**: 2|A ∩ B| / (|A| + |B|)
  - Similar to Jaccard but gives more weight to overlap

---

## RECOMMENDED METRICS FOR YOUR SYSTEM

### For Text-Level Tracking

**Core metrics** (compute for every augmented text):

1. **TTR / STTR** - Vocabulary richness fingerprint
2. **Average Sentence Length** - Syntactic style
3. **Morphological Suffix Frequencies**:
   - Count of -եմ forms (Eastern marker)
   - Count of -իմ forms (Western marker)
   - Other key suffixes (-ում, -ան, etc.)
4. **Orthographic Pattern Frequencies**:
   - Classical (ո, ե, իւ, եա) vs Reformed markers
5. **Pronoun Distribution** - Pragmatic style
6. **Entropy Score** - Unpredictability/diversity
7. **Dialect Orthographic Expansion Delta** - Letter-count difference for equivalent forms
8. **Dialect Whitespace Load Delta** - Space-count difference for equivalent forms
9. **Orthographic Load Index** - Weighted combined letter+space expansion score

**Advanced metrics** (optional, for comparative analysis):

10. **KL Divergence from WA baseline** - How far from standard WA
11. **Perplexity on WA language model** - Model confidence
12. **Code-switching Index** - Dialect purity
13. **Levenshtein Distance** between original and augmented - How much changed

### For Batch/Corpus-Level Tracking

1. **Distribution statistics** of all above metrics across batch
2. **Chi-square tests** comparing variant frequencies to baseline
3. **Cluster analysis** - Which texts group together?
4. **Entropy trends** - Is augmentation increasing diversity?

---

## IMPLEMENTATION NOTES

### Libraries to Use

- **NLTK**: Sentence/word tokenization, basic metrics
- **Stanza/spaCy**: More sophisticated tokenization, POS tagging
- **Scikit-learn**: TF-IDF, cosine similarity, chi-square tests
- **SciPy**: Statistical tests (t-test, chi-square, etc.)
- **NumPy/Pandas**: Numerical computation, data aggregation
- **TFIDF/Gensim**: Semantic similarity metrics
- **Regex**: Character/grapheme analysis

### Normalization Considerations

For comparing across different text lengths:
- Use STTR instead of TTR
- Use per-1000-word frequencies
- Use proportional metrics (ratios) rather than absolute counts
- Consider log normalization for skewed distributions

### Baseline Establishment

Before tracking changes:
1. Compute all metrics on clean WA corpus snapshot
2. Store as baseline statistics (mean, std dev, min, max)
3. Flag texts that deviate from baseline as potential issues
4. Track baseline drift over time (as corpus grows)

---

## FUTURE FEATURE EXTRACTION IDEAS (COMPREHENSIVE GUIDE)

### Pair-Aligned Dialect Features

These features compare **equivalent word/phrase pairs** across Western Armenian (WA) and Eastern Armenian (EA) to quantify structural differences. They enable detailed analysis of how dialects systematically differ in encoding the same meaning.

#### Core Pair-Aligned Metrics

**`letter_delta`** (character count difference)
- Measures how many more or fewer characters one dialect uses vs the other
- Example: WA "միասին" (6 chars) vs EA "միայն" (4 chars) = delta of -2
- Applied per pair across lexicon; aggregated by source domain
- Reveals systematic compression patterns

**`space_delta`** (token boundary differences)
- Differences in how many spaces appear in equivalent multi-word phrases
- Useful for measuring whether dialects segment text differently
- Example: compare aligned multi-word equivalents and count literal spaces on each side
- Helps detect spacing conventions that differ per dialect/domain

**`orthographic_load`** (encoding density)
- Quantifies letters needed to express same semantic content
- High in WA (classical orthography preserves archaic letters: իւ, եա, մեջ)
- Lower in EA (Soviet reforms simplified forms, including `իւ` removal and `եա→յա` in many contexts)
- Aggregated per source to detect encoding complexity by corpus type

#### Advanced Pair Features

**Directionality indicators**
- `% pairs where Eastern is longer`: directional bias in compression
- `% pairs where Eastern is more spaced`: segmentation tendency
- Helps detect asymmetric patterns (e.g., WA consistently shorter)

**Robust aggregation statistics**
- Rather than simple mean, use:
  - Trimmed mean (removes top/bottom 5% outliers)
  - IQR (interquartile range) for spread without heavy influence of single long words
  - Percentile bands (10th, 25th, 50th, 75th, 90th) for distribution shape
- Reduces impact of outlier pairs (e.g., single very long classical word)

---

### Character Geometry & Rendering Cost Proxies

These features model **visual/computational properties** of written characters—directly applicable to OCR contexts, rendering difficulty, and character-level ML models.

#### Glyph Complexity Approximation

**Stroke count proxy**
- Armenian letters have varying visual complexity (e.g., Ա has ~3 strokes, Ե has ~2)
- Can approximate by:
  - Manual lookup table of stroke counts per letter
  - Proxy: number of connected components (e.g., Ո appears as two parts)
  - Weighted by frequency of letter in corpus
- **Utility**: Explains OCR misrecognition rates; predicts model attention patterns

**Width/density class**
- Classify letters as: narrow (ի, ւ), medium (ա, ե), wide (Ո, Վ, etc.)
- Compute average width of equivalent forms
- Affects line-breaking, font rendering, and token boundary detection

#### Visual Encoding Metrics

**`visual_density_delta`** (visual weight comparison)
- Compares "visual weight" (complexity × frequency) between equivalent forms
- May explain why one form is easier to print/scan/recognize
- Example: Dense ligatures (իւ as single glyph) vs decomposed sequences (ի + ւ)
- Correlates with: OCR confidence scores, font rendering cost, tokenization stability

**Punctuation adjacency patterns**
- Measures how tightly punctuation clusters around tokens
- Different dialects may use punctuation differently within/after words
- High adjacency → harder segmentation zones for tokenizers
- Useful for preprocessing robustness analysis

**Token boundary density**
- How tightly packed words are: character spacing per word
- Cramped typography (low spacing) → harder for segmentation models
- Spaced typography (high spacing) → clearer but more bytes
- Impacts both OCR and downstream NLP pipeline robustness

---

### Phonology-Orthography Alignment Features

These features model **how well the written form maps to sound**. Critical for WA because it preserves classical spelling that often doesn't match modern pronunciation—unlike EA's simplified reform orthography.

#### Grapheme-to-Phoneme Mappings

- Build approximations of grapheme→phoneme correspondence per dialect
- WA example: իւ (digraph) → /iv/ or /u/ depending on morphological context
- EA example: reform removed իւ digraph entirely, substituting shorter sequences
- Track which letters have **multiple pronunciations** (allophonic variation)

**`phonetic_efficiency` score**
- Measures how "directly" spelling maps to sound
- **WA patterns**: Lower efficiency
  - More silent letters (archaic spellings)
  - Classical digraphs (ease of sound but longer encoding)
  - Context-dependent pronunciation
- **EA patterns**: Higher efficiency
  - Soviet simplified orthography matches pronunciation more directly
  - Removed/reformed ambiguous digraphs
- **Use case**: Detect when WA spelling is "less efficient" but more culturally authentic

#### Diphthong & Vowel Patterns

**Diphthong preservation vs decomposition**
- WA retains classical diphthongs: "-այ", "-օյ" (word-final)
- EA often decomposes: -այ→-ա-ե? or reforms them
- Binary feature per word: `preserved=1, decomposed=0`
- Aggregate across text: % of classically preserved diphthongs

**Silent/weak-vowel insertion**
- Tracks epenthetic vowels inserted in morpheme boundaries
- Example: genitive constructions may insert schwa in WA but not EA
- Affects letter-count metrics; indicates morpho-phonological differences
- Useful for morphological variant analysis

---

### Morphosyntactic Variant Features

These features capture **grammatical micro-variations** at the inflectional level—where WA and EA most differ beyond vocabulary.

#### Synthesis vs Analyticity Indicators

**Tense/aspect encoding patterns**
- WA: synthetic present tense via prefix `կը + verb` (one token)
- EA: analytical forms via auxiliary `verb + ով` or other particles (2+ tokens)
- **`token_count_delta`**: Count tokens in equivalent verb phrases
  - If WA uses prefixes: lower token count
  - If EA uses auxiliaries: higher token count
- Aggregated: `average delta per phrase pair`
- **Use case**: Detect analytic vs synthetic language change over dialect/time

#### Suffix Variation & Entropy

**Variant affix entropy by POS class**
- For verbs: measure diversity of "-եմ", "-իմ", "-ում" endings
- Entropy = -Σ(p_i × log(p_i)) where p_i = frequency of ending i
- **High entropy**: Many different endings used (WA diversity)
- **Low entropy**: Few standard forms (EA standardization)
- Computed per POS class to detect if noun vs verb affixation differs

**Per-POS frequency tables**
- Store: `{pos_class: {ending: count}}`
- Compare distributions: Kolmogorov-Smirnov test or chi-squared
- Flag if dialect significantly favors one ending over others

#### Agreement & Case Marking

**Agreement-marker divergence score**
- Person/number endings shift differently across dialects
- Example: 3rd person plural past tense markers differ systematically
- Measure: Jensen-Shannon divergence between ending distributions
- High divergence = strong grammatical difference

#### Brainstorm: Quantitative Grammar Difference (Grounded in Existing Research)

This subsection extends the project's already-implemented grammar signals into a more explicit research plan for WA/EA grammatical distance.

**Current research baseline already available in this repo**
- `src/augmentation/text_metrics.py`: suffix frequency features (`-եմ`, `-իմ`, `-ում`, `-ան`, `-ել`)
- `src/augmentation/dialect_clustering.py`: `em_rate`, `im_rate`, and `em_vs_im_log_ratio` in the clustering feature vector
- `docs/AUGMENTATION_VALIDATION.md`: WA grammar cues used in validation (for example `կը`, `պիտի`)

**Goal**
- Move from "single-marker counts" to a reproducible, auditable grammar-distance score per text and per source.

**Feature set A: Inflectional profile vectors**
- Background:
  - WA/EA divergence often appears first in inflectional endings because endings are high-frequency, structurally constrained, and less topic-dependent than open vocabulary.
  - This makes inflectional profiles more stable across domains (news vs literature) than lexical markers alone.
  - In this repo, suffix-based tracking already exists (`-եմ`, `-իմ`, `-ում`, `-ան`, `-ել`), so profile vectors are a natural extension of established signals.
- Build per-text ending vector over tracked suffixes: `v = [freq(-եմ), freq(-իմ), freq(-ում), freq(-ան), freq(-ել), ...]`
- Compute distance from WA baseline vector using Jensen-Shannon divergence (bounded and interpretable)
- Add robust normalization: per-1000-token rates + log scaling for rare endings
- Output:
  - `grammar_profile_jsd_to_wa`
  - `grammar_profile_jsd_to_ea`
  - `grammar_profile_margin = jsd_to_ea - jsd_to_wa`

**Feature set B: Analytic vs synthetic grammar load**
- Background:
  - Many dialect differences are not only "which suffix is used" but "how many grammatical words are needed" for tense/aspect/person expression.
  - Synthetic constructions compress grammatical information into inflectional morphology; analytic constructions spread it across auxiliaries/particles.
  - Quantifying this gives a grammar-complexity view that pair-length metrics alone cannot capture.
- Track construction templates rather than isolated tokens:
  - Prefix-based present patterns (for example `կը + VERB`)
  - Auxiliary-heavy tense/aspect patterns (multi-token verb phrases)
- Define:
  - `synthetic_rate = count(synthetic_patterns) / verb_phrase_count`
  - `analytic_rate = count(analytic_patterns) / verb_phrase_count`
  - `analytic_synthetic_log_ratio = log((analytic_rate + eps)/(synthetic_rate + eps))`
- Pair with existing `token_count_delta` from aligned variants to estimate grammatical expansion cost.

**Feature set C: Paradigm-consistency metrics**
- Background:
  - Real dialectal grammar tends to form coherent paradigms; noisy corpora tend to produce fragmented, contradictory paradigms.
  - Stability at lemma/paradigm level helps distinguish genuine dialect structure from OCR artifacts or mixed-source contamination.
  - This metric family is especially useful when frequency-based features are ambiguous.
- Group forms by lemma candidate and compute within-lemma consistency:
  - Ending entropy per lemma
  - Person/number ending coverage ratio (how complete the paradigm appears)
- Define `paradigm_stability_score = 1 - normalized_entropy`
- Low stability can indicate dialect mixing, OCR corruption, or extraction noise.

**Feature set D: Grammar distance by domain/time**
- Background:
  - Dialect metrics can be confounded by source style (editorial conventions) and publication period (orthographic reform effects).
  - Without domain/time controls, a model may learn "newspaper grammar" or "era grammar" rather than WA/EA grammar.
  - A domain/time-aware model improves interpretability and prevents false dialect attributions.
- Compute grammar features by source and period (newspaper/literature/encyclopedia; pre/post reform)
- Fit simple mixed-effects model:
  - Response: grammar-distance metric
  - Fixed effect: dialect label
  - Random effects: source and year bucket
- Use this to separate true dialect signal from domain artifacts.

**Feature set E: Error-aware grammar metrics**
- Background:
  - OCR and tokenization errors disproportionately affect short grammatical morphemes, making raw counts brittle.
  - Confidence-weighting makes grammar metrics degrade gracefully on noisy scans instead of producing unstable jumps.
  - This is critical when mixing high-quality born-digital text and historical OCR corpora.
- Add confidence weights to each detected pattern:
  - `high` when pattern appears in clean token boundaries
  - `low` when OCR-noise heuristics trigger
- Weighted metric example:
  - `weighted_suffix_rate = sum(conf_i * marker_i) / token_count`
- Improves robustness when corpus quality varies.

**Composite score proposal**
- Background:
  - A single scalar index is useful for ranking, thresholding, monitoring drift, and regression tests.
  - Component-level metrics remain necessary for diagnostics; the composite should summarize, not replace, interpretable parts.
  - Weighting should be data-driven and revisitable as corpus composition evolves.
- Define a single interpretable index:
  - `GrammarDistanceIndex = w1*JSD_profile + w2*|analytic_synthetic_log_ratio| + w3*(1-paradigm_stability) + w4*agreement_divergence`
- Calibrate weights on held-out manually reviewed texts.
- Persist score card fields with component breakdown to keep decisions auditable.

**Evaluation plan (research-to-production)**
- Background:
  - Grammar metrics can look plausible yet fail under domain shift; explicit evaluation stages prevent premature deployment.
  - Backtesting + ablation ensures each added feature contributes measurable value.
  - Schema versioning is required for reproducibility once metrics begin driving filtering or training decisions.
1. Backtest on already labeled WA/EA samples in current corpus metadata.
2. Measure discrimination quality (AUC, F1) for each component and composite index.
3. Run ablation study to find minimal high-value grammar feature subset.
4. Freeze `grammar_feature_schema_version` once stable.
5. Integrate into `dialect_clustering.py` and augmentation validation thresholds.

**Practical implementation notes**
- Background:
  - Implementation should prioritize traceability first, then modeling sophistication.
  - Fast heuristics are appropriate for baseline and iteration; heavier NLP components can be layered once value is proven.
  - Auditability is a first-class requirement because these metrics directly influence dialect filtering and corpus curation.
- Start with regex + suffix heuristics (fast baseline), then layer POS tagging where needed.
- Keep all grammar metrics length-normalized and confidence-weighted.
- Store both raw counts and normalized rates to support audits and re-analysis.
- Log per-source confidence intervals, not only point estimates.

---

### Corpus and Temporal Drift Features

These model **how language varies across time and writing context**—crucial for understanding corpus bias and training data quality.

#### Time-Sliced Orthographic Load Trends

**Historical periodization**
- Pre-reform era (pre-1922): pure classical orthography
  - High complexity (classical digraphs, archaic markers)
  - WA corpus likely shows this pattern throughout
- Reform era (1922-1940): transition period in EA
  - Mixed markers (some old, some new)
  - WA corpus shows little change (diaspora rejected reforms)
- Post-reform (1940-present): EA standardized simplified forms
  - Low complexity (reformed orthography)
  - Clear EA signal in texts from this period

**Time-sliced analysis**
- Group texts by publication date
- Compute orthographic load per time period
- **WA trend**: Should be flat (no drift)
- **EA trend**: Should show drop in classical markers over time
- Deviation from expected trends = potential data quality issue

#### Source-Style Normalization Score

**Domain variation in orthography**
- Newspapers: may modernize spelling for readability
- Literature: may preserve classical orthography for effect
- Encyclopedia: standardized modern form
- **Score**: How much does source type predict orthography vs dialect?
- If source type explains more variance than dialect, flag as biased corpus

**Per-domain profiling**
- Store baseline orthographic load per source:
  - Wikipedia vs newspapers vs books vs archive texts
  - Even within WA, different sources may vary in orthography
- Normalize texts by source before comparing dialects

#### Domain Adaptation Flags

**Feature-to-source correlation**
- Features that strongly predict corpus source instead of dialect
- Example: "presence of long-e" might correlate with "book source" rather than "Western"
- Flag these as problematic: indicates confounding variable
- Use methods like:
  - Logistic regression: can feature predict source (p < 0.05)?
  - Mutual information: I(feature; source) vs I(feature; dialect)

---

### Model-Oriented Composite Features

These features are **designed for downstream ML tasks**—classification, compression, RAG retrieval—rather than purely linguistic analysis.

#### Dialect Compression Ratio

**Formula**: 
$$\text{Compression Ratio} = \frac{\text{letters}_\text{WA} + w \times \text{spaces}_\text{WA}}{\text{letters}_\text{EA} + w \times \text{spaces}_\text{EA}}$$

- Weights spaces lower than letters (w < 1, e.g., w=0.3)
  - Spaces cost less to store (usually just count, not char-by-char)
  - Letters are the primary encoding cost
- **Interpretation**:
  - Ratio > 1: WA takes more bits (classical orthography)
  - Ratio < 1: EA takes more bits (less common, suggests different encoding)
  - Ratio ≈ 1: Comparable length (unusual)
- **Use case**: Estimate storage/bandwidth costs of supporting both dialects

#### Dialect Stability Score

**Concept**: Variance of pair-metrics for **same lemma** across different contexts
- Example: track one lemma across many contexts and compare pair-metric variance
- High stability = predictable, consistent variant patterns
  - Example: the same aligned mapping remains stable across sources
  - Indicates reliable normalization is possible
- Low stability = inconsistent or noisy variants
  - Example: mappings fluctuate across sources or time slices
  - Indicates ambiguity; may degrade normalization quality
- **Metric**: std dev of `letter_delta` for same lemma across corpus contexts
  - Aggregate: average over all lemmas
  - Per-lemma scores: flag low-stability words for manual review

#### Retrieval-Aware Features

**RAG compatibility analysis**
- In Retrieval-Augmented Generation, does orthographic load hurt nearest-neighbor matching?
- Example: Long WA form may fail to retrieve short EA query (vice versa)
- **Measure**:
  - Compute embedding similarity between WA-EA equivalent pairs (using dense vector model)
  - Hypothesis: longer WA forms might have lower similarity due to spurious alignment
  - High dissimilarity = feature hurt RAG performance
- **Use case**: Decide whether to normalize forms before RAG indexing

---

### Data Quality & Audit Features

These features provide **transparency and validation** for data pipelines—critical for maintaining corpus integrity and catching errors early.

#### Pair Mapping Confidence

**Confidence scoring system**
- **High confidence** sources:
  - Multiple lexicons agree on mapping (W-E)
  - Mapping appears in 3+ independent sources
  - Score: 0.9-1.0
- **Medium confidence**:
  - Single strong lexicon or 2 weaker sources
  - Score: 0.6-0.9
- **Low confidence**:
  - Inferred from frequency patterns only
  - Score: 0.3-0.6
- **Tags for manual review**:
  - `low_confidence`: needs human verification
  - `disputed`: multiple sources disagree
  - `needs_verification`: only one source OR inferred

**Disagreement tracking**
- Store competing mappings with scores
- Example: "էր" might map to either "էր" (EA same) or "էր" (different context form)
- Timestamp and reason: why was mapping disputed?
- Use for active learning: prioritize disputed pairs for annotation

#### OCR Noise Susceptibility Index

**Per-letter cluster analysis**
- Which letter clusters are commonly misrecognized in OCR?
  - Example: "իւ" often OCR'd as separate "ի + ւ" (ligature breaks)
  - Example: Armenian glyphs may be confused with visually similar non-Armenian glyphs in noisy scans
- **Compute**: 
  - Frequency of letter cluster in corpus
  - Reported OCR error rate for that cluster (from OCR vendor data or ground truth)
  - Multiply: susceptibility = frequency × error_rate
- **Aggregate**: High-risk zones in texts (noisy letters)

**Spacing pattern analysis**
- Certain spacing patterns (cramped, irregular) confuse tokenizers
- Flag texts with unusual spacing density
- Correlate: spacing anomaly → post-OCR quality issues?

**Output**: Susceptibility index per text
- Aggregate metric: how much OCR noise is expected in this text?
- Flag texts with high susceptibility for manual review

#### Counterfactual Parity Checks

**Concept**: After variant normalization (converting EA → WA), does **meaning stay stable**?

**Verification methods**
1. **Semantic similarity**: 
   - Compute embeddings of original EA form and normalized WA form
   - Cosine similarity should be high (> 0.95)
   - Low similarity = over-normalization, meaning drift
   
2. **Paraphrase checks**:
   - Human annotators verify: do EA and normalized WA forms mean the same thing?
   - Red flag: if 10% of pairs lose meaning, normalization is bad
   
3. **Morphological preservation**:
   - Does lemma stay same? Does POS stay same?
   - Variant should not change grammatical role

**Output**: Parity report
- % of pairs that pass all checks: target ≥ 95%
- Pairs that fail: flag for manual review or remove from training
- Prevents subtle meaning shifts from contaminating training data

---

## EXAMPLE METRIC CARD FOR TEXT

```json
{
  "text_id": "aug_20260305_001",
  "source": "wikipedia_extracted",
  "text_length": 245,
  "metrics": {
    "lexical": {
      "ttr": 0.72,
      "sttr": 0.68,
      "yule_k": 145,
      "unique_words": 176,
      "total_words": 245
    },
    "syntactic": {
      "avg_sentence_length": 18.3,
      "clauses_per_sentence": 1.8,
      "flesch_kincaid_grade": 8.4
    },
    "morphological": {
      "suffix_em_count": 0,
      "suffix_em_frequency": 0.0,
      "suffix_im_count": 3,
      "suffix_im_frequency": 0.012,
      "suffix_um_count": 8,
      "suffix_um_frequency": 0.033,
      "suffix_an_count": 5,
      "suffix_an_frequency": 0.020
    },
    "orthographic": {
      "classical_markers_count": 34,
      "classical_markers_frequency": 0.139,
      "reformed_markers_count": 2,
      "reformed_markers_frequency": 0.008,
      "classical_to_reformed_ratio": 17.0
    },
    "semantic": {
      "entropy": 4.82,
      "pronoun_frequency": 0.045,
      "avg_word_frequency_in_corpus": 234
    },
    "contamination": {
      "code_switching_index": 0.0,
      "eastern_form_ratio": 0.0,
      "variant_ratio_avg": 0.0
    },
    "comparison": {
      "cosine_similarity_to_original": 0.89,
      "kl_divergence_from_wa_baseline": 0.12,
      "levenshtein_distance_to_original": 45
    }
  },
  "quality_flags": {
    "dialect_purity_score": 0.98,
    "baseline_deviation": "within 1 std dev",
    "potential_issues": []
  }
}
```

---

## REFERENCES & STANDARDS

**Key papers/standards:**
- Biber, D. (1988). Variation Across Speech and Writing
- Flesch, R. & Kincaid, J. (1973). Flesch-Kincaid Grade Level formula
- Shannon, C. (1948). Mathematical Theory of Communication (Entropy)
- Kullback-Leibler divergence (Information Theory)

**Corpus Linguistics Standards:**
- COCOA XML markup standard
- TEI P5 guidelines for linguistic texts
- Sketch Engine metrics

**Computational Linguistics Standards:**
- COLING metrics standards
- ACL shared task evaluation measures
