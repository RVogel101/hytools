import os, re
patterns = [
    (re.compile(r'from\s+cleaning(?=[\s\.])'), 'from hytools.cleaning'),
    (re.compile(r'import\s+cleaning(?=[\s\,]|$)'), 'import hytools.cleaning'),
    (re.compile(r'from\s+ingestion(?=[\s\.])'), 'from hytools.ingestion'),
    (re.compile(r'import\s+ingestion(?=[\s\,]|$)'), 'import hytools.ingestion'),
    (re.compile(r'from\s+augmentation(?=[\s\.])'), 'from hytools.augmentation'),
    (re.compile(r'import\s+augmentation(?=[\s\,]|$)'), 'import hytools.augmentation'),
    (re.compile(r'from\s+integrations(?=[\s\.])'), 'from hytools.integrations'),
    (re.compile(r'import\s+integrations(?=[\s\,]|$)'), 'import hytools.integrations'),
    (re.compile(r'from\s+linguistics(?=[\s\.])'), 'from hytools.linguistics'),
    (re.compile(r'import\s+linguistics(?=[\s\,]|$)'), 'import hytools.linguistics'),
    (re.compile(r'from\s+ocr(?=[\s\.])'), 'from hytools.ocr'),
    (re.compile(r'import\s+ocr(?=[\s\,]|$)'), 'import hytools.ocr'),
    (re.compile(r'from\s+core_contracts(?=[\s\.])'), 'from hytools.core_contracts'),
    (re.compile(r'import\s+core_contracts(?=[\s\,]|$)'), 'import hytools.core_contracts'),
]

for dirpath, dirnames, filenames in os.walk('.'):
    if any(x in dirpath for x in ['.git', 'venv', '__pycache__', 'hytools/__pycache__']):
        continue
    for fn in filenames:
        if fn.endswith('.py'):
            fp = os.path.join(dirpath, fn)
            with open(fp, 'r', encoding='utf-8') as f:
                txt = f.read()
            new = txt
            for pat, rep in patterns:
                new = pat.sub(rep, new)
            if new != txt:
                with open(fp, 'w', encoding='utf-8') as f:
                    f.write(new)
print('rewritten imports')
