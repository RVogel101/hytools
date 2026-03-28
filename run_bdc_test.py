import importlib.machinery, importlib.util, sys
path = r'C:\Users\litni\armenian_projects\hytools\hytools\linguistics\dialect\branch_dialect_classifier.py'
loader = importlib.machinery.SourceFileLoader('bdc', path)
spec = importlib.util.spec_from_loader(loader.name, loader)
mod = importlib.util.module_from_spec(spec)
sys.modules[loader.name]=mod
loader.exec_module(mod)
text = '\u0547\u0561\u0570 \u056c\u0561\u057e \u0574\u0565\u057a \u0574\u0561\u0572\u0564\u056b\u0578\u057e \u057a\u0561\u057f\u0561\u0574\u0565\u0574'
res = mod.classify_text_classification(text)
print(res)
