import importlib.machinery, importlib.util, sys
path = r'C:\Users\litni\armenian_projects\hytools\hytools\linguistics\dialect\branch_dialect_classifier.py'
loader = importlib.machinery.SourceFileLoader('temp_bdc', path)
spec = importlib.util.spec_from_loader(loader.name, loader)
mod = importlib.util.module_from_spec(spec)
# ensure module is in sys.modules to satisfy dataclasses checks
sys.modules[loader.name] = mod
loader.exec_module(mod)
text = '\u0547\u0561\u0570 \u056c\u0561\u057e \u0574\u0565\u057a \u0574\u0561\u0572\u0564\u056b\u0578\u057e \u057a\u0561\u057f\u0561\u0574\u0565\u0574'
lines = []
lines.append('text repr: '+repr(text))
lines.append('text len: '+str(len(text)))
lines.append('codepoints:')
for i,ch in enumerate(text):
    lines.append(f"{i} {ch} {hex(ord(ch))}")
# find substrings
for w in ['շատ','լաւ','մեծ']:
    idx = text.find(w)
    lines.append(f'find {w} -> {idx}')
    if idx>=0:
        lines.append('substr codepoints: '+str([hex(ord(c)) for c in text[idx:idx+len(w)]]))
    else:
        lines.append('not found (maybe normalization differences)')
# also print regex search spans
import re
for r in mod._CONSOLIDATED_RULES:
    if r.get('rule_id')=='WA_VOCAB_SHAD':
        p = re.compile(r.get('pattern'))
        m = p.search(text)
        lines.append('regex m: '+str(m))
        if m:
            lines.append('span '+str(m.span())+' '+repr(m.group(0)))

sys.stdout.buffer.write('\n'.join(lines).encode('utf-8'))
