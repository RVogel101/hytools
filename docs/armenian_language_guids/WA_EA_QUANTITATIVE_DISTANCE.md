# WA vs EA Quantitative Distance — Methodology

This document records the methodology for computing Western Armenian (WA) vs Eastern Armenian (EA) distance across three axes: phonetic, lexical, and orthographic.

Summary of pipeline:

- Phonetic: IPA transcription → edit distance + difficulty scores
- Lexical: marker counts + shared-token ratios
- Orthographic: rule-based marker counts + classical/reformed ratios
- Composite index: weighted sum (default: phonetic 40%, lexical 40%, orthographic 20%)

Data files and code:

- analysis/wa_ea_corpus_manifest.json — corpus manifest (scaffold)
- analysis/wa_ea_orthography_rules.yaml — rule scaffold
- scripts/wa_ea_distance.py — runnable script to produce CSV outputs

Reproducibility: run the script with a WA and EA sample file:

```bash
python scripts/wa_ea_distance.py --wa data/textbook_modern_wa_extract.txt --ea data/ea_sample.txt --outdir analysis
```

Notes: This is a reproducible scaffold. The rule YAML needs expansion from canonical docs before large-scale runs.
