# Western Armenian Keyboard for Android: Implementation Research

Deep research on building a Western Armenian keyboard (IME) for Android: timeline, parts, feasibility, templates, and implementation paths.

---

## Executive summary

| Aspect | Summary |
|--------|--------|
| **Feasibility** | **High.** Multiple viable paths: extend existing open-source IME (AnySoftKeyboard), use Keyman Engine, or build a minimal custom IME from a template. |
| **Timeline (minimal)** | **2–4 weeks** for a basic Western Armenian layout using a template or language pack. |
| **Timeline (full-featured)** | **2–4 months** for suggestions, long-press, symbols, and polish if building custom or heavily customizing. |
| **Recommended path** | **Option A (AnySoftKeyboard pack)** for fastest ship with suggestions and ecosystem; **Option B (Keyman)** if you need a standalone app or cross-platform reuse; **Option C (custom IME)** only if you need full control and accept maintenance cost. |

---

## 1. Implementation approaches

### Option A: AnySoftKeyboard language pack (fastest)

- **What:** Add a Western Armenian layout and optional dictionary as a **language pack** for [AnySoftKeyboard](https://github.com/AnySoftKeyboard/AnySoftKeyboard) (Apache 2.0).
- **Pros:** No IME framework code to write; suggestions, themes, gesture typing already supported; F-Droid distribution; existing [Armenian pack](https://f-droid.org/en/packages/com.anysoftkeyboard.languagepack.armenian2/) (`armenian2`) to reference or fork.
- **Cons:** Depends on AnySoftKeyboard app; LanguagePack repo is [deprecated](https://github.com/AnySoftKeyboard/LanguagePack) (but packs still build and work); need to confirm whether current Armenian pack is Western or Eastern and adapt.
- **Artifacts:** New Android library module with:
  - `res/xml/keyboards.xml` (register layout)
  - `res/xml/<layout>.xml` (key rows/keys; key labels in Armenian Unicode)
  - `res/xml/dictionaries.xml` (optional word list for suggestions)
  - `res/values/strings.xml` and `values-hy` (or `values-hy-arevela` for Western) for labels
- **Effort:** ~1–3 weeks for layout + optional dictionary, assuming one layout variant.

### Option B: Keyman Engine for Android

- **What:** Use [Keyman Engine for Android](https://help.keyman.com/developer/engine/android/) to ship your own app that loads a Western Armenian keyboard (.kmn → compiled .js + touch layout).
- **Pros:** Full control over layout and packaging; [Keyman Developer](https://keyman.com/developer/) for designing keyboards; same keyboard can target Android, iOS, desktop, web; SIL’s long-standing support for minority scripts.
- **Cons:** Users install a separate Keyman app or you embed the engine; Western layout is [deprecated](https://help.keyman.com/keyboard/armenian_west/current-version) in Keyman’s catalog (you’d use or adapt it); need to learn .kmn and touch-layout format.
- **Artifacts:**
  - `.kmn` source (key rules, dead keys if any)
  - Keyman touch layout (visual layout for phones)
  - Build with Keyman Developer → .js + assets; package per [distribution guide](https://help.keyman.com/developer/current-version/guides/distribute/packages).
- **Effort:** ~2–4 weeks for layout design, touch layout, testing, and store packaging.

### Option C: Custom IME from scratch / template

- **What:** Build a minimal Android IME that extends `InputMethodService` and shows a Western Armenian keyboard UI.
- **Pros:** No dependency on third-party IME app; can be a single, small APK; full control over UX and behavior.
- **Cons:** You own all code (lifecycle, input connection, optional suggestions, settings); `KeyboardView` is deprecated (API 29+); need to handle subtypes, multiple layouts (letters/symbols), and testing across devices.
- **Artifacts:** One Android app with:
  - Service extending `InputMethodService`
  - Input view (keyboard UI) and optional candidates view
  - XML keyboard definitions or custom view
  - Manifest with IME declaration and optional settings activity
- **Effort:** ~3–6 weeks for a minimal but robust keyboard; 2–4 months if you add suggestions, symbols, long-press, and polish.

---

## 2. Timeline (by path)

| Phase | AnySoftKeyboard pack | Keyman | Custom IME |
|-------|----------------------|--------|------------|
| Setup / clone / env | 1–2 days | 2–3 days | 2–5 days |
| Layout design (keys + Unicode) | 3–5 days | 3–5 days | 5–7 days |
| Integration / build | 2–5 days | 5–7 days | 1–2 weeks |
| Dictionary (optional) | 3–7 days | N/A (or external) | 1–2 weeks |
| Testing + devices | 3–5 days | 3–5 days | 5–10 days |
| Store / F-Droid packaging | 2–3 days | 2–3 days | 2–3 days |
| **Total (minimal)** | **~2–3 weeks** | **~2–4 weeks** | **~3–6 weeks** |
| **Total (with suggestions)** | **~3–4 weeks** | **N/A** | **~2–4 months** |

---

## 3. Parts and components

### 3.1 Android IME (all custom/standalone approaches)

- **Manifest:** IME service with `BIND_INPUT_METHOD`, intent filter `android.view.InputMethod`, metadata (e.g. `res/xml/method.xml`) for subtypes and optional `android:settingsActivity`.
- **Core service:** Class extending `InputMethodService`:
  - `onCreateInputView()` → return keyboard view.
  - `getCurrentInputConnection()` → `commitText()`, `setComposingText()`, `deleteSurroundingText()` for sending text.
  - Optional: `onCreateCandidatesView()` for suggestions; handle `EditorInfo.inputType` for number/URL/password layouts.
- **Keyboard UI:** Either:
  - **Deprecated but still used:** `KeyboardView` + `Keyboard` from AOSP (or copy from [hijamoya/KeyboardView](https://github.com/hijamoya/KeyboardView) to avoid deprecation warnings). Layout defined in XML with `<Keyboard>`, `<Row>`, `<Key>`; `android:codes` = Unicode code point (e.g. 0x0561 for ա).
  - **Modern:** Custom view (e.g. `RecyclerView` of keys or custom `ViewGroup`) that calls `InputConnection.commitText()` on tap.
- **Subtypes:** In `method.xml`, define `hy` (Armenian) locale and optionally `hy-arevela` (Western) vs `hy-arevmda` (Eastern) for correct system labeling.
- **Optional:** Settings activity, IME switcher key (`switchToNextInputMethod()`), numeric/symbol layouts.

### 3.2 Western Armenian layout content

- **Script:** Armenian Unicode block **U+0530–U+058F** (see [Unicode nameslist](https://unicode.org/charts/nameslist/n_0530.html)).
- **Letters:** 38 main letters (uppercase U+0531–U+0556, lowercase U+0561–U+0586); plus ligature **և** (U+0587). Use classical orthography (e.g. **իւ** for “oil”) per project standards.
- **Punctuation / marks:** Armenian comma ՝ (U+055D), emphasis ՛ (U+055B), exclamation ՜ (U+055C), question ՞ (U+055E), apostrophe ՚ (U+055A), full stop ։ (U+0589), hyphen ֊ (U+058A), left/right angle quotes « » (often U+00AB/U+00BB or Armenian equivalents).
- **Reference layout:** “Western Armenian (Legacy)” (Windows KBDARMW) — [kbdlayout.info](http://kbdlayout.info/KBDARMW/) and [Armeniapedia](https://www.armeniapedia.org/wiki/Western_Armenian_Keyboard_Layout) give the physical key arrangement. Same 38+1 letters as Eastern; difference is **key placement**, not character set.

### 3.3 Western vs Eastern (keyboard)

- **Character set:** Identical (Unicode Armenian block).
- **Difference:** Key-to-letter mapping. Western (Legacy) follows the KBDARMW arrangement; Eastern (Legacy) follows KBDARME. For a “Western Armenian” product you implement the Western (Legacy) or a phonetic layout labeled for Western Armenian.
- **Locale:** Use `hy` or `hy-arevela` (Western) in IME subtype so the system shows “Armenian (Western)” or similar.

### 3.4 AnySoftKeyboard pack specifics

- **Layout XML:** Same idea as AOSP: rows of keys; each key has a code (Unicode) and label. Copy structure from [LanguagePack English](https://github.com/AnySoftKeyboard/LanguagePack/blob/master/languages/english/pack/src/main/res/xml/eng_16keys.xml) or another language; replace with Western Armenian key codes and labels.
- **keyboards.xml:** Register the new layout and set display name, locale.
- **dictionaries.xml:** Optional; point to a word list for suggestions (Western Armenian vocabulary).
- **Build:** Gradle; output is an APK that users install alongside AnySoftKeyboard.

### 3.5 Keyman specifics

- **Source:** `.kmn` (keyboard rules) + touch layout (on-screen key positions).
- **Keyman Developer:** Create keyboard project → define key output and rules → build → get .js + assets for Android.
- **Android:** Either user installs Keyman app and your keyboard, or you embed [Keyman Engine for Android](https://help.keyman.com/developer/engine/android/) and ship keyboard with your app.

---

## 4. Key mapping strategies for Western Armenian

### 4.1 Design goals (Western Armenian–specific)

- **Respect Western Armenian phonology:** Keep frequently used consonants and vowels under the strongest fingers and easy bigram paths (e.g. բան, տուն, պիտի, պիտի, պիտի / պիտի, կը / bidi, gu, etc.).
- **Minimize cognitive load for existing users:**
  - Offer at least one layout close to **Windows Western Armenian (KBDARMW)** for users who already touch-type.
  - Offer an alternative **phonetic QWERTY** layout for users coming from Latin keyboards.
- **Make digraphs and diphthongs fast:**
  - Single-tap or long-press for common sequences like **ու**, **իւ**, **եա**, **աւ**, **ոյ**.
  - Consider dedicated keys for **և** and the Armenian punctuation marks.
- **Thumb ergonomics (phones):** Put highest-frequency letters in the **center columns of rows 2–3**, since that is where thumbs rest in portrait.

### 4.2 High-letter-count strategies

- **Legacy typewriter-style (KBDARMW-compatible):**
  - Map keys exactly as on Windows Western Armenian.
  - Pros: zero retraining for experienced typists; matches existing documentation.
  - Cons: not intuitive for new learners; not optimized for thumbs.
- **Phonetic QWERTY-style:**
  - Map Armenian letters to Latin keys roughly by sound (e.g. `p` → բ/պ pair, `k` → գ/կ pair, `j` → ճ, `c` → ծ/ց pair).
  - Pros: low barrier for users who think in QWERTY; easier to remember.
  - Cons: requires a clear set of Western Armenian–centric phonetic choices (respecting reversed voicing, ջ=ch, ճ=j, ձ=ts, ծ=dz, etc.).
- **Frequency-optimized / thumb-first:**
  - Use corpus frequencies (Western Armenian) to place the top 8–10 letters on the home/center columns, with frequent bigrams on easy thumb rolls.
  - Pros: potentially faster with practice.
  - Cons: non-standard; harder to learn; more design work.

### 4.3 Handling digraphs, diphthongs, and punctuation

For Western Armenian, important multi-character units and marks include:

- **Diphthongs / letter sequences:**
  - **ու**, **իւ**, **եա**, **աւ**, **ոյ**, and orthographic pairs like **ի՛նք**, **ու՛ր**.
- **Ligatures / single code points:**
  - **և** (U+0587) – should almost certainly be a **dedicated key** or long-press from **ե** or **ւ**.
- **Punctuation:**
  - ՝ (comma), ՛ (emphasis), ՜ (exclamation), ՞ (question), ։ (full stop), ֊ (hyphen), «», ՚ (apostrophe).

Implementation patterns:

- **Long-press menus on base vowels:**
  - Long-press ի to show **ի + ւ → իւ**, long-press ու to show variant pairs if desired.
  - Long-press ե or ւ to insert **և** directly (single code point).
- **Dedicated keys on main layout:**
  - Put **և**, ՝, ՛, ՞ on the right side of the main layout, replacing some Latin punctuation.
  - Consider a dedicated **ու** key if analysis shows it is among the top bigrams; otherwise, make it a long-press on ու or ու’s components.
- **Smart composition (optional):**
  - IME-level rule: if the user types ե + ւ quickly, temporarily show a composing **և** candidate; commit as either two letters or ligature depending on setting.

### 4.4 Draft Western Armenian layouts (phone, portrait)

Below are **conceptual** draft layouts. Actual implementation would map each Armenian character to its Unicode code point in the XML or touch layout.

#### Layout A: Legacy-friendly (close to KBDARMW)

Goal: familiar to Windows Western Armenian users; minimal surprises.

- **Row 1 (numbers + punctuation):**
  - Digits 1–0, with Armenian comma ՝, question ՞, exclamation ՜, and «» in long-press menus.
- **Row 2 (roughly QWERTY row):**
  - Map to KBDARMW equivalents (conceptually): `q w e r t y u i o p` → `խ վ է ր դ ե ը ի ո բ`
  - Keep **ո, բ, ե** under strong fingers; place **և** as long-press on ե or ւ.
- **Row 3:**
  - `a s d f g h j k l ;` → `ա ս տ ֆ կ հ ճ ք լ թ`
- **Row 4:**
  - `z x c v b n m` → `զ ց գ ւ պ ն մ`
  - Long-press ւ for **ու**, **իւ**; long-press զ for related symbols if desired.

This layout mainly documents “copy KBDARMW row-by-row” while adding smartphone-friendly long-presses for **ու**, **եւ**, punctuation.

#### Layout B: Phonetic QWERTY (WA-aware)

Goal: make sense for a Western Armenian speaker who thinks phonetically in Latin letters, respecting reversed voicing and affricate mappings.

Example mapping sketch (lowercase row only; actual mapping should be iterated with speakers and corpus stats):

- **Row 2 (QWERTY):** `q w e r t y u i o p`
  - Map **t-like** consonants and vowels: e.g. տ, թ, դ, ե, ը, ի, ո, ու, պ/բ.
  - Example: `t` → տ, `d` → դ, `p` → պ, `b` → բ (via long-press on `p` key), `k`/`g` mapping respects բ=p, պ=b, etc. from the WA voicing table.
- **Row 3 (QWERTY):** `a s d f g h j k l ;`
  - Vowels on **a/e/o** positions (ա, է, օ), common consonants on s, d, f, g, h.
  - Put **ջ=ch** and **ճ=j** on intuitive keys (`c` vs `j`) with long-press pairs for each affricate pair (ջ/ճ, ձ/ծ).
- **Row 4 (QWERTY):** `z x c v b n m`
  - Reserve `c`/`z` cluster for **ծ/ց/ձ** triplet (dz/ts group).
  - Put **շ, ս, խ, ղ** on strong thumb positions.

Digraph handling in this layout:

- Long-press **o** or ու key position for **ու**.
- Long-press **y**-mapped key (յ) for sequences like **յու**, **իւ**.
- Dedicated **և** key on the right edge of row 2 or 3 (under thumb).

#### Layout C: Thumb-optimized modern (frequency-first)

Goal: treat the keyboard as a fresh surface; cluster the **top 10–12 letters by frequency** in the center, around the thumbs.

Conceptual steps:

- Use your Western Armenian corpus to extract letter and bigram frequencies.
- Put the top ~8 letters (likely ա, ի, ն, ս, տ, կ, ր, ո / etc.) in the **middle 4–6 keys of rows 2–3**.
- Place **ու** as a dedicated key in the center-right, because it is very frequent and is two code points.
- Cluster affricate pairs:
  - One key shows ճ (tap) + long-press for its pair.
  - One key shows ջ (tap) + long-press for its pair.
  - Similarly for ծ/ց/ձ.
- Put punctuation keys **(՝, ՛, ՞, ։)** along the right edge, under the right thumb.

This layout is the most experimental but could give best speed once learned. It is best combined with:

- Onboarding diagrams in the app settings.
- An in-keyboard quick cheat-sheet (press-and-hold space to show mini layout help).

---

## 5. Feasibility

- **Technically:** Straightforward. Armenian is well supported in Unicode; Android’s IME API is stable; reference layouts exist (KBDARMW, Keyman, AnySoftKeyboard armenian2).
- **Resource-wise:** One developer can deliver a minimal Western Armenian keyboard in 2–4 weeks (pack or Keyman) or 3–6 weeks (custom). Adding suggestions and polish increases time (especially for custom).
- **Risks:** (1) AnySoftKeyboard LanguagePack repo deprecated — still buildable, but long-term may need to move to app-internal packs or fork. (2) KeyboardView deprecation — either copy AOSP implementation or build a simple custom key view. (3) Western vs Eastern — ensure layout and locale are clearly Western so users and documentation are not confused.

---

## 6. Templates and references

### 6.1 Minimal Android IME

- **[BasicKeyboard](https://github.com/modularizer/BasicKeyboard)** (Kotlin): Barebones IME, single-file `KeyboardService.kt`; good starting point to replace QWERTY with Armenian keys.
- **[SimpleKeyboard](https://github.com/mmahmad/SimpleKeyboard)**: Another minimal template (no emoji/suggestions).
- **AOSP SoftKeyboard**: [samples/SoftKeyboard](https://android.googlesource.com/platform/development/+/master/samples/SoftKeyboard) — reference for `InputMethodService`, XML keyboard format, and lifecycle.
- **KeyboardView copy:** [hijamoya/KeyboardView](https://github.com/hijamoya/KeyboardView) — drop-in for deprecated `KeyboardView`/`Keyboard`.

### 6.2 Layout and Unicode

- **Western Armenian key arrangement:** [Armeniapedia – Western Armenian Keyboard Layout](https://www.armeniapedia.org/wiki/Western_Armenian_Keyboard_Layout) (tables for lower/upper).
- **KBDARMW (Windows):** [kbdlayout.info KBDARMW](http://kbdlayout.info/KBDARMW/) — scancodes, shift states, download (KLC, JSON, etc.) for exact mapping.
- **Unicode:** [Unicode Armenian block (U+0530)](https://unicode.org/charts/nameslist/n_0530.html) — all letters and punctuation with code points.

### 6.3 Existing Armenian keyboards

- **AnySoftKeyboard Armenian:** [F-Droid – Armenian for AnySoftKeyboard](https://f-droid.org/en/packages/com.anysoftkeyboard.languagepack.armenian2/) — check if Western or Eastern and reuse/fork layout ideas.
- **Keyman Armenian:** [Keyman – Armenian Unicode](https://keyman.com/keyboards/armenian); [Armenian (Western) deprecated](https://help.keyman.com/keyboard/armenian_west/current-version) — can be used as reference or base for a Western-labeled layout.

### 6.4 Official Android

- **Creating an input method:** [Android Developers – Create an input method](https://developer.android.com/develop/ui/views/touch-and-input/creating-input-method) — lifecycle, manifest, sending text, subtypes, UI considerations.

---

## 7. Implementation checklist (custom IME)

- [ ] Android project (Kotlin/Java), minSdk 21+ (or 24+ for simpler testing).
- [ ] `InputMethodService` subclass; register in manifest with `BIND_INPUT_METHOD` and `android.view.InputMethod`; `method.xml` with subtype `hy` or `hy-arevela`.
- [ ] Input view: either KeyboardView (from AOSP/hijamoya) + XML or custom view; keys send Unicode via `getCurrentInputConnection().commitText(String, 1)`.
- [ ] One or more XML keyboards (or code-built `Keyboard`) with Western Armenian layout (KBDARMW-based or phonetic); key codes = Unicode code points (e.g. 0x0561 for ա).
- [ ] Shift state: alternate set of key codes for uppercase (U+0531–U+0556) and և (U+0587); optionally caps lock.
- [ ] Optional: symbol/secondary layout (numbers, punctuation, « » ։ ՝ etc.).
- [ ] Optional: settings activity; IME switcher key.
- [ ] Test on multiple devices and API levels; verify Armenian text in notes, browser, and search.

---

## 8. Recommendation

- **Ship quickly with suggestions:** Fork or clone the AnySoftKeyboard Armenian language pack, confirm/correct layout for Western (KBDARMW), add or tune dictionary, publish as “Western Armenian” pack (e.g. F-Droid). **Timeline: 2–3 weeks.**
- **Standalone app or cross-platform:** Use Keyman Developer to create/adapt a Western Armenian keyboard and touch layout; distribute via Keyman app or embed Keyman Engine in your app. **Timeline: 2–4 weeks.**
- **Full control, minimal deps:** Use BasicKeyboard (or SimpleKeyboard) as template; replace layout with Western Armenian XML (Unicode codes from this doc); copy KeyboardView if targeting API 29+; add symbols and optional suggestions. **Timeline: 3–6 weeks minimal, 2–4 months with suggestions and polish.**

---

## 9. References (URLs)

- Android: [Create an input method](https://developer.android.com/develop/ui/views/touch-and-input/creating-input-method)
- AnySoftKeyboard: [GitHub](https://github.com/AnySoftKeyboard/AnySoftKeyboard), [LanguagePack](https://github.com/AnySoftKeyboard/LanguagePack), [Armenian on F-Droid](https://f-droid.org/en/packages/com.anysoftkeyboard.languagepack.armenian2/)
- Keyman: [Keyman for Android](https://keyman.com/), [Engine for Android](https://help.keyman.com/developer/engine/android/), [Armenian Western (deprecated) help](https://help.keyman.com/keyboard/armenian_west/current-version)
- Layout: [Armeniapedia Western Armenian Keyboard](https://www.armeniapedia.org/wiki/Western_Armenian_Keyboard_Layout), [KBDARMW kbdlayout.info](http://kbdlayout.info/KBDARMW/)
- Unicode: [Armenian block U+0530](https://unicode.org/charts/nameslist/n_0530.html)
- Templates: [BasicKeyboard](https://github.com/modularizer/BasicKeyboard), [SimpleKeyboard](https://github.com/mmahmad/SimpleKeyboard), [hijamoya/KeyboardView](https://github.com/hijamoya/KeyboardView)

---

*Document generated from research for the Western Armenian keyboard Android implementation. Update as you choose a path and implement.*
