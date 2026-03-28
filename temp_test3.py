import types, sys, importlib.util, os
# create package placeholders
sys.modules['hytools'] = types.ModuleType('hytools')
sys.modules['hytools.linguistics'] = types.ModuleType('hytools.linguistics')
sys.modules['hytools.linguistics.dialect'] = types.ModuleType('hytools.linguistics.dialect')

p = os.path.join(os.getcwd(),'hytools','linguistics','dialect','branch_dialect_classifier.py')
spec = importlib.util.spec_from_file_location('hytools.linguistics.dialect.branch_dialect_classifier', p)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
b = mod

text = '\u0547\u0561\u0570 \u056c\u0561\u057e \u0574\u0565\u057a \u0574\u0561\u0572\u0564\u056b\u0578\u057e \u057a\u0561\u057f\u0561\u0574\u0565\u0574'
print('compiled rules:', len(b._COMPILED_RULES))
print('sample patterns for shad lav medz present?')
for rule, pat in b._COMPILED_RULES[:50]:
    if rule.rule_id in ('WA_VOCAB_SHAD','WA_VOCAB_LAV','WA_VOCAB_MEDZ'):
        print(rule.rule_id, 'pattern=', rule.pattern, 'weight=', rule.weight)
print('score=', b.compute_wa_score(text))
