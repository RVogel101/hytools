import json, re
from pathlib import Path
from hytools.ingestion._shared import helpers as h

path = Path('tests/data/textbook_modern_wa_vocab_and_sentences.json')
if not path.exists():
    raise SystemExit('data file missing')
with path.open('r', encoding='utf-8') as f:
    data = json.load(f)
west = data.get('sentences_western', [])
eas = data.get('sentences_eastern', [])
new_rule_ids = {
    'WA_NEG_CONJUNCTION_AYL',
    'WA_PRESENT_ONSET_GU',
    'WA_CASE_DATIVE_WITHIN',
    'WA_VERB_PARTICIPLE_ALU',
    'WA_VOCAB_SHAD',
}
original_rules = list(h._CONSOLIDATED_RULES)

def label_stats(sentences, deweight_new=False):
    if deweight_new:
        altered = []
        for r in original_rules:
            r2 = r.copy()
            if r2['rule_id'] in new_rule_ids:
                r2['weight'] = 0.0
            altered.append(r2)
        h._CONSOLIDATED_RULES = altered
        h._CONSOLIDATED_COMPILED = [(r, re.compile(r['pattern'], flags=re.IGNORECASE)) for r in h._CONSOLIDATED_RULES]

    counts = {'likely_western':0, 'likely_eastern':0, 'likely_classical':0, 'inconclusive':0}
    for t in sentences:
        res = h.classify_text_classification(t)
        counts[res['label']] += 1

    if deweight_new:
        h._CONSOLIDATED_RULES = original_rules
        h._CONSOLIDATED_COMPILED = [(r, re.compile(r['pattern'], flags=re.IGNORECASE)) for r in h._CONSOLIDATED_RULES]

    return counts

west_before = label_stats(west, deweight_new=True)
west_after = label_stats(west, deweight_new=False)
eas_before = label_stats(eas, deweight_new=True)
eas_after = label_stats(eas, deweight_new=False)

print('WESTERN (baseline before -> after)')
print(west_before, '=>', west_after)
print('EASTERN (baseline before -> after)')
print(eas_before, '=>', eas_after)

# Nathan known false pos/neg
west_miss = [(t,h.classify_text_classification(t)['label']) for t in west if h.classify_text_classification(t)['label'] != 'likely_western']
eas_fp = [(t,h.classify_text_classification(t)['label']) for t in eas if h.classify_text_classification(t)['label'] == 'likely_western']

print('\nwestern false negatives:', len(west_miss))
print('eastern false positives:', len(eas_fp))
print('eastern false positive samples:', eas_fp[:5])
