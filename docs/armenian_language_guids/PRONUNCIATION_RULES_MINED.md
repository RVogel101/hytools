# Pronunciation Rules Mined from docs/armenian_language_guids

**Purpose:** Single reference of pronunciation rules extracted from the Western Armenian phonetics guide, quick reference, classical orthography guide, and related docs. Used by `linguistics/transliteration.py` for unwritten schwa insertion and IPA/Latin output.

---

## 1. Context-dependent letters (from WESTERN_ARMENIAN_PHONETICS_GUIDE.md, ARMENIAN_QUICK_REFERENCE.md)

| Letter | Position / context | IPA / Latin | Example |
|--------|--------------------|-------------|---------|
| **յ** | Word-initial | h | յոյս = hoys |
| **յ** | Word-medial or -final | j (y) | բայ = pay |
| **ո** | Before consonant | vo | ոչ = voch, որ = vor |
| **ո** | After consonant or as vowel | o | կո = go |
| **ե** | Word-initial | jɛ / ye | եղ = yegh |
| **ե** | Word-medial or -final | ɛ / e | բեր = ber |
| **ւ** | In diphthongs ու, իւ | u, ju | ուր = oor, իւր = yur |
| **ւ** | Between vowels | v | այւ = ayv |

---

## 2. Unwritten ը (epenthetic schwa) — implementation rules

These rules are applied when generating **pronunciation form** (IPA or Latin with schwa) for Western Armenian.

### 2.1 Word-initial սպ

- **Rule:** Word-initial **սպ** is pronounced with an unwritten **ը** before it.
- **Example:** սպասել → pronounced ըսպասել (uspasel).
- **Source:** User requirement and project convention; document in phonetics guide if not already.

### 2.2 Between two consonants

- **Rule:** Between two consonants (no vowel in between), an unwritten **ը** is often pronounced (epenthetic schwa to break the cluster).
- **Examples:** մնալ → մընալ (mənal); տեսնել → տեսնէլ with possible ը between consonant clusters depending on syllable.
- **Implementation:** After normalization, scan for consecutive Armenian consonants (excluding digraphs like ու, իւ); insert ը between them when building the “pronunciation” string for IPA/Latin. Optionally limit to certain clusters (e.g. մն, սպ, զբ) if full C+C is too aggressive.

### 2.3 Consonant set (for “between two consonants”)

Armenian consonants (single letters, no vowels):  
**բ գ դ զ թ ժ լ խ ծ կ հ ձ ղ ճ մ ն շ չ պ ջ ռ ս վ տ ր ց ւ փ ք ֆ**.  
Vowels (no schwa between): **ա ե է ը ի ո յ օ**.

---

## 3. Voicing reversal (Western only)

From WESTERN_ARMENIAN_PHONETICS_GUIDE.md, ARMENIAN_QUICK_REFERENCE.md:

- բ→p, պ→b; գ→k, կ→g; դ→t, տ→d; ճ→j, ջ→ch; ձ→ts, ծ→dz.
- թ = t (not “th”).

---

## 4. Diphthongs

- **ու** = u (oo). In classical/Western, before a vowel the sequence may be read as **v** + vowel.
- **իւ** = ju (yoo).

---

## 5. Classical orthography (from CLASSICAL_ORTHOGRAPHY_GUIDE.md)

- Use **իւ** not յուղ (e.g. իւղ = oil).
- **ուր** = “where”; **իւր** / **իր** = “his/her”.
- Western does not use **և** inside words; use **եւ** (two characters). **և** only for the word “and”.

---

## 6. References

- `WESTERN_ARMENIAN_PHONETICS_GUIDE.md`
- `ARMENIAN_QUICK_REFERENCE.md`
- `CLASSICAL_ORTHOGRAPHY_GUIDE.md`
- `phonetics_rule_gaps.md`
- `western-armenian-grammar.md`
