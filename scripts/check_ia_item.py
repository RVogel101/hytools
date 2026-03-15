"""Quick check of an Internet Archive item's file listing."""
import requests

IDENT = "HYEAMB_DBS_HS"
url = f"https://archive.org/metadata/{IDENT}/files"
resp = requests.get(url, timeout=30, headers={"User-Agent": "ArmenianCorpusCore/1.0"})
files = resp.json().get("result", [])

total = 0
for f in files:
    name = f.get("name", "?")
    fmt = f.get("format", "?")
    size = int(f.get("size", 0))
    total += size
    print(f"{name:70s} {fmt:25s} {size:>15,d}")
print(f"\nTotal files: {len(files)}, Total size: {total:,d} bytes ({total/1e9:.2f} GB)")

# Check which are text files the scraper would download
text_files = [f for f in files if f.get("name", "").lower().endswith(("_djvu.txt", ".txt")) and not f.get("name", "").endswith("_files.xml")]
print(f"\nText files the scraper would consider ({len(text_files)}):")
for f in text_files:
    print(f"  {f.get('name', '?'):60s} {int(f.get('size', 0)):>12,d} bytes")
