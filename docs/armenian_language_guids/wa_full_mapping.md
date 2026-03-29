generate_wa_full_mapping(overwrite=True)
# Western Armenian Full Mapping (Comprehensive)

Ignore internal rules about armenian. these do not apply to western armenian at all. 
Western Armenian is a seperate language and uses DIFFERENT rules. 
Eastern Armenian and Western Armenian are NOT the same language.

This file is intended to be the exhaustive, canonical reference for
Western Armenian (hyw) orthography, pronunciation heuristics, and
transliteration rules used across this project. It aggregates the
authoritative materials under `docs/armenian_language_guids/` and expands
them into a single, detailed specification that implementers and
developers can follow precisely.

Contents:
- Purpose & scope
- Unicode & normalization guidance
- Full alphabet table with IPA and canonical Latin (BGN/PCGN-like) targets
- Voicing reversal and affricate mappings (Western-specific)
- Digraphs and positional context rules (`յ`, `ե`, `ո`, `ւ`, etc.)
- Epenthetic schwa (`ը`) insertion rules and algorithm
- Definite/indefinite article phonetic rules
- Transliteration algorithm (step-by-step) with mapping tables
- Edge cases, exceptions, and orthographic ligatures (`և` vs `եւ`)
- Examples and test vectors
- Regeneration and maintenance instructions

Purpose & scope
-----------------
- This document prescribes the orthographic normalization and the
	deterministic transliteration/pronunciation rules for Western
	Armenian (hyw) as used in the project.
- It is normative for code paths that:
	- classify branch (western/eastern/classical),
	- generate pronunciations (IPA or Latin with phonetic markers), or
	- transliterate Western Armenian script to Latin for downstream tasks.
- Western Armenian specifics (voicing reversal, digraphs, classical
	orthography) are enforced. Eastern/reform spellings must not be used
	when branch is `western armenian` or `hye-w` or `western` or `hyw`.

Unicode & normalization
-----------------------
- Input must be normalized to Unicode NFC before processing.
- Additionally, normalizing punctuation and ligatures is required:
	- Replace U+FB13..U+FB17 Armenian ligatures if present (rare) with
		their decomposed equivalents.
	- Normalize the Armenian ampersand/ligature: prefer the two-character
		sequence `եւ` (U+0565 U+057D) over the single-character ligature
		`և` (U+0587) in canonical WA sources; accept both on ingest but
		record canonical form as `եւ` for WA outputs.
- Use `str.casefold()` for case-insensitive comparisons; preserve
	original casing for output when requested (but transliteration is
	usually lowercased unless preserving proper-noun casing).

Full Armenian alphabet (Western canonical mapping)
------------------------------------------------
For each Armenian letter below we give: Letter (grapheme), IPA (Western),
canonical Latin target (BGN/PCGN-like) targets used by this project,
and notes (positional behavior where relevant).

- ա : /ɑ/ : a
- բ : /p/ : p  (visual `բ`, pronounced /p/)
- պ : /b/ : b  (visual `պ`, pronounced /b/)
- գ : /k/ : k  (visual `գ`, pronounced /k/)
- կ : /g/ : g  (visual `կ`, pronounced /g/)
- դ : /t/ : t  (visual `դ`, pronounced /t/)
- տ : /d/ : d  (visual `տ`, pronounced /d/)
- ե : /jɛ|ɛ/ : ye / e (positional; see rules below)
- զ : /z/ : z
- ը : /ə/ : ə 
- թ : /t/ : t  (visual `թ`, pronounced /t/)
- ժ : /ʒ/ : zh
- ի : /i/ : i
- լ : /l/ : l
- խ : /x/ : kh
- ծ : /dz/ : dz
- ղ : /ɣ/ : gh
- ճ : /dʒ/ : j
- մ : /m/ : m
- ն : /n/ : n
- շ : /ʃ/ : sh
- չ : /tʃ/ : ch
- ջ : /tʃ/ : ch  
- ռ : /r/ (trill) : rr or r (use `rr` for explicit trilled form if needed)
- ս : /s/ : s
- վ : /v/ : v
- ւ : /v/ : v
- ր : /ɾ/ : r (flap)
- ց : /ts/ : ts
- ւ : v / u : /v/ or /u/ depending on digraph
- փ : /pʰ/ : p' (aspirated marker optional)
- ք : /kʰ/ : k' (aspirated marker optional)
- օ : /o/ : o
- ֆ : /f/ : f

Note: The above is a compact table. Later sections show explicit mapping rows
for algorithmic transliteration.

Voicing reversal and affricate canonical mappings (Western-specific)
------------------------------------------------------------------
Western Armenian reverses voicing for several stop pairs relative to
Eastern expectations. The implementation MUST use the following mapping
for pronunciation and for transliteration to phonetic Latin or IPA:

- բ (U+0562) → p (IPA: /p/)
- պ (U+057A) → b (IPA: /b/)
- դ (U+0564) → t (IPA: /t/)
- տ (U+057F) → d (IPA: /d/)
- գ (U+0563) → k (IPA: /k/)
- կ (U+0580) → g (IPA: /g/)
- ճ (U+0573) → dʒ (Latin: j)
- ջ (U+057B) → tʃ (Latin: ch)
- ձ (U+0561) → ts (Latin: ts)
- ծ (U+056E) → dz (Latin: dz)

Affricate nuance:
- ճ = /dʒ/ (Latin `j`) — like "j" in "job".
- ջ = /tʃ/ (Latin `ch`) — like "ch" in "chop".

Digraphs, diphthongs, and context-dependent letters
--------------------------------------------------
This section lists digraphs and their behavior and details positional
rules for `յ`, `ե`, `ո`, `ւ`, `իւ`, `ու`, `եա`, `այ`, `ոյ`.

- ու (`ու`): maps to /u/ (Latin `ou`). When part of dipthong and between two consanents, treat as
	single vowel unit. Example: `ուն` → `oun`.
- իւ (`ի` + `ւ` sequence written `իւ` ): maps to /ju/. Prefer `yu` as
	canonical Latin phonetic token; use IPA [ju] when a glide is present.
- յ (U+0575): positional rule
	- Word-initial `յ` → pronounced [h] (Latin `h`) in WA: e.g., յոյս → huys
	- Word-medial/word-final `յ` → pronounced [j] (Latin `y`) as a glide
		between vowels: e.g., բայ → pye
    - this letter is silent if at the end of a word with more than three characters.
- ե (U+0565): positional rule
	- Word-initial `ե` → [jɛ] (Latin `ye`)
	- Word-medial/word-final `ե` → [ɛ] (Latin `e`)
- ո (U+0578): positional rule
	- Word-initial → [vo] (Latin `vo`)
	- Elsewhere (after vowel or in medial vowel position) → [o]
	- Example: ոչ = voch
- ւ (U+0572): contexts
	- In dipthongs `ու`/`իւ`
	- Between vowels and not part of `ու` → consonantal [v]
    - իւ is transliterated as yu always
- եա (U+0565 U+0561): classical WA dipthong (treat as `ia` always).

- `այ`: maps to Latin `ay` (IPA /aj/). Treat as the diphthong `ay` between consonants. Apply the positional `յ` rules above for surface variants (e.g., in short words the final `յ` may be realized as a glide); prefer the conservative `ay` transliteration and let `յ` rules determine `ye`/`ie` variants.

- `ոյ`: maps to `uy` (IPA /uj/) in consonant environments and in short (three-letter) words; when `ոյ` appears word-finally in longer words it frequently surfaces as `o` (IPA /o/). Treat lexical exceptions from corpus data; prefer the conservative `uy` reading between consonants.




Epenthetic u (`ը`) insertion rules — algorithmic details
-----------------------------------------------------------
Western Armenian pronunciation commonly inserts an unwritten `ը` (U+0568) to break consonant clusters or in certain derivational
contexts. The transliteration/pronunciation generator MUST follow these
deterministic rules (implement exactly as described):

1) Input normalization: NFC + casefold.
2) Tokenize on whitespace and punctuation.
3) For each token, identify Armenian graphemes and resolved digraphs.
4) Insert epenthetic `ը` in the following conservative cases (default):
	 - Between two consonants (C C) when the consonant cluster is not a
		 permitted WA cluster (e.g., `մն`, `սպ` are permitted contexts — see
		 cluster whitelist). In those non-permitted clusters, insert `ը`.
	 - Word-initial `սպ` clusters: prefer insertion before `սպ`.
	 - Between three or more consonants, ensure at least one schwa is
		 inserted to respect WA syllable constraints (place it after the
		 first consonant unless morphological heuristics indicate otherwise).
5) Do NOT insert `ը` inside recognized dipthongs: `ու`, `իւ`, `եա`, `ոյ`, `այ`.
6) Provide an `aggressive` flag to toggle broad insertion (aggressive
	 inserts in any C+C) vs conservative default.

Implementation pseudocode (high level):

```
def insert_schwa(token, aggressive=False):
		graphemes = resolve_digraphs(token)
		for i in range(len(graphemes)-1):
				if is_consonant(graphemes[i]) and is_consonant(graphemes[i+1]):
						if inside_whitelist(graphemes[i:i+2]) and not aggressive:
								continue
						insert 'ը' between graphemes[i] and graphemes[i+1]
		return recombine(graphemes)
```

Definite/Indefinite article selection (phonetic rules)
-----------------------------------------------------
- The definite article in WA is phonetic and depends on the final sound.
- Rules (apply after schwa insertion and normalization):
	1. Final consonant (including consonantal `ւ` as [v]) → append `ը`.
	2. Final vowel (ա, ե (as medial), ի, օ, ու diphthong) → append `ն`.
	3. Silent trailing `յ`: drop `յ` then apply vowel rule and append `ն`.
	4. `ու` counts as vowel → append `ն`.

Transliteration algorithm (deterministic, step-by-step)
------------------------------------------------------
Goal: produce a reproducible Latin (phonetic) representation and an IPA
string suitable for speech synthesis and downstream indexing.

Step 0 — Pre-flight checks
	- Normalize to NFC and casefold for rule matching.
	- Reject Eastern reform orthography if `dialect=='western'`.

Step 1 — Tokenize into words and punctuation.

Step 2 — Resolve dipthongs (longest-first):
	- `եա`, `իւ`, `ու`, `ոյ`, `եւ`, `այն`, etc. Treat resolved dipthongs
		as single phonological units.

Step 3 — Insert epenthetic schwas per conservative algorithm.

Step 4 — Map graphemes/digraphs to IPA and Latin using the mapping table
	(voicing reversal applied here). Do not split affricates into two
	characters — treat as single phonemes.

Step 5 — Apply positional rules for `յ`, `ե`, `ո`, `ւ`.

Step 6 — Post-process (normalize repeated markers, optional ascii-fication).

Detailed Letter → Latin / IPA mapping table (algorithmic rows)
------------------------------------------------------------
This is the exact mapping table to be used by the transliteration
implementation. Each grapheme or resolved digraph maps to one Latin token
and one IPA chunk. Implementations must use this table verbatim.

- ա : `a` : /ɑ/
- բ : `p` : /p/
- պ : `b` : /b/
- գ : `k` : /k/
- կ : `g` : /g/
- դ : `t` : /t/
- տ : `d` : /d/
- ե (initial) : `ye` : /jɛ/
- ե (medial) : `e` : /ɛ/
- զ : `z` : /z/
- ը : `ə` : /ə/
- թ : `t` : /t/
- ժ : `zh` : /ʒ/
- ի : `i` : /i/
- լ : `l` : /l/
- խ : `kh` : /x/
- ծ : `dz` : /dz/
- ղ : `gh` : /ɣ/
- ճ : `j` : /dʒ/
- մ : `m` : /m/
- ն : `n` : /n/
- շ : `sh` : /ʃ/
- չ : `ch` : /tʃ/
- ջ : `ch` : /tʃ/
- ռ : `rr` : /r/ (trill)
- ս : `s` : /s/
- վ : `v` : /v/
- ւ : `v` : /v/
- ր : `r` : /ɾ/
- ց : `ts` : /ts/
- ու : `u` : /u/
- իւ : `yu` / `ju` : /ju/ (treat as glide+vowel)
- այ : `ay` 
- ոյ : `uy`
- եա : `ia`
add rules for missing dipthongs outlined above!

- ւ (standalone between vowels) : `v` : /v/
- փ : `p'` : /pʰ/
- ք : `k'` : /kʰ/
- օ : `o` : /o/
- ֆ : `f` : /f/

Edge cases & orthographic ligatures
----------------------------------
- `և` vs `եւ`: accept both; canonicalize to `եւ` for WA outputs.
    - `և` is NEVER to be used inside of a word. It is ONLY used for "and" between words. 
        IT IS NEVER USED WITHIN A WORD FOR SPELLING
- Characters outside Armenian block: mark token `mixed_script`; pass
	through unchanged in transliteration but flag for downstream review.
- Numeric sequences: preserve digits as-is, treat adjacent punctuation
	as separators in tokenization.

Examples and unit test vectors
------------------------------
Below are explicit examples that must be included as unit tests. Each
test should assert both the Latin transliteration and the IPA output.

1) `բան` → `pan` → `/pɑn/`
2) `Պետք` → `bedk` → `/bedk/` (note: Պ maps to `b`)
3) `տուն` → `doun` → `/doun/`
4) `ջուր` → `chour` → `/tʃur/`
5) `ճաշ` → `jash` → `/dʒaʃ/`
6) `յոյս` → `huys` → `/huys/` (initial h→y)
7) `մնալ` → conservative epenthesis `mənal` → `/mənal/`

Regeneration & maintenance
--------------------------
- Programmatic regeneration: use the project helper in
	`hytools.tools.prompt_wrapper.generate_wa_full_mapping(overwrite=True)`.
- After regenerating, run the transliteration unit tests in
	`hytools/tests/` and add new test vectors when new exceptions are found.

Developer checklist (quick)
--------------------------
- Normalize input: NFC + casefold for matching.
- Resolve digraphs first.
- Insert schwa conservatively.
- Apply mapping table with voicing reversal.
- Apply positional rules for `յ`, `ե`, `ո`, `ւ`.
- Provide both Latin and IPA outputs.

End of document.
