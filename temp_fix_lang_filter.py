from pathlib import Path
path = Path('hytools/cleaning/language_filter.py')
text = path.read_text(encoding='utf-8')
text = text.replace('is_wa = wa_score >= WA_SCORE_THRESHOLD', 'is_wa = wa_score >= get_wa_score_threshold()')
old = """# Reformed suffix regex (Soviet-era spelling of classical -outhiwn).\n_REFORMED_SUFFIX_RE = re.compile(r"\\u0578\\u0582\\u0569\\u0575\\u0578\\u0582\\u0576")\n# Classical suffix regex (WA spelling -outhiwn).\n_CLASSICAL_SUFFIX_RE = re.compile(r"\\u0578\\u0582\\u0569\\u056B\\u0582\\u0576")\n"""
text = text.replace(old, '')
path.write_text(text, encoding='utf-8')
print('updated')
