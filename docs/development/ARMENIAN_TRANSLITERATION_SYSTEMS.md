# Armenian Transliteration Systems: Deep Dive

**Purpose:** Compare major romanization systems (Hübschmann-Meillet, BGN/PCGN, ALA-LC, ISO 9985) and document how **Western vs Eastern Armenian** spelling and phonetics affect mapping. This project uses **Western Armenian**; see `.cursor/rules/western-armenian-transliteration.mdc` and `docs/armenian_language_guids/` for WA-specific rules.

---

## 1. Overview

Multiple systems exist for converting Armenian script to Latin characters:


| System                 | Year                 | Primary use                     | Reversible?               | WA/EA distinction        |
| ---------------------- | -------------------- | ------------------------------- | ------------------------- | ------------------------ |
| **Hübschmann-Meillet** | 1913                 | Linguistics, Classical Armenian | Yes (with diacritics)     | Not dialect-specific     |
| **BGN/PCGN**           | 1981                 | Geographic names (US/UK boards) | No (digraphs, context)    | Single table             |
| **ISO 9985**           | 1996                 | Bibliographic interchange       | Largely yes               | Single table             |
| **ALA-LC**             | 1997, rev. 2022–2023 | US/library cataloging           | Yes (with disambiguation) | **Yes — WA in brackets** |


**Critical point:** In Western Armenian, **voicing is reversed** relative to Eastern and to the “letter name” intuition: բ = /p/ (p), պ = /b/ (b), etc. Any system that does not specify WA vs EA will default to Eastern in most sources; for this project we **always** apply WA mappings.

---

## 2. Hübschmann-Meillet (1913)

- **Origin:** Heinrich Hübschmann, *Armenische Grammatik* (1897); Antoine Meillet, *Altarmenisches Elementarbuch* (1913). Standard in **linguistic** and **Classical Armenian** literature (e.g. *Revue des Études Arméniennes*).
- **Aspirates:** Combining diacritic above the letter:
  - **Rough breathing** (reversed comma, U+0314): t̔, ch̔, č̔, p̔, k̇ (similar to Greek spiritus asper).
  - **Dot above** (U+0307): ṫ, cḣ, č̇, ṗ, k̇.
- **Fallbacks:** Because combining diacritics have poor support in fonts, many texts use **spacing** variants after the letter: left half-ring ⟨ʿ⟩ (U+02BF), turned comma ⟨ʼ⟩ (U+02BB), or even ASCII apostrophe ⟨'⟩ when unambiguous.
- **Vowels:** ê (է), ə (ը); distinct from e (ե). No built-in WA vs EA; system targets Classical phonology.
- **Use case:** Academic papers, etymology, Classical texts. Not ideal for modern WA/EA without an explicit dialect table.

---

## 3. BGN/PCGN (1981)

- **Origin:** United States Board on Geographic Names (BGN) and Permanent Committee on Geographical Names (PCGN). Adopted for **geographic names** and later used as a base for ISO 9985.
- **Aspirates:** **Right** single quotation mark (modifier letter apostrophe): tʼ, chʼ, tsʼ, pʼ, kʼ — opposite side to the historical rough breathing.
- **Context-dependent (non-reversible) digraphs:**
  - **և** → *yev* initially / after certain vowels; *ev* elsewhere.
  - **ո** → *vo* initially; *o* elsewhere.
  - **ե** → *ye* initially or after certain vowels; *e* elsewhere.
- **Single letters romanized as digraphs:** e.g. ճ → ch, ջ → j, ձ → dz, ծ → ts, etc. Without dictionary or context, reverse mapping is ambiguous.
- **WA vs EA:** One table; does not swap consonant pairs for WA. So **BGN/PCGN out of the box is Eastern-oriented**; for WA we must apply voicing reversal (բ→p, պ→b, etc.) and affricate swap (ջ→ch, ճ→j, ձ→ts, ծ→dz) ourselves.

---

## 4. ISO 9985 (1996)

- **Origin:** International standard for **transliteration of modern Armenian** into Latin for bibliographic and electronic interchange. Based on BGN/PCGN but adjusted for reversibility.
- **Aspirates:** Apostrophe-like mark for most: pʼ, tʼ, cʼ, kʼ. **Inconsistency:** aspirated **չ** is not marked; instead **unaspirated ճ** is written č̣ (with underdot). So in ISO 9985, **č = չ** (not ճ); this **collides** with Hübschmann-Meillet where **č = ճ**.
- **Reversibility:** Avoids ambiguous digraphs for simple letters (except the č/č̣ distinction). Good for bibliographic keys; less so for pronunciation (no WA/EA split in the standard).
- **Use case:** Cataloging, interchange. For **Western Armenian** we still need a separate mapping layer (voicing + affricates) if we want phonetic fidelity.

---

## 5. ALA-LC (1997; 2022–2023)

- **Origin:** American Library Association – Library of Congress. Used in North American and British libraries for **cataloging**.
- **Aspirates:** **Left** single quotation mark (modifier letter left half-ring ʿ U+02BF, or backtick/ASCII in some documents): tʿ, chʿ, tsʿ, pʿ, kʿ.
- **WA vs EA:** ALA-LC **explicitly** differs by dialect:
  - **Classical/Eastern** consonant values: բ→b, պ→p, գ→g, կ→k, դ→d, տ→t, ճ→ch, ջ→j, ձ→dz, ծ→ts.
  - **Western Armenian** (shown in brackets in the official table): **բ→p, պ→b, գ→k, կ→g, դ→t, տ→d, ճ→j, ջ→ch, ձ→ts, ծ→dz** — i.e. voicing reversal and affricate swap.
- **Disambiguation:** Soft sign (prime) between two letters that would otherwise be read as a digraph; no prime inside digraphs like zh, kh, ts, dz, gh, ch.
- **Classical-only quirks:** Initial **յ** → h (reformed orthography removed this); initial **ե** before vowel → y in names. Modern orthography simplifies these.
- **Use case:** Library catalogs, authoritative citations. The **2023** table is the best single reference that includes WA variants; see [LOC Armenian romanization table](https://www.loc.gov/catdir/cpso/romanization/armenian.pdf).

---

## 6. WA vs EA: Spelling and Mapping Differences

### 6.1 Voicing reversal (Western Armenian)


| Grapheme | Eastern (default in many systems) | Western (this project) |
| -------- | --------------------------------- | ---------------------- |
| բ        | b                                 | **p**                  |
| պ        | p                                 | **b**                  |
| գ        | g                                 | **k**                  |
| կ        | k                                 | **g**                  |
| դ        | d                                 | **t**                  |
| տ        | t                                 | **d**                  |
| ճ        | ch                                | **j**                  |
| ջ        | j                                 | **ch**                 |
| ձ        | dz                                | **ts**                 |
| ծ        | ts                                | **dz**                 |


So any system that does not label “Western” will map բ→b, ջ→j, etc.; for WA we must **swap** these pairs.

### 6.2 Vowels and context

- **ը (schwa):** EA often romanized e; WA as **u** (or ə in linguistic notation). Example: ընել → *unel* (WA), not *enel*.
- **է:** Often ē or e′; same grapheme in both; pronunciation differs.
- **թ:** EA sometimes “th”; WA **t** (no aspiration in romanization if we follow ALA-LC/ISO).
- **Initial յ:** Classical “h”; reformed spelling often drops or changes; WA initial յ → **h** (e.g. յոյս = hoys).
- **Diphthongs:** ու → u/oo; իւ → WA **yoo** (e.g. իւր = yur, իւղ = yoogh). Classical orthography prefers **իւ**; reformed uses different spellings (e.g. յուղ for “oil” in EA reform — we keep classical **իւղ** for WA).

### 6.3 Orthography (Classical vs Reformed)

- **Classical** (used in many WA texts): գիւղ, իւղ, ճիւղ, -եան (surnames).
- **Reformed** (EA and some modern WA): գյուղ, յուղ, ճյուղ; different grapheme sequences.
- Transliteration tables may assume one orthography; we **normalize** (NFC, ligature decomposition) before mapping. See `docs/development/NFC_AND_LIGATURE_DECOMPOSITION.md`.

---

## 7. Summary Table (Consonants — WA)

For **Western Armenian** romanization in this project, use the following (aligned with `.cursor/rules` and ALA-LC WA):


| Armenian      | WA Roman     | Note                       |
| ------------- | ------------ | -------------------------- |
| բ             | p            | Voicing reversal           |
| պ             | b            |                            |
| գ             | k            |                            |
| կ             | g            |                            |
| դ             | t            |                            |
| տ             | d            |                            |
| ճ             | j            | Affricate: “job”           |
| ջ             | ch           | Affricate: “chop”          |
| ձ             | ts           |                            |
| ծ             | dz           |                            |
| թ             | t            | Not “th” in WA             |
| ժ             | zh           |                            |
| ղ             | gh           |                            |
| ռ             | rr           |                            |
| ն, մ, լ, etc. | n, m, l, ... | Same as EA in most systems |


Vowels and context rules (յ→h/y, ո→vo/o, ե→ye/e, ւ in ու/իւ, etc.) are in the Western Armenian transliteration rule and phonetics guides.

---

## 8. Recommendations for Implementation

1. **Single canonical WA table:** Maintain one Armenian→Latin table for **Western Armenian** (e.g. in `linguistics/` or `data/`) keyed by grapheme, with context rules for յ, ո, ե, և.
2. **Normalize first:** Apply NFC and ligature decomposition (see `cleaning/armenian_tokenizer`) before transliteration.
3. **Cite standard:** For bibliographic or library alignment, say “ALA-LC 2023, Western Armenian variant”. For linguistics, “Hübschmann-Meillet with WA phonetic values”.
4. **Do not mix:** Do not use ISO 9985’s č for ճ when we need WA j; keep one consistent WA mapping.
5. **Testing:** Use the verification words in `.cursor/rules/western-armenian-transliteration.mdc` (e.g. պետք→bedk, ջուր→choor, իւր→yur).

---

## 9. References

- **Hübschmann,** Heinrich. *Armenische Grammatik.* 1897.
- **Meillet,** Antoine. *Altarmenisches Elementarbuch.* Heidelberg, 1913 (2nd ed. 1980).
- **BGN/PCGN:** *Romanization of Armenian* (1981). [PDF](https://geonames.nga.mil/geonames/GNSSearch/GNSDocs/romanization/ROMANIZATION_OF_ARMENIAN.pdf).
- **ISO 9985:1996** — Transliteration of Armenian characters into Latin characters.
- **ALA-LC:** *Armenian romanization table* (2023). [LOC PDF](https://www.loc.gov/catdir/cpso/romanization/armenian.pdf).
- **Wikipedia:** [Romanization of Armenian](https://en.wikipedia.org/wiki/Romanization_of_Armenian).
- **Project rules:** `.cursor/rules/western-armenian-transliteration.mdc`, `docs/armenian_language_guids/WESTERN_ARMENIAN_PHONETICS_GUIDE.md`, `docs/armenian_language_guids/ARMENIAN_QUICK_REFERENCE.md`.

