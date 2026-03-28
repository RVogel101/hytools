Importing external benchmark datasets

Place external benchmark CSVs (ASJP exports, language-pair tables) somewhere accessible and run:

```bash
python scripts/import_benchmarks.py --csv path/to/external_benchmarks.csv
```

The script normalizes distances to [0,1] (min-max) and appends them to `analysis/wa_ea_benchmark_comparison.csv`.

Expected CSV minimal columns: `pair`, `distance` (or `d`). If different, rename columns or pre-process.

Sources to consider:
- ASJP databases (download separately)
- Published language-distance tables (preprocess to CSV)
