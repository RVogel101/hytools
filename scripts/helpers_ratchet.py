from pathlib import Path

helpers_path = Path('hytools/ingestion/_shared/helpers.py')
text = helpers_path.read_text(encoding='utf-8')
start = text.index('_CONSOLIDATED_RULES: list[dict] = [')
end = text.index('\n# ═════════════════════════════════════════════════════════════════════════════', start)

replacement = '''# Consolidated WA/EA/classical rule set is now sourced from branch_dialect_classifier.py
from hytools.linguistics.dialect.branch_dialect_classifier import (
    _CONSOLIDATED_RULES,
    get_consolidated_rules,
    get_eastern_markers,
    get_lexical_markers,
    get_classical_markers,
    get_wa_vocabulary_markers,
    get_wa_standalone_patterns,
    get_wa_suffix_patterns,
    get_ea_regex_patterns,
    get_word_internal_e_long_re,
    get_word_ending_ay_re,
    get_word_ending_oy_re,
    get_wa_authors,
    get_wa_publication_cities,
    get_armenian_punctuation,
    get_wa_score_threshold,
    _rule_includes_marker,
    _verify_consolidated_rules_consistency,
    _CONSOLIDATED_COMPILED,
    _classify_scores,
    classify_text_classification,
    classify_batch_texts,
    classify_vocab_and_sentences,
)

# Verify that compatibility wrappers are imported correctly.
'''

text = text[:start] + replacement + text[end:]
helpers_path.write_text(text, encoding='utf-8')
print('helpers.py updated to wrapper mode')
