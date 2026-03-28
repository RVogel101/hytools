"""Generate all candidate Bagin archive PDF URLs used by `tert_nla`.

Writes `scripts/tert_nla_tried_urls.txt` with one URL per line and prints
count + sample to stdout.
"""
from pathlib import Path

base_template = "https://tert.nla.am/archive/NLA%20AMSAGIR/Bagin/{year}/{fname}"
start_year = 1962
end_year = 2024
max_issue = 12
candidates = []
for year in range(start_year, end_year + 1):
    for i in range(1, max_issue + 1):
        candidates.append(base_template.format(year=year, fname=f"{i}_ocr.pdf"))
        candidates.append(base_template.format(year=year, fname=f"{i}.pdf"))
    for i in range(1, max_issue):
        candidates.append(base_template.format(year=year, fname=f"{i}-{i+1}_ocr.pdf"))
        candidates.append(base_template.format(year=year, fname=f"{i}-{i+1}.pdf"))
        candidates.append(base_template.format(year=year, fname=f"{i}_{i+1}_ocr.pdf"))

out = Path('scripts/tert_nla_tried_urls.txt')
out.parent.mkdir(parents=True, exist_ok=True)
with out.open('w', encoding='utf-8') as f:
    for url in candidates:
        f.write(url + '\n')

print(f'Wrote {len(candidates)} candidate URLs to {out.resolve()}')
print('\nFirst 20:')
for u in candidates[:20]:
    print(u)
print('\n(Full list saved to the file above; run `type scripts\\tert_nla_tried_urls.txt` on Windows or `cat scripts/tert_nla_tried_urls.txt` on Unix to view everything.)')
