# Armenian tokenizer: `extract_words` in-depth

The function `cleaning.armenian_tokenizer.extract_words(text, min_length=2)` is the standard way to get a list of Armenian word tokens from raw text. It is used for per-document word counts, frequency aggregation, loanword analysis, and text metrics.

## What it does (high level)

1. **Normalizes** the string (Unicode NFC, ligature decomposition, lowercasing).
2. **Finds** every maximal run of Armenian-script characters.
3. **Filters** by minimum character length (default 2).
4. **Returns** a list of those tokens (strings).

So it does **not** split on spaces or punctuation; it only considers characters in the Armenian Unicode ranges (and one ligature block). Anything outside those ranges (spaces, Latin, digits, punctuation) acts as a separator.

---

## Step 1: Normalization

`extract_words` calls `normalize(text)` first. Normalization does three things:

### 1.1 Unicode NFC

- **`unicodedata.normalize("NFC", text)`**  
  Puts the string in **Canonical Composition (NFC)**. That way, precomposed characters (e.g. one code point for a letter+diacritic) and decomposed sequences (base + combining mark) are treated the same. Without this, the same “word” could appear in different forms and be counted separately.

### 1.2 Ligature decomposition

- Armenian has **presentation-form ligatures** in Unicode (U+FB13–U+FB17): single glyphs that represent two letters (e.g. ﬓ → մն).
- **`decompose_ligatures(text)`** replaces each of those ligatures with the corresponding two-letter sequence from a fixed map. So tokenization works on the underlying letters, not on the ligature as one “character,” and word boundaries and counts stay consistent whether the font uses ligatures or not.

### 1.3 Armenian lowercasing

- **`armenian_lowercase(text)`** maps uppercase Armenian (U+0531–U+0556) to lowercase (U+0561–U+0587) by adding `0x30` to the code point. Non-Armenian characters are unchanged. So all subsequent logic and word counts are on a single casing.

---

## Step 2: Word extraction (regex)

After normalization, the code uses a single regex to find “words”:

```python
_ARMENIAN_WORD_RE = re.compile(r"[\u0531-\u0556\u0561-\u0587\uFB13-\uFB17]+")
```

- **`\u0531-\u0556`** — Armenian uppercase (so any that weren’t lowercased, or if the step were skipped).
- **`\u0561-\u0587`** — Armenian lowercase.
- **`\uFB13-\uFB17`** — Armenian ligatures (in case any remain).

So a **word** here is “one or more characters from these ranges.” No spaces or other scripts inside a token.

- **`.findall(text)`** returns every maximal contiguous match. So you get one token per run of Armenian script; anything else (space, punctuation, Latin, digits, etc.) breaks the run and starts a new token when Armenian starts again.

---

## Step 3: Minimum length filter

- **`min_length`** defaults to **2** (same as `MIN_WORD_LENGTH`).
- Any token with **fewer than `min_length`** characters is dropped. So single Armenian letters (e.g. “ո” or “ի”) are not in the list when `min_length=2`. This reduces noise in frequency and word-count stats.

For **per-document word counts** in ingest we use **`min_length=1`** so every Armenian character token is counted (see `_compute_document_metrics` in `scraping/_helpers.py`).

---

## Step 4: Return value

- Return type is **`list[str]`**: each element is one token (normalized, lowercase Armenian, possibly with decomposed ligatures).
- Order is **preserved** (same as in the text). Duplicates are kept; if you need counts, use `Counter(extract_words(...))` or `word_frequencies(...)` in the same module.

---

## Design choices and caveats

- **Script-only**: Only Armenian script (and the ligature block) is considered. Mixed text (e.g. “Armenian word” or “100 դրամ”) yields tokens only from the Armenian parts; the rest is ignored for this list.
- **No stemming/lemmatization**: “գրել”, “գրեց”, “գրում” are three different tokens.
- **No segmenter**: Clitics or hyphenated compounds are not split; they are one token if they are one run of Armenian characters.
- **Ligatures**: Handled by decomposition before matching, so they don’t create extra or odd tokens.

---

## Where it’s used

- **Per-doc word counts on ingest**: `scraping._helpers._compute_document_metrics` uses `extract_words(text, min_length=1)` and `Counter` to fill `document_metrics.word_counts`.
- **Loanword tracker / text metrics**: Same tokenizer for consistent vocabulary and metrics.
- **Frequency aggregator**: Uses its own Armenian-word regex; for a single pipeline, using `extract_words` everywhere would align tokenization across features.
