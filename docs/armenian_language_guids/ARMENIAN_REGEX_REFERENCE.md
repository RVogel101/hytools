# Armenian Regex Reference

Complete inventory of every regex and Armenian string pattern used in armenian-corpus-core, with dialect labeling (Western vs Eastern) and verification notes for Western Armenian correctness.

**Unicode ranges:**

- `\u0531-\u0587`: Armenian uppercase (Ա-Տ) + lowercase (ա-տ) + punctuation
- `\u0530-\u058F`: Full Armenian block (includes modifier letters, punctuation)
- `\u0560-\u058F`: Armenian lowercase subset (redundant with above)
- `\uFB13-\uFB17`: Armenian ligatures (ﬓ ﬔ ﬕ ﬖ ﬗ)

---

## Quick Reference: Dialect by File


| File                                | Dialect                               | Purpose                           |
| ----------------------------------- | ------------------------------------- | --------------------------------- |
| scraping/_helpers.py                | **WA** (positive), **EA** (negative)  | WA classifier, Wikitext           |
| linguistics/dialect_classifier.py   | **WA**, **EA**                        | Rule-based dialect classification |
| ingestion/discovery/book_inventory.py | **Neutral** (WA context)              | Title discovery                   |
| scraping/frequency_aggregator.py    | **Neutral**                           | Word tokenization                 |
| cleaning/armenian_tokenizer.py      | **Neutral**                           | Word extraction                   |
| augmentation/batch_worker.py        | **Neutral**                           | Armenian char detection           |
| ingestion/enrichment/biography_enrichment.py | **Both**                              | Death/place extraction            |
| linguistics/metrics/text_metrics.py | **WA** (classical), **EA** (reformed) | Orthography metrics               |
| ocr/postprocessor.py                | **Neutral**                           | OCR cleanup                       |


---

## 1. scraping/_helpers.py — WA/EA Dialect Classifier

**Purpose:** Western Armenian vs Eastern Armenian classification via orthographic and lexical markers.

### 1.1 WESTERN ARMENIAN — Classical Orthography Markers

**Note:** "Classical orthography" refers to *spelling* (diphthongs/digraphs), not Classical Armenian language. Eastern Armenians in Iran use classical orthography but speak Eastern. Classical markers: diphthongs/digraphs **ոյ, այ, իւ, եա, եօ, էյ**; **յ** at word end; **ութիւն** at word end = classical.

| Pattern (Unicode)                                                    | Armenian    | Romanization       | Purpose                                        | WA Correct? |
| -------------------------------------------------------------------- | ----------- | ------------------ | ---------------------------------------------- | ----------- |
| `\u0565\u0561`                                                       | եա          | ea                 | Digraph retained in WA; EA reformed to ya (յա) | ✅ Yes       |
| `\u056B\u0582`                                                       | իւ          | yu / yoo           | Classical digraph (not iw); EA dropped         | ✅ Yes       |
| `\u0574\u0567\u057B`                                                 | մէջ         | mej                | "in" (postposition)            | ✅ Yes       |
| `\u056B\u0582\u0580\u0561\u0584\u0561\u0576\u0579\u056B\u0582\u0580` | իւրաքանչիւր | yoorakanchyoor     | "each/every" (classical spelling)              | ✅ Yes       |
| `\u056C\u0565\u0566\u0578\u0582`                                     | լեզու       | lezou              | "language" (classical spelling)                 | ✅ Yes       |
| `\u0578\u0575`                                                       | ոյ          | uy                 | Diphthong (classical)                          | ✅ Yes       |


### 1.2 WESTERN ARMENIAN — Lexical Markers


| Pattern (Unicode)                            | Armenian | Romanization | Purpose                        | WA Correct? |
| -------------------------------------------- | -------- | ------------ | ------------------------------ | ----------- |
| `\u056F\u0568`                               | կը       | gu           | Present tense prefix           | ✅ Yes       |
| `\u056F\u055A`                               | կ՚       | g'           | Elided before vowel            | ✅ Yes       |
| `\u057A\u056B\u057F\u056B`                   | պիտի     | bidi         | WA future marker (beedee)      | ✅ Yes       |
| `\u0570\u0578\u0576`                         | հոն      | hon          | "there" (EA: այնտեղ)          | ✅ Yes       |
| `\u0570\u0578\u057D`                         | հոս      | hos          | "here" (EA: այստեղ)            | ✅ Yes       |
| `\u0561\u056C`                               | ալ       | al           | "also/too" (EA: էլ)            | ✅ Yes       |
| `\u0570\u056B\u0574\u0561`                   | հիմա     | hima         | "now"                          | ✅ Yes       |
| `\u0561\u0575\u057D\u057A\u0567\u057D`       | այսպէս   | aysbes       | "like this" (long-e)           | ✅ Yes       |
| `\u0561\u0575\u0576\u057A\u0567\u057D`       | այնպէս   | aynbes       | "like that" (long-e)           | ✅ Yes       |
| `\u0578\u0579\u056B\u0576\u0579`             | ոչինչ    | vochinch     | "nothing" (EA: ոչինչ, same)    | ✅ Yes       |
| `\u0562\u0561\u0576 \u0574\u0568`            | բան մը   | pan mu       | "something" (indefinite is մը/մըն postposition) | ✅ Yes |
| `\u0579\u0565\u0574`                         | չեմ      | chem         | Negative particle              | ✅ Yes       |
| `\u0574\u0565\u0576\u0584`                   | մենք     | menk         | "we" (EA: մենք, same)          | ✅ Yes       |
| `\u056B\u056C`                               | իլ       | il           | Passive verb suffix (e.g. խօսիլ); NOT indefinite | ✅ Yes |
| `\u0563\u0565\u0572\u0565\u0581\u056B\u056F` | գեղեցիկ  | keghetsig    | "beautiful"                    | ✅ Yes       |


### 1.3 WESTERN ARMENIAN — Vocabulary


| Pattern (Unicode)                            | Armenian | Romanization | Purpose                           | WA Correct? |
| -------------------------------------------- | -------- | ------------ | --------------------------------- | ----------- |
| `\u0573\u0565\u0580\u0574\u0561\u056f`       | ճերմակ   | jermag      | "white" (EA: սպիտակ)              | ✅ Yes       |
| `\u056d\u0578\u0570\u0561\u0576\u0578\u0581` | խոհանոց  | khohanots    | "kitchen"                         | ✅ Yes       |
| `\u0573\u0578\u0582\u0580`                   | ջուր     | chour         | "water" (EA: ջուր, same)          | ✅ Yes       |
| `\u0577\u0561\u057a\u056b\u056f`             | շապիկ    | shabig       | "shirt" (EA: շապիկ)               | ✅ Yes       |
| `\u0574\u0561\u0576\u0578\u0582\u056f`       | մանուկ   | manoog       | "child" (EA: մանկիկ)              | ✅ Yes       |
| `\u057f\u0572\u0561\u0575`                   | տղայ     | d'gha         | "boy" (WA with silent յ; EA: տղա) | ✅ Yes       |
| `\u056d\u0585\u057d\u056b\u056c`             | խօսիլ    | khosil       | "to speak" (EA: խոսել)            | ✅ Yes       |
| `\u0565\u0580\u0569\u0561\u056c`             | երթալ    | yertal       | "to go" (EA: գնալ)                | ✅ Yes       |
| `\u0568\u0576\u0565\u056c`                   | ընել     | unel         | "to do" (EA: անել)                | ✅ Yes       |
| `\u0578\u0582\u0566\u0565\u056c`             | ուզել    | ouzel        | "to want" (EA: ուզում եմ)         | ✅ Yes       |
| `\u0570\u0561\u057d\u056f\u0576\u0561\u056c` | հասկնալ  | hasgnal      | "to understand" (EA: հասկանալ)    | ✅ Yes       |
| `\u0561\u0580\u0564\u0567\u0576`             | արդէն    | arten        | "already" (EA: արդեն)             | ✅ Yes       |
| `\u0570\u0561\u057a\u0561`                   | հապա     | haba         | "then/so" (colloquial)            | ✅ Yes       |
| `\u0577\u0561\u057f`                         | շատ      | shad         | "very/much"                       | ✅ Yes       |
| `\u056f\u056b\u0580\u0561\u056f\u056b`       | կիրակի   | giragi       | "Sunday" (EA: same spelling)      | ✅ Yes       |


### 1.4 EASTERN ARMENIAN — Reform Markers (negative signal)


| Pattern (Unicode)                | Armenian | Romanization | Purpose                       | EA Correct? |
| -------------------------------- | -------- | ------------ | ----------------------------- | ----------- |
| `\u0574\u056B\u0575`             | միյ      | miy          | EA reformed digraph (from ea) | ✅ Yes       |
| `\u056D\u0576\u0561\u0575\u0574` | խնայմ    | khnaym       | EA reformed (WA: խնամ)        | ✅ Yes       |


### 1.5 Regex — Word-internal long-e, diphthongs


| Regex                                        | Purpose                                  | Dialect                  |
| -------------------------------------------- | ---------------------------------------- | ------------------------ |
| `[\u0531-\u0587]\u0567[\u0531-\u0587]`       | Word-internal long-e (է) between letters | **WA** (classical)       |
| `\u0561\u0575(?=[\s\u0589\u055D\u055E,.;:!?] | \Z)`                                     | Word-final -ay diphthong |
| `\u0578\u0575(?=[\s\u0589\u055D\u055E,.;:!?] | \Z)`                                     | Word-final -oy diphthong |


### 1.6 WA Authors (boost score)

*-եան transliterated as "ian" in Western Armenian*

| Pattern                                                  | Armenian  | Name          |
| -------------------------------------------------------- | --------- | ------------- |
| `\u0544\u0565\u056D\u056B\u0569\u0561\u0580`             | Մեղիթար   | Meghitar      |
| `\u0544\u056D\u056B\u0569\u0561\u0580\u0565\u0561\u0576` | Մխիթարեան | Mukhitarian  |
| `\u054F\u0561\u0576\u056B\u0567\u056C`                   | Տանիէլ    | Daniel        |
| `\u054E\u0561\u0580\u0578\u0582\u056A\u0561\u0576`       | Վարուժան  | Varoujan    |
| `\u054D\u056B\u0561\u0574\u0561\u0576\u0569\u0578`       | Սիամանթօ  | Siamanto    |
| `\u0536\u0561\u0580\u056B\u0586\u0565\u0561\u0576`       | Զարիբէան  | Zarifean    |
| `\u054F\u0565\u0584\u0567\u0565\u0561\u0576`             | Թէքէեան   | Tekeyan     |
| `\u054D\u0561\u0580\u0561\u0586\u0565\u0561\u0576`       | Սարաֆէան  | Sarafian    |
| `\u0547\u0561\u0570\u0576\u0578\u0582\u0580`             | Շահնուր   | Shahnour    |
| `\u0536\u0561\u0580\u0564\u0561\u0580\u0565\u0561\u0576` | Զարդարեան | Zartarian   |
| `\u0536\u0561\u057A\u0567\u056C`                         | Զապէլ     | Zabel       |
| `\u0535\u057D\u0561\u0575\u0565\u0561\u0576`             | Եսայեան   | Yesayian    |
| `\u0540\u0561\u0574\u0561\u057D\u057F\u0565\u0572`       | Համաստեղ  | Hamasdegh   |
| `\u0536\u0578\u0570\u0580\u0561\u057A`                   | Զոհրապ    | Zohrap      |


### 1.7 WA Publication Cities


| Pattern                                            | Armenian | Place                | Note                             |
| -------------------------------------------------- | -------- | -------------------- | -------------------------------- |
| `\u054A\u0567\u0575\u0580\u0578\u0582\u0569`       | Պէյրութ  | Beyroot (Beirut)     | _helpers.py, book_inventory.py ✅ |
| `\u054A\u0578\u056C\u056B\u057D`                   | Պոլիս    | Bolis (Istanbul)     | ✅                                |
| `\u0553\u0561\u0580\u056B\u0566`                   | Փարիզ    | Pariz (Paris)        | ✅                                |
| `\u0533\u0561\u0570\u056B\u0580\u0567`             | Գահիրէ   | Gahire (Cairo)       | ✅                                |
| `\u054A\u0578\u057D\u0569\u0578\u0576`             | Պոսդոն   | Boston               | ✅                                |
| `\u0546\u056B\u0582 \u0535\u0578\u0580\u0584`      | Նիւ Եորք | Nyoo Yeork           | ✅                                |
| `\u0540\u0561\u056C\u0567\u057A`                   | Հալէպ    | Haleb (Aleppo)       | ✅                                |
| `\u0544\u0578\u0576\u0569\u0580\u0567\u0561\u056C` | Մոնթրէալ | Monturial (Montreal) | ✅                                |


---

## 2. ingestion/discovery/book_inventory.py — Title Discovery

**Purpose:** Book/manuscript title extraction from MongoDB corpus.

### 2.1 General


| Regex              | Purpose                         | Dialect |
| ------------------ | ------------------------------- | ------- |
| `[\u0530-\u058F]+` | Any Armenian character sequence | Neutral |


### 2.2 Context Markers (substring match)


| Pattern                                                  | Armenian  | Romanization | Purpose            |
| -------------------------------------------------------- | --------- | ------------ | ------------------ |
| `\u056f\u0561\u0580\u0564`                               | կարդ      | gart         | "read" (verb: կարդալ) |
| `\u0563\u056b\u0580\u0584`                               | գիրք      | kirk         | "book"             |
| `\u0571\u0565\u0580\u0561\u0563\u056b\u0580`             | ձեռագիր   | tserakir     | "manuscript"       |
| `\u0570\u0580\u0561\u0569\u0561\u0580\u0561\u056f`       | հրատարակ  | hratarak     | "publish"          |
| `\u0563\u0580\u0561\u056e`                               | գրած      | k'radz       | "wrote"            |
| `\u0544\u0561\u0569\u0565\u0561\u0576`                   | Մատեան    | matian       | "manuscript/codex" |
| `\u0536\u0578\u0572\u0578\u0582\u056e\u0561\u0581\u0582` | Ժողովածու | zhoghovadzou | "collection"       |


### 2.3 "Book of" / Title-start Patterns (regex)


| Regex                                                                 | Armenian     | Romanization  | WA Correct?   |
| --------------------------------------------------------------------- | ------------ | ------------- | ------------- |
| `^\u0563\u056b\u0580\u0584\s`                                         | Գիրք         | Girkʿ         | ✅ Yes         |
| `^\u0536\u0578\u0572\u0578\u0582\u056e\u0561\u0581\u0582\s`           | Ժողովածու    | Zhoghovatsou  | ✅ Yes         |
| `^\u054a\u0561\u0569\u0574\u0582\u0569\u056b\u0582\u0576`             | Պատմութիւն   | Patmutʿiwn    | ✅ Yes (fixed) |
| `^\u054f\u0561\u0563\u0565\u0580`                                     | Տաղեր        | Tagher        | ✅ Yes         |
| `^\u054f\u0561\u0563\u0565\u0580\u0563\u0582\u0569\u056b\u0582\u0576` | Տաղերգութիւն | Taghergutʿiwn | ✅ Yes (fixed) |
| `^\u0535\u0580\u056f\u0565\u0580\s`                                   | Երկեր        | Yerker        | ✅ Yes (works) |


### 2.4 Exclusion — Person Prefixes


| Pattern               | Armenian | Meaning         |
| --------------------- | -------- | --------------- |
| `\u054e\u0580\u0564.` | Վրդ.     | Vrd. (Reverend) |
| `\u0564\u0578\u056f.` | Դոկ.     | Dok. (Doctor)   |


### 2.5 Exclusion — Places


| Pattern                                            | Armenian | Place    |
| -------------------------------------------------- | -------- | -------- |
| `\u054a\u0567\u0575\u0580\u0582\u0569`             | Պէյրութ  | Peyrouth |
| `\u054a\u0578\u056c\u056b\u057d`                   | Պոլիս    | Bolis    |
| `\u0553\u0561\u0580\u056b\u0566`                   | Փարիզ    | Bariz    |
| `\u0540\u0561\u056c\u0567\u057a`                   | Հալէպ    | Halep    |
| `\u0535\u0580\u0582\u0561\u0576`                   | Երեւան   | Yerevan  |
| `\u0544\u0578\u0576\u0569\u0580\u0567\u0561\u056c` | Մոնթրէալ | Montreal |
| `\u0546\u056b\u0582 \u0535\u0578\u0580\u0584`      | Նիւ Եորք | New York |


### 2.6 Exclusion — Institutions


| Pattern                                                  | Armenian  |
| -------------------------------------------------------- | --------- |
| `\u0544\u056d\u056b\u0569\u0561\u0580\u0565\u0561\u0576` | Մխիթարեան |
| `\u0546\u0582\u054a\u0561\u0580\u0565\u0561\u0576`       | Նուպարեան |


### 2.7 Quoted Title Extraction


| Regex                      | Purpose                     |
| -------------------------- | --------------------------- |
| `\u00AB([^\u00BB]+)\u00BB` | «...» (Armenian guillemets) |
| `"([^"]+)"`                | Double-quoted               |


---

## 3. linguistics/dialect_classifier.py — Rule-based Classifier

**Purpose:** Dialect classification using morphology and orthography.

### 3.1 WESTERN ARMENIAN


| Pattern | Armenian  | Purpose                                                                 |
| ------- | --------- | ----------------------------------------------------------------------- |
| `իւ`    | իւ        | Classical digraph (EA: յու/ու)                                          |
| `(^     | \s)մը($   | \s                                                                      |
| `(^     | \s)կը($   | \s                                                                      |
| `(^     | \s)պիտի($ | \s                                                                      |
| `(^     | \s)չը($   | \s                                                                      |

**Negation:** Western Armenian marks negation with **չ** at the beginning of a word. The pattern `(^|\s)չը($|\s)` matches the negative particle "չը" as a stand-alone word; more generally, any word starting with **չ** (e.g. չեմ, չէ, չուզեմ) indicates negative. Purpose: strong WA signal.


### 3.2 EASTERN ARMENIAN


| Pattern     | Armenian          | Classical (WA) equivalent |
| ----------- | ----------------- | ------------------------- |
| `(^         | \s)յուղ($         | \s                        |
| `(^         | \s)գյուղ($        | \s                        |
| `(^         | \s)ճյուղ($        | \s                        |
| `(^         | \s)զամբյուղ($     | \s                        |
| `(^         | \s)ուրաքանչյուր($ | \s                        |
| `\bpetik\b` | (Latin)           | Transliteration cue       |
| `\bjayur\b` | (Latin)           | Transliteration cue       |


---

## 4. scraping/frequency_aggregator.py


| Regex                           | Purpose                    | Note                                                                                 |
| ------------------------------- | -------------------------- | ------------------------------------------------------------------------------------ |
| `[\u0530-\u058F\u0560-\u058F]+` | Armenian word tokenization | **Redundant:** \u0560-\u058F is subset of \u0530-\u058F. Consider `[\u0530-\u058F]+` |


---

## 5. scraping/_helpers.py — Wikitext


| Regex  | Purpose | Armenian?                      |
| ------ | ------- | ------------------------------ |
| `(File | Image   | \u054a\u0561\u057f\u056f):.*?` |


---

## 6. scraping/rss_news.py

**ARMENIAN_KEYWORDS:** Latin transliteration only (armenia, armenian, hay, yerevan, etc.). No Armenian script. Used for filtering international RSS feeds.

---

## 7. cleaning/armenian_tokenizer.py — Word Extraction


| Regex                                        | Purpose                          | Dialect     |
| -------------------------------------------- | -------------------------------- | ----------- |
| `[\u0531-\u0556\u0561-\u0587\uFB13-\uFB17]+` | Armenian words (incl. ligatures) | **Neutral** |


**Ligature map (U+FB13–U+FB17):** ﬓ→մն, ﬔ→մե, ﬕ→մի, ﬖ→վն, ﬗ→մխ

---

## 8. augmentation/batch_worker.py


| Regex                          | Purpose                                | Dialect     |
| ------------------------------ | -------------------------------------- | ----------- |
| `[\u0531-\u0587\uFB13-\uFB17]` | Single Armenian char (incl. ligatures) | **Neutral** |


---

## 9. ingestion/enrichment/biography_enrichment.py — Author Profile Extraction


| Regex                    | Armenian | Romanization | Purpose                            | Dialect  |
| ------------------------ | -------- | ------------ | ---------------------------------- | -------- |
| `հրաժեշտ\s*–?\s*(\d{4})` | հրաժեշտ  | hrajesht     | "farewell" (death year)            | **Both** |
| `մահ\s*–?\s*(\d{4})`     | մահ      | mah          | "death" (death year)               | **Both** |
| `[Ա-Ֆ][ա-ֆ]{3,15}`       | —        | —            | Place names (cap + 3–15 lowercase) | **Both** |


---

## 10. linguistics/metrics/text_metrics.py — Orthography Metrics


| Pattern | Armenian | Purpose          | Dialect |
| ------- | -------- | ---------------- | ------- |
| `ո`     | ո        | Classical marker | **WA**  |
| `իւ`    | իւ       | Diphthong        | **WA**  |
| `եա`    | եա       | Digraph          | **WA**  |
| `ա`     | ա        | Reformed marker  | **EA**  |
| `ե`     | ե        | Reformed marker  | **EA**  |

**Orthography metrics captured:** classical markers (ո, իւ, եա counts), reformed markers (ա, ե counts), classical_to_reformed_ratio. Used to distinguish classical (WA) vs reformed (EA) orthography.

**Pronouns list:** ես, դու, նա, ան, ինք, մենք, դուք, նրանք, այն, սա — used in both dialects at different rates; Western also uses **ան** for he/she/it. Used for semantic metrics (pronoun frequency), not dialect classification.

---

## 11. ocr/postprocessor.py — OCR Cleanup


| Regex                                 | Purpose                                | Dialect     |
| ------------------------------------- | -------------------------------------- | ----------- |
| `[^\u0530-\u058F\u0020-\u007E\s]{4,}` | Garbage (non-Armenian, non-ASCII runs) | **Neutral** |
| `(?<=\S)\.\.` → `։`                   | Replace `..` with Armenian full stop   | **Neutral** |


**Preserved punctuation:** ՝ (comma), ՞ (question), ։ (full stop), ՛ (emphasis), ՜ (exclamation)

---

## 12. Sentence Splitting (Armenian Full Stop)


| File                                    | Regex            | Purpose               |
| --------------------------------------- | ---------------- | --------------------- |
| augmentation/strategies.py              | `(?<=[։.!?])\s+` | Split on sentence end |
| linguistics/metrics/dialect_distance.py | `(?<=[։.!?])\s+` | Split on sentence end |


**Armenian full stop:** `։` (U+0589)

---

## 13. ingestion/discovery/author_extraction.py


| Regex       | Armenian                 | Purpose          |
| ----------- | ------------------------ | ---------------- |
| `[,\.։՝\-]` | ։ (full stop), ՝ (comma) | Strip from names |


---

## 14. Summary by Dialect


| Dialect     | Files                                                                                                | Purpose                                                                             |
| ----------- | ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **Western** | _helpers.py, dialect_classifier.py, book_inventory.py, text_metrics.py                               | WA markers, classical orthography, WA vocabulary, WA authors/cities, title patterns |
| **Eastern** | _helpers.py, dialect_classifier.py, text_metrics.py                                                  | EA reform markers (negative signal), EA reformed spellings                          |
| **Neutral** | book_inventory.py, frequency_aggregator.py, armenian_tokenizer.py, batch_worker.py, postprocessor.py | Armenian script detection, tokenization, OCR                                        |


---

## 15. Bugs Fixed (Western Armenian)


| Item         | Location          | Fix                       |
| ------------ | ----------------- | ------------------------- |
| Պատմութիւն   | book_inventory.py | Changed final ր → ն       |
| Տաղերգութիւն | book_inventory.py | Changed final ր → ն       |
| Պէյրութ      | book_inventory.py | Added missing ո (7 chars) |


