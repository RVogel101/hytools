from pathlib import Path
from collections import Counter
import re
p = Path(r'c:\Users\litni\armenian_projects\hytools\data\textbook_modern_wa_pages')
files = sorted(p.glob('page_*.txt'))
print('file count', len(files))
char_counts = Counter()
word_counts = Counter()
arm_cnt = 0
for f in files:
    txt = f.read_text(encoding='utf-8', errors='ignore')
    arm = re.findall(r'[\u0531-\u058F]+', txt)
    if arm:
        arm_cnt += 1
    for token in arm:
        word_counts[token] += 1
    for ch in txt:
        if '\u0531' <= ch <= '\u058F':
            char_counts[ch] += 1
print('files containing Armenian text', arm_cnt)
print('top char', char_counts.most_common(20))
print('top word', word_counts.most_common(80))
