# Research: վ vs ու for “v” sound at end of passive verbs (Western Armenian / classical)

**Status:** Draft – working heuristic based on orthography + morphology; corpus confirmation still to-do.

---

## 1. Question

In Western Armenian / classical orthography, when the **[v] sound** appears at the **right edge of a passive verb form** (passive infinitive / participle / verbal adjective), should the spelling use **վ** or **ու**?

- **վ** = letter վեւ, segmental consonant [v].
- **ու** = digraph functioning primarily as vowel **[u]** (or as part of diphthongs); in classical spelling, the **consonantal [v]** is normally written with **ւ** between vowels, not with bare ու as “v”.

This matters for **Latin → Armenian** reverse transliteration when we see final `-v` in a form that we want to map into a passive verb.

---

## 2. Orthographic background (classical / Western)

- In **traditional (classical) orthography**:
  - **վ** always represents a **consonant [v]**.
  - **ւ** is also a consonant [v], but **only in specific positions**, especially **between vowels** (e.g. classical forms with այւ, մայրս, գաւառ, etc.).
  - **ու** is treated as a **vowel digraph** corresponding to [u] (or part of diphthongs), not as a bare consonant symbol.
- Western Armenian phonetics guide in this repo:
  - Lists **ւ between vowels** as [v].
  - Treats **ու** as the **u/oo** vowel; the guide never uses զույգ «ու» to represent a stand‑alone word‑final consonant [v].

**Implication:** In classical spelling a true **word-final consonant [v]** is represented with **վ**, not with ու. When we see final ու, that sequence is interpreted as **vowel [u]**, not [v].

---

## 3. Passive verb morphology (Western / classical)

Very briefly, for **Western Armenian** (classical spelling):

- **Passive participles**:
  - Commonly use endings like **-ուած, -եալ, -ած** (e.g. գրուած, սիրուած, գրեալ, սիրած).
  - In these patterns, any [v] segment that occurs is **internal**, typically written with **ւ between vowels** (e.g. գրուած has ու as vowel plus ւ; pronunciation may involve a [v]-like glide but orthographically it is not a separate final v consonant).
  - The word **does not end** in a standalone consonant [v]; the right edge is normally a consonant like ծ/լ or a vowel, not վ.

- **Passive infinitives**:
  - Infinitive forms in -ուիլ, -ուել, etc. (e.g. գրուիլ “to be written”) again have any [v]-like articulation **medially**, within the syllable containing ու + following vowel.
  - Orthographically, these are analyzed as vowel sequences (ու + ի/է + լ), not as a final consonant v.

Surveying standard patterns, **passive verb forms in classical / Western Armenian almost never end with a bare consonant [v]**. When [v] appears in the stem, it is written as:

- **վ** when it is a clear consonant segment (often before a vowel or in loanwords).
- **ւ** between vowels (classical convention).

There is no productive pattern where a passive verb has a **final consonant [v] spelled ու**.

---

## 4. Practical heuristic for Latin → Armenian

For our transliteration pipeline (Latin → Armenian) when reconstructing **Western Armenian passive forms**:

- **If the Latin form ends in `-v` and we believe it is a passive verb form:**
  - There is **no evidence** for spelling a **final consonant [v]** with **ու**.
  - The classical spelling system strongly suggests we should **use վ** if we truly need a final [v] consonant.
  - In practice, however, canonical passive verb forms **do not end in a bare v consonant**; they end in something like -ուած, -ած, -եալ, -ուիլ, etc. So a Latin form that literally ends in `-v` is more likely:
    - A **loanword** or transliterated non-Armenian verb, or
    - A **romanization artifact**, not a standard native passive form.

- **Heuristic (current recommendation):**
  - For **native passive participles / infinitives**, we should not be trying to create Armenian spellings ending in **ու for [v]**. Instead we should:
    - Map Latin **-uv / -oov / -ouf** etc. that clearly indicate **vowel [u]** to Armenian **ու**.
    - Map bare final **-v** (if we really need to materialize it) to **վ**, consistent with classical orthography for final consonant [v].
  - When reverse‑mapping known passive patterns (e.g. Latin “grvadz” → Armenian):
    - We should reconstruct **գրուած / գրուած**‑type forms using **Ւ/ու + participle endings**, not a final վ or ու.

This gives a **safe default**: for a final consonant [v] in any Armenian word (including verbs), prefer **վ**, and reserve **ու** for vowel [u] (or diphthongs), even in passive forms.

---

## 5. Open items / future work

- **Corpus validation:** We should still run a targeted search over:
  - Classical Western Armenian corpora (digitized newspapers, books).
  - Nayiri dictionary entries for passive participles and infinitives.
  - To clarify that:
    - In **native passive verb morphology in classical orthography**, forms with a true **word-final consonant [v]** are essentially **nonexistent**; where a final consonant [v] does appear in native words, it is normally written with **վ**.
    - However, Western Armenian **does** have lexical items (especially loans, names, and modern forms) where word-final **ու** can be pronounced [v], so we must not turn the “վ vs ու” preference into a blanket prohibition outside the narrow **passive‑verb reconstruction** context.
- **Implementation note:** When we implement Latin → Armenian reverse mapping in `linguistics/transliteration.py`, we should:
  - For **native passive verb reconstruction**, prefer **վ** if we truly need to spell a final consonant [v] and otherwise reconstruct full participle / infinitive endings (‑ուած, ‑ած, ‑ուիլ, etc.) instead of a bare final v.
  - Avoid introducing new spellings where **ու** is used *solely* as a final consonant [v] in these reconstructed verb forms, but do **not** rewrite or forbid existing lexemes in the corpus that legitimately end in ու.
  - Handle passive forms by reconstructing the **full participle / infinitive ending** (-ուած, -ած, -ուիլ, etc.), rather than by trying to spell a bare final v.

Once corpus checks are done, we can tighten this document with concrete examples and citations.

