# Western Armenian Phonetics Rule Gaps

**Audit Date**: 2026-03-06  
**Moved from**: WesternArmenianLLM (phonetics material not used in training).

## Summary

- **Test words**: 5
- **Eastern leakage detected**: 0
- **Words with rule gaps**: 2

## Key Findings

### 1. Reversed Voicing (բ/պ, դ/տ, գ/կ, ճ/ջ)

Western Armenian has **reversed voicing** from Eastern Armenian:


| Grapheme | WA Phone | WA Voicing | EA Phone | EA Voicing |
| -------- | -------- | ---------- | -------- | ---------- |
| բ        | /p/      | voiceless  | /b/      | voiced     |
| պ        | /b/      | voiced     | /p/      | voiceless  |
| դ        | /t/      | voiceless  | /d/      | voiced     |
| տ        | /d/      | voiced     | /t/      | voiceless  |
| գ        | /k/      | voiceless  | /g/      | voiced     |
| կ        | /g/      | voiced     | /k/      | voiceless  |
| ճ        | /dʒ/     | voiced     | /tʃ/     | voiceless  |
| ջ        | /tʃʰ/    | aspirated  | /dʒ/     | voiced     |
| ձ        | /ts/     | voiceless  | /dz/     | voiced     |
| ծ        | /dz/     | voiced     | /ts/     | voiceless  |


### 2. Contextual ո and ե Behavior

- **ո**: Word-initial → /ʋɔ/ (diphthong), elsewhere → /ɔ/
- **ե**: Word-initial → /jɛ/ (with /j/), elsewhere → /ɛ/

### 3. Classical Orthography Markers (WA-specific)

- **իւ**: /ʏ/ (rounded high front) - retained in WA, reformed away in EA written in the Republic of Armenia
- **եա**: Retained in WA, reformed to յա in EA written in the Republic of Armenia

## Per-Word Analysis

(Original per-word analysis preserved from audit.)

## Conclusion

1. A dedicated phonetics/G2P module lives in **armenian-corpus-core** (e.g. `linguistics/phonetics.py`).
2. Voicing reference and vocabulary filter are in **linguistics.metrics**.
3. Contextual rules for ո/ե and classical orthography (իւ, եա) are documented here for implementation in core.
4. **Recommendation**: Implement full G2P in armenian-corpus-core with contextual rules and digraph handling.

