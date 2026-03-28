from pathlib import Path
import re

helpers_path = Path('hytools/ingestion/_shared/helpers.py')
branch_path = Path('hytools/linguistics/dialect/branch_dialect_classifier.py')
helper_text = helpers_path.read_text(encoding='utf-8')
branch_text = branch_path.read_text(encoding='utf-8')

start = helper_text.index('_CONSOLIDATED_RULES: list[dict] = [')
end = helper_text.index('\ndef get_consolidated_rules()', start)
rules_block = helper_text[start:end].strip()

sub_start = helper_text.index('def get_consolidated_rules()', end)
sub_end = helper_text.index('\n# Run consistency check at module import', sub_start)
helper_funcs_block = helper_text[sub_start:sub_end].strip()

branch_text = branch_text.replace('from hytools.ingestion._shared.helpers import get_consolidated_rules\n\n', '')

build_pattern = r"def _build_dialect_rules\(\) -> List\[DialectRule\]:.*?return rules\n\n"
branch_text = re.sub(build_pattern,
"""def _build_dialect_rules() -> List[DialectRule]:\n    rules = []\n    for r in _CONSOLIDATED_RULES:\n        rules.append(\n            DialectRule(\n                rule_id=r.get(\"rule_id\", \"\"),\n                dialect=r.get(\"branch\", \"unknown\"),\n                weight=float(r.get(\"weight\", 0.0)),\n                pattern=r.get(\"pattern\", \"\"),\n                source=r.get(\"source\", \"\"),\n                note=r.get(\"note\", \"\"),\n            )\n        )\n    return rules\n\n""", branch_text, flags=re.S)

insert_point = branch_text.index('def _build_dialect_rules')
prefix = branch_text[:insert_point]
suffix = branch_text[insert_point:]

insert_text = '\n\n# Source-of-truth rule table now in branch_dialect_classifier.py\n' + rules_block + '\n\n' + helper_funcs_block + '\n\n_CONSOLIDATED_COMPILED = [\n    (r, re.compile(r[\"pattern\"], flags=re.IGNORECASE)) for r in _CONSOLIDATED_RULES\n]\n\n# Run consistency check at module import\n_verify_consolidated_rules_consistency()\n\n'

branch_text = prefix + insert_text + suffix
branch_path.write_text(branch_text, encoding='utf-8')
print('branch_dialect_classifier updated')
