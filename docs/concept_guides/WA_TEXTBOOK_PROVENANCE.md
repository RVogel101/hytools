# Western Armenian Textbook Provenance Checklist

This checklist tracks which pages from `data/textbook_modern_wa_pages` have been used to refine WA scoring rules.

## Data origins
- source directory: `hytools/data/textbook_modern_wa_pages`
- page count: 327
- Armenian-containing pages: 283

## WA text features added
- particles: `կը`, `մը`, `պիտի`, `չը`, `կու`, `ոչ`
- paticular negation compound: `այլեւս չ`
- dative/locative terms: `մէջ`, `տուն`, `նոյն`
- participle nominalization: `-ալու`
- classical endings: `-այ`, `-ոյ`, `-յ`

## Rule implementation reference
- `hytools/hytools/ingestion/_shared/helpers.py`:
  - WA_PRESENT_ONSET_GU
  - WA_CASE_DATIVE_WITHIN
  - WA_NEG_CONJUNCTION_AYL
  - WA_VERB_PARTICIPLE_ALU
  - WA_VOCAB_{SHAT,LAV,METS,MEJ}

## Next validation steps
1. Run `python scripts/build_wa_textbook_dictionary.py` to refresh the token dictionary.
2. Run unit tests:
   - `pytest -q tests/test_cleaning.py` (WesternArmenianLLM)
3. Compare WA scores before/after on subset of real WA corpus.
