# Transliteration and IPA: Logic and Mappings by Dialect

**Purpose:** Detailed report of the exact logic and mapping used for Armenian ↔ Latin (BGN/PCGN 1981 style) and Armenian → IPA for **Eastern**, **Classical**, and **Western** variants. Implementation: `linguistics/transliteration.py`.

---

## 1. Overview


| Dialect       | Latin (BGN/PCGN)                                                                                                       | IPA                                                      |
| ------------- | ---------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| **Eastern**   | BGN/PCGN 1981 base (բ=b, պ=p, ջ=j, ճ=ch). Aspirates: tʼ, chʼ, tsʼ, pʼ, kʼ.                                             | Eastern Armenian phonemes (բ=b, ր=ɾ, etc.)               |
| **Classical** | Like Eastern with ē for է, ə for ը; initial յ→h, initial ե→ye.                                                         | Same as Eastern IPA (traditional)                        |
| **Western**   | Voicing reversal: բ→p, պ→b, գ→k, կ→g, դ→t, տ→d, ճ→j, ջ→ch, ձ→ts, ծ→dz; ը→u; թ→t (no apostrophe). Context: initial յ→h. | Western phonemes per WESTERN_ARMENIAN_PHONETICS_GUIDE.md |


**Normalization:** Before any conversion, text is NFC-normalized, Armenian ligatures (U+FB13–U+FB17) are decomposed, and Armenian uppercase is lowercased.

**Aspirate character:** Modifier letter apostrophe U+02BC (ʼ) is used for BGN/PCGN aspirates: tʼ, chʼ, tsʼ, pʼ, kʼ (Eastern/Classical). Western uses plain "t" for թ (no "th").

---

## 2. Armenian → Latin (BGN/PCGN) — Single-Letter Mappings

### 2.1 Eastern (BGN/PCGN 1981 base)


| Armenian | Latin | Note                                    |
| -------- | ----- | --------------------------------------- |
| ա        | a     |                                         |
| բ        | b     |                                         |
| գ        | g     |                                         |
| դ        | d     |                                         |
| ե        | e     | (context: ye at start / after vowel)    |
| զ        | z     |                                         |
| է        | e     |                                         |
| ը        | y     |                                         |
| թ        | tʼ    | aspirate                                |
| ժ        | zh    |                                         |
| ի        | i     |                                         |
| լ        | l     |                                         |
| խ        | kh    |                                         |
| ծ        | ts    |                                         |
| կ        | k     |                                         |
| հ        | h     |                                         |
| ձ        | dz    |                                         |
| ղ        | gh    |                                         |
| ճ        | ch    |                                         |
| մ        | m     |                                         |
| յ        | y     | (context: h at word start in Classical) |
| ն        | n     |                                         |
| շ        | sh    |                                         |
| ո        | o     | (context: vo before consonant)          |
| չ        | chʼ   | aspirate                                |
| պ        | p     |                                         |
| ջ        | j     |                                         |
| ռ        | rr    |                                         |
| ս        | s     |                                         |
| վ        | v     |                                         |
| տ        | t     |                                         |
| ր        | r     |                                         |
| ց        | tsʼ   | aspirate                                |
| ւ        | w     | (in digraphs: ու→u, իւ→yoo)             |
| փ        | pʼ    | aspirate                                |
| ք        | kʼ    | aspirate                                |
| օ        | o     |                                         |
| ֆ        | f     |                                         |


### 2.2 Western (voicing reversal + affricate swap)

Same as Eastern **except**:


| Armenian | Eastern | Western               |
| -------- | ------- | --------------------- |
| բ        | b       | **p**                 |
| պ        | p       | **b**                 |
| գ        | g       | **k**                 |
| կ        | k       | **g**                 |
| դ        | d       | **t**                 |
| տ        | t       | **d**                 |
| ճ        | ch      | **j**                 |
| ջ        | j       | **ch**                |
| ձ        | dz      | **ts**                |
| ծ        | ts      | **dz**                |
| ը        | y       | **u**                 |
| թ        | tʼ      | **t** (no apostrophe) |


Context: **յ** at word start → **h** (else y).

### 2.3 Classical

Same as Eastern **except**: է→**ē**, ը→**ə**; **յ** at word start → **h**; **ե** at word start or after vowel → **ye**.

---

## 3. Digraph and Context Logic (Armenian → Latin)

### 3.1 Digraphs (processed first, left-to-right)


| Sequence       | Eastern/Classical                        | Western | Note               |
| -------------- | ---------------------------------------- | ------- | ------------------ |
| **ե + ւ** (և)  | yev (word start or after vowel), else ev | same    | BGN/PCGN           |
| **ո + ւ** (ու) | u                                        | u       | single sound "oo"  |
| **ի + ւ** (իւ) | yoo                                      | yoo     | single sound "yoo" |


### 3.2 Context-dependent single letters

- **ո (O/V)**  
  - **Before a consonant** (including word-initial): output **vo**.  
  - **After a vowel or end of word**: output **o**.
- **ե (E/YE)**  
  - **Word-initial or after vowel** (ա, ե, է, ը, ի, ո, յ, օ): output **ye**.  
  - **Else**: output **e**.
- **յ (Y/H)**  
  - **Western / Classical**: **word-initial** → **h**; else → **y**.  
  - **Eastern**: always **y** in this implementation.

---

## 4. Latin → Armenian — Reverse Mappings

Reverse mapping is **ambiguous** in places (one Latin string can correspond to more than one Armenian letter). The implementation uses a **single canonical Armenian letter per Latin token** per dialect.

### 4.1 Multi-character sequences (longest match first)


| Latin | Armenian |
| ----- | -------- |
| yoo   | իւ       |
| yev   | և        |
| ev    | և        |
| vo    | ո        |
| ye    | ե        |
| u     | ու       |


### 4.2 Aspirate sequences


| Latin | Armenian |
| ----- | -------- |
| tʼ    | թ        |
| chʼ   | չ        |
| tsʼ   | ց        |
| pʼ    | փ        |
| kʼ    | ք        |


### 4.3 Single-character reverse (dialect-specific)

**Eastern:** b→բ, p→պ, g→գ, k→կ, d→դ, t→տ, ch→ճ, j→ջ, dz→ձ, ts→ծ, etc. (first occurrence in forward table wins when building reverse).

**Western:** p→բ, b→պ, k→գ, g→կ, t→դ, d→տ, j→ճ, ch→ջ, ts→ձ, dz→ծ, u→ը (schwa), etc.

**Classical:** Same as Eastern for consonants; ə→ը, ē→է.

**Ambiguity note:** For example in Western, "t" could be թ or (in other systems) տ; we map "t"→թ and "d"→տ. Latin input should use the same dialect convention for correct round-trip.

---

## 5. Armenian → IPA — Single-Letter Mappings

### 5.1 Western IPA

Source: `docs/armenian_language_guids/WESTERN_ARMENIAN_PHONETICS_GUIDE.md`.


| Armenian | IPA    | Note                           |
| -------- | ------ | ------------------------------ |
| ա        | ɑ      |                                |
| բ        | p      | voicing reversal               |
| գ        | k      |                                |
| դ        | t      |                                |
| ե        | ɛ / jɛ | jɛ word-initial or after vowel |
| զ        | z      |                                |
| է        | ɛ      |                                |
| ը        | ə      |                                |
| թ        | t      |                                |
| ժ        | ʒ      |                                |
| ի        | i      |                                |
| լ        | l      |                                |
| խ        | x      |                                |
| ծ        | dz     |                                |
| կ        | g      |                                |
| հ        | h      |                                |
| ձ        | ts     |                                |
| ղ        | ɣ      |                                |
| ճ        | dʒ     |                                |
| մ        | m      |                                |
| յ        | j / h  | h word-initial                 |
| ն        | n      |                                |
| շ        | ʃ      |                                |
| ո        | ɔ / vo | vo before consonant            |
| չ        | tʃ     |                                |
| պ        | b      |                                |
| ջ        | tʃ     |                                |
| ռ        | r      |                                |
| ս        | s      |                                |
| վ        | v      |                                |
| տ        | d      |                                |
| ր        | ɾ      |                                |
| ց        | ts     |                                |
| ւ        | v      | (in digraphs: ու→u, իւ→ju)     |
| փ        | p      |                                |
| ք        | k      |                                |
| օ        | o      |                                |
| ֆ        | f      |                                |


**Digraphs:** ու → u (IPA); in Latin Western **ու** → "ou" (between consonants or end), or "v" when **ու** is before a vowel (classical/traditional).

### 5.2 Eastern IPA


| Armenian | IPA | Note |
| -------- | --- | ---- |
| բ        | b   |      |
| պ        | p   |      |
| գ        | g   |      |
| կ        | k   |      |
| դ        | d   |      |
| տ        | t   |      |
| ճ        | tʃ  |      |
| ջ        | dʒ  |      |
| ձ        | dz  |      |
| ծ        | ts  |      |
| ը        | ə   |      |
| թ        | tʰ  |      |
| խ        | χ   |      |
| ղ        | ʁ   |      |
| ռ        | r   |      |
| ր        | ɾ   |      |
| ց        | tsʰ |      |
| փ        | pʰ  |      |
| ք        | kʰ  |      |
| չ        | tʃʰ |      |


(Other letters as in Western where not listed.)

### 5.3 Classical IPA

Same as Eastern IPA in this implementation (traditional Classical values).

### 5.4 IPA context rules

- **ե:** jɛ at word start or after vowel; ɛ elsewhere.  
- **ո:** vo before consonant; ɔ elsewhere.  
- **յ:** h at word start (Western/Classical); j elsewhere.

---

## 6. Verification Examples


| Armenian | Western Latin | Western IPA |
| -------- | ------------- | ----------- |
| պետք     | bedkʼ         | bɛdk        |
| ժամ      | zham          | ʒɑm         |
| ջուր     | chour         | tʃuɾ        |
| ոչ       | vochʼ         | votʃ        |
| իւր      | yoor          | juɾ         |
| յոյս     | hoys          | hojs        |


*(Western Latin uses "ou" for ու to avoid collision with ը→u. BGN/PCGN uses ʼ for aspirates.)*

---

## 7. API Summary

- **to_latin(text, dialect="western"|"eastern"|"classical")** — Armenian → Latin.  
- **to_armenian(roman_text, dialect=...)** — Latin → Armenian.  
- **to_ipa(text, dialect=...)** — Armenian → IPA.  
- **get_armenian_to_latin_map(dialect)** — Armenian → Latin table.  
- **get_latin_to_armenian_map(dialect)** — Latin → Armenian table.  
- **get_armenian_to_ipa_map(dialect)** — Armenian → IPA table.

Implementation: `linguistics/transliteration.py`. Authoritative Western phonetics: `docs/armenian_language_guids/WESTERN_ARMENIAN_PHONETICS_GUIDE.md`.

---

## 8. Full Western Tables (Reference)

**Armenian → Latin (Western):** ա→a, բ→p, գ→k, դ→t, ե→e/ye, զ→z, է→e, ը→u, թ→t, ժ→zh, ի→i, լ→l, խ→kh, ծ→dz, կ→g, հ→h, ձ→ts, ղ→gh, ճ→j, մ→m, յ→y/h, ն→n, շ→sh, ո→o/vo, չ→chʼ, պ→b, ջ→ch, ռ→rr, ս→s, վ→v, տ→d, ր→r, ց→tsʼ, ւ→w, փ→pʼ, ք→kʼ, օ→o, ֆ→f. Digraphs: ու→u, իւ→yoo, և→yev/ev.

**Latin → Armenian (Western):** a→ա, b→պ, ch→ջ, d→տ, dz→ծ, e→ե, g→կ, h→հ, i→ի, j→ճ, k→գ, kh→խ, l→լ, m→մ, n→ն, o→օ, p→բ, r→ր, rr→ռ, s→ս, t→թ, ts→ձ, v→վ, w→ւ, y→յ, z→զ, zh→ժ; plus aspirates tʼ→թ, chʼ→չ, tsʼ→ց, pʼ→փ, kʼ→ք; multi-char vo→ո, ye→ե, u→ու, yoo→իւ, ev/yev→և.

**Armenian → IPA (Western):** See §5.1; digraphs ու→u, իւ→ju.

---

## 9. Ambiguities in Reverse (Latin → Armenian)

- **Western:** **"u"** maps to **ը** (schwa). **"ou"** and **"oo"** map to **ու**. Eastern/Classical: **"u"** maps to **ու** only.
- **"t"** in Western is **թ**; **"d"** is **տ**. In Eastern, **"t"** is **տ** and **"tʼ"** is **թ**.
- **"ye"** and **"vo"** map to **ե** and **ո** (word-initial convention).
- **"v"** in reverse maps to **վ**; when **ու** appears before a vowel it is output as "v" + vowel in Latin, but reverse does not yet convert "v" + vowel back to **ու** (research needed for վ vs ու at end of passive verbs).

