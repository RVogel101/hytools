"""Report per-page character and word counts for OCR output (page_*.txt).

Use after running OCR to find pages with very low yield (e.g. tables where
only numbers were recognized, or missed text). See docs/development/ARMENIAN_OCR_GPU_AND_QUALITY.md §4.

Usage::

    python -m ocr.page_stats data/textbook_modern_wa_pages
    python -m ocr.page_stats data/ocr_output/gomidas --min-chars 100
    python -m ocr.page_stats data/textbook_modern_wa_pages --csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report per-page OCR yield (chars/words) and flag low-yield pages.",
    )
    parser.add_argument(
        "dir",
        type=Path,
        help="Directory containing page_*.txt files (e.g. data/textbook_modern_wa_pages)",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=100,
        help="Flag pages with fewer than this many characters (default: 100)",
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=0,
        help="Flag pages with fewer than this many words (default: 0, disabled)",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Print CSV header + one row per page (page,chars,words)",
    )
    args = parser.parse_args()

    if not args.dir.is_dir():
        print(f"Not a directory: {args.dir}", file=sys.stderr)
        sys.exit(1)

    files = sorted(args.dir.glob("page_*.txt"))
    if not files:
        print(f"No page_*.txt files in {args.dir}", file=sys.stderr)
        sys.exit(1)

    rows: list[tuple[str, int, int]] = []
    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        chars = len(text)
        words = len(text.split())
        rows.append((p.stem, chars, words))

    low_char = [r for r in rows if r[1] < args.min_chars]
    low_word = [r for r in rows if args.min_words and r[2] < args.min_words]

    if args.csv:
        print("page,chars,words")
        for stem, c, w in rows:
            print(f"{stem},{c},{w}")
        return

    print(f"Directory: {args.dir}")
    print(f"Pages: {len(rows)}")
    print(f"Total chars: {sum(r[1] for r in rows)}, total words: {sum(r[2] for r in rows)}")
    print()

    if low_char:
        print(f"Pages with < {args.min_chars} chars ({len(low_char)}):")
        for stem, c, w in low_char:
            print(f"  {stem}  chars={c}  words={w}")
    if low_word and args.min_words:
        print(f"Pages with < {args.min_words} words ({len(low_word)}):")
        for stem, c, w in low_word:
            if (stem, c, w) not in [(r[0], r[1], r[2]) for r in low_char]:
                print(f"  {stem}  chars={c}  words={w}")

    if not low_char and not (low_word and args.min_words):
        print("No pages below threshold.")


if __name__ == "__main__":
    main()
