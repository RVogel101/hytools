# Agent Command Rules (Runtime Behavior)

This document captures the authoritative command policy for how the assistant responds to shell/PowerShell invocation questions.

## Rule summary
1. Never guess PowerShell command forms. Always derive from actual code in the repository.
2. Confirm the exact entrypoint and options from source code before responding.
3. For this repository, the CLI is `hytools.ingestion.runner` and the valid commands are `run`, `status`, `list`, `dashboard` (as implemented in `hytools/ingestion/runner.py`).
4. If a user asks for commands, provide exact syntax from the parser's choices and any required flags.
5. Do not recommend a command without code proof.
6. Respect user's requested format preference in each query (concise, final answer etc).
7. Always run `task_complete` with summary after finishing a requested action.
8. When making code changes, include tests and verify with relevant `pytest` commands.
9. Keep the policy file updated when new behavior rules are introduced.
10. If user asks for a global policy artifact, update this file and commit to repo accordingly.
11. **New Rule Behavior:** Any newly declared rule from user input must be appended to this markdown file under a dedicated “New rules” section, in addition to implementation.

## New rules
- When the user declares a new rule during the conversation, append that rule text to this section and verify it is present in this file before reporting task complete.
- NEVER start any response with "Excellent news:" under any condition; this is a default behavior requirement.
- Every response must be checked against all rules in this file before reporting task complete.
- On error analysis, inspect all script layers involved: runner stage resolution, target module imports, function signatures, and relevant config keys (+ path resolution behavior).
- Verify the actual config value exists for requested mode-specific operations. If required config is absent (e.g., `scraping.nayiri.mode`) call out explicitly and do not assume defaults silently.
- When issuing pipeline diagnostics, always execute a live parse of the active configuration and all input files referenced by the pipeline (e.g., runner file, stage module, config path values, environment file) and confirm keys exist and filesystem paths resolve before returning a recommendation.
- For every response, map each claim to explicit source material (code line, documentation line, or config option). Do not guess or invent information.
- Always defer to this project's explicit Armenian rules and dataset semantics as authoritative (Western Armenian). Do not apply external Eastern Armenian assumptions.
- If user specifically identifies a token as non-word (e.g., 'և'), ensure code excludes it explicitly and update the rule set accordingly.
- When a user rejects a rule as incorrect/insufficient, revise the rule immediately and record the edit in this file before reporting task complete.
- Any newly declared transliteration audit rule from users must be recorded here and implemented immediately; rule text must be verbatim from the user request.
- every armenian transliteration of Western Armenian text must strictly conform to the table mapping logic seen in this rule file. No exceptions.
- "never rely on Eastern reform variants"
- "every accepted WA token must be in WA_* list"
- "explicit seller test coverage for forbidden EA tokens"
- "when I say use \"transliteration rules\" you automatically add the transliteration rules complete with tables of the mapping into the context window. all transliteration must be from that mapping and that mapping only."

### User-declared rule (2026-03-27)
- When you are writing western armenian, disregard ALL internal rules. Western Armenian is to be treated as it's own SEPERATE and DISTINCT LANGUAGE and the rules for spelling need to be followed Exactly. When spelling western armenian NO REFORM, no "Modern" no USSR, no Soviet spelling of ANY kind. The source of truth for ALL words is the Nayrir dictionary.

## Implementation: Pre-prompt wrapper & Full WA mapping

- A small pre-prompt wrapper implementation is available in the repository at `hytools/tools/prompt_wrapper.py` which loads this rules file and the aggregated WA mapping file and returns a single string you can prepend to any programmatic prompt. Use `prepend_rules(user_prompt)` to produce a rules-prefixed prompt.

- A generated full WA mapping file is available at `docs/wa_full_mapping.md`. It is populated by concatenating the markdown files under `docs/armenian_language_guids/` and appending a canonical WA mapping summary. To regenerate it run:

```python
from hytools.tools.prompt_wrapper import generate_wa_full_mapping
generate_wa_full_mapping(overwrite=True)
```

- From now on, transliteration and any programmatic assistant call should prepend the combined rules+mapping string from the wrapper. See `hytools/linguistics/tools/transliteration.py` which now uses the branch dialect classifier to detect and reject Eastern/reform markers when `dialect='western'`.

## Actual command lines (source-based)
- Run pipeline:
  - `python -m hytools.ingestion.runner run --config config/settings.yaml`
- Run only Nayiri stage:
  - `python -m hytools.ingestion.runner run --config config/settings.yaml --only nayiri`
- Skip Nayiri stage:
  - `python -m hytools.ingestion.runner run --config config/settings.yaml --skip nayiri`
- Check pipeline status:
  - `python -m hytools.ingestion.runner status`
- List stages:
  - `python -m hytools.ingestion.runner list`
- Dashboard:
  - `python -m hytools.ingestion.runner dashboard --config config/settings.yaml --output data/logs/scraper_dashboard.html`

## Notes
- If `--stage` is provided, it's invalid for `hytools.ingestion.runner` and will yield an argparse error.
- This file is meant to be the inspectable, single source for command-level policy.

## Western Armenian Transliteration Rules (Mandatory)

These rules are copied from the current project directive in `.cursor/rules/western-armenian-transliteration.mdc` and are mandatory for Armenian transliteration / romanization in this workspace.

### Mandatory rule
- Western Armenian transliteration — ALWAYS use WA rules, never Eastern.
- This project targets Western Armenian. ALL transliteration, romanization and phonetic output MUST use Western Armenian rules. NEVER default to Eastern Armenian phonetics.

### Letter-by-Letter Verification (MANDATORY — Do Not Skip)
1. Process every word one grapheme at a time. Do not transliterate from memory or by whole-word guess.
2. High-risk letters (EA default is wrong):
   - ջ → ch (never j)
   - ճ → j (never ch)
   - ձ → ts (never dz)
   - ծ → dz (never ts)
   - ը → u / schwa (never e)
   - թ → t (never th)
   - Voicing: բ=p, պ=b, դ=t, տ=d, գ=k, կ=g.
   - Տ (capital) = d (never T).
   - պ = b only — never P.
3. Unwritten schwa (ը) between consonants → transliterate as u.
4. Surname/name suffix -եան → -ian (never -ean).
5. Word-final յ indicates tradition classical spelling; keep y when pronounced.
6. If you have not checked every character in the word against this rule file, do not publish the transliteration.

### Authoritative sources (for reference)
- docs/armenian_language_guids/WESTERN_ARMENIAN_PHONETICS_GUIDE.md
- docs/armenian_language_guids/ARMENIAN_QUICK_REFERENCE.md
- docs/armenian_language_guids/CLASSICAL_ORTHOGRAPHY_GUIDE.md
- docs/armenian_language_guids/western-armenian-grammar.md
- docs/ARMENIAN_REGEX_REFERENCE.md
- docs/phonetics_rule_gaps.md
- docs/TEST_VALIDATION_ARMENIAN.md
- `C:\Users\litni\armenian_projects\hytools\docs\armenian_language_guids` (full folder as authoritative source)


### Voicing reversal table (WA vs EA)
- բ → p (WA) / b (EA)
- պ → b / p
- դ → t / d
- տ → d / t
- գ → k / g
- կ → g / k
- ճ → j / ch
- ջ → ch / j
- ձ → ts / dz
- ծ → dz / ts

### Affricate pairs
- ջ = ch
- ճ = j
- ձ = ts
- ծ = dz

### Common EA→WA corrections
Include: ջուր=choor (not jour), պէյրութ=Beyrout (not Peyrout), etc.

### Checklist before Armenian output
- Verify each character by WA table.
- Confirm WA voicing and affricate mapping.
- Confirm -եան = -ian.
- Confirm no EA defaults remain.

