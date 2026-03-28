from pathlib import Path

lf_path = Path('hytools/cleaning/language_filter.py')
text = lf_path.read_text(encoding='utf-8')

# Remove block in language_filter that defines locale markers locally; we will use helpers imports instead.
start = text.find('# == 1. Classical-orthography markers')
if start != -1:
    end = text.find('# == 2c. East Armenian post-1922 reform markers', start)
    if end != -1:
        text = text[:start] + '# Marker definitions are provided by hytools.ingestion._shared.helpers\n' + text[end:]

# Remove the 4) authors block and 5) publication cities block, since helpers has them.
start = text.find('# == 4. Known WA publication cities')
if start != -1:
    end = text.find('# == Regex for word-internal long-e', start)
    if end != -1:
        text = text[:start] + '# WA publication cities from helpers (hytools.ingestion._shared.helpers).\n' + text[end:]

# No need for suffix regex here; these are imported from helpers now.
text = text.replace('_REFORMED_SUFFIX_RE = re.compile(r"\\u0578\\u0582\\u0569\\u0575\\u0578\\u0582\\u0576")\n', '')
text = text.replace('_CLASSICAL_SUFFIX_RE = re.compile(r"\\u0578\\u0582\\u0569\\u056B\\u0582\\u0576")\n', '')

lf_path.write_text(text, encoding='utf-8')
print('language_filter.py has been migrated to import helper constants')