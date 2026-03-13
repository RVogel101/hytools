# AGENTS.md

Memory for agent behavior across sessions. Plain bullet points only.

## Learned User Preferences

- When fixing linter/type errors: use explicit None guards and type narrowing (e.g. `x or {}`, `x or []`, `if x is None: raise ...`) so return types and attribute access are type-safe; add `# type: ignore[reportMissingModuleSource]` for optional dependencies (yaml, datasketch, pymongo, bson) when the checker cannot resolve them.
- After applying a fix: verify (linter clean, tests pass) and give a concise summary: Change / Why / Verification.
- Prefer shared helpers for path or config resolution (e.g. resolve_filtered_corpus_dir) instead of duplicating logic in multiple call sites.
- Prefer config-driven paths (e.g. paths.filtered_dir, paths.cleaned_dir) over hardcoded directory strings.
- Add progress logs to long-running pipeline steps (e.g. normalize: log every N files) so the user can see advancement.
- When implementing recommendations from a doc: update the doc to mark items as done (e.g. TRAINING_FLOW_ANALYSIS.md).
- When refactoring structure: flatten nested packages (e.g. ocr/ocr → ocr), move modules to logical homes (e.g. data_sources → extraction), group integrations (e.g. anki + database under integrations); then update imports, tests, and docs (e.g. STRUCTURE.md, INDEX.md).
- For workspace problem count: exclude non-source paths from Pylance (envs, node_modules, venv, archive, cache, __pycache__, build) and set reportMissingImports/reportMissingModuleSource to warning for optional deps; suggest reloading the window after changing workspace settings.
- When producing docs for a data engineer: single consolidated markdown with overview, auth/rate limits, URL structure, datasets, geography, variables, example URLs, and a pipeline-integration checklist.
- After updating or implementing anything in `armenian-corpus-core`, update `docs/development/FUTURE_IMPROVEMENTS.md` (not `docs/FUTURE_IMPROVEMENTS.md`) to reflect the current status (mark items as implemented when done and adjust summary tables/notes).
- **Armenian transliteration:** Before writing any Armenian letter to English/roman transliteration, always verify against the Western Armenian standard: check the mapping in `.cursor/rules/western-armenian-transliteration.mdc` and in `docs/armenian_language_guids/` (e.g. WESTERN_ARMENIAN_PHONETICS_GUIDE.md, ARMENIAN_QUICK_REFERENCE.md) and `docs/development/ARMENIAN_TRANSLITERATION_SYSTEMS.md`. Use WA voicing (բ=p, պ=b, ջ=ch, ճ=j, ձ=ts, ծ=dz, etc.) and context rules (յ→h/y, ո→vo/o, ե→ye/e); never default to Eastern Armenian mappings.

## Learned Workspace Facts

- Workspace includes multiple roots: armenian-corpus-core, WesternArmenianLLM, lousardzag.
- armenian-corpus-core: package `armenian_corpus_core` with core_contracts, extraction (data_sources, registry, mappers), scraping, cleaning, linguistics (metrics, morphology, phonetics, stemmer), augmentation, ocr, research, integrations (anki, database); use docs/STRUCTURE.md and docs/INDEX.md for layout and nav.
- WesternArmenianLLM: training pipeline is prepare_training_data → pretrain → instruct_finetune; config uses paths.filtered_dir and paths.cleaned_dir; cleaning runner writes PID to data/logs/.clean_runner.pid; conda env wa-llm.
- Training data flow: MongoDB → cleaning (normalize, dedup, WA filter, promote) → data/filtered and data/archive/cleaned → create_splits → data/archive/splits; create_splits prefers data/filtered then paths.cleaned_dir; Stage 1 (pretrain) loads base model; Stage 2 (instruct) can start from base via training.instruct_start_from_base.
- This project targets Western Armenian: use WA transliteration and phonetics; consult docs/armenian_language_guids and .cursor/rules for Western Armenian.
