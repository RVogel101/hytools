#!/usr/bin/env python
"""Simple RAG path for Western Armenian retrieval + generation proof of concept."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# Placeholder for generation (print retrieved context only)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RETRIEVAL_DIR = PROJECT_ROOT / "data" / "retrieval"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 5


def load_index():
    meta_path = RETRIEVAL_DIR / "wa_chunks_meta.json"
    if not meta_path.exists():
        raise FileNotFoundError("Retrieval metadata missing. Run prepare_wa_retrieval_index.py first.")
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    index = faiss.read_index(meta['index_path'])
    chunks = []
    with open(meta['chunks_path'], 'r', encoding='utf-8') as f:
        for line in f:
            chunks.append(json.loads(line))
    return index, chunks


def retrieve(query: str, index, chunks):
    model = SentenceTransformer(MODEL_NAME)
    q_emb = model.encode([query], convert_to_numpy=True)
    faiss.normalize_L2(q_emb)
    D, I = index.search(q_emb, TOP_K)
    results = []
    for dist, idx in zip(D[0], I[0]):
        if idx < 0 or idx >= len(chunks):
            continue
        entry = chunks[idx].copy()
        entry['score'] = float(dist)
        results.append(entry)
    return results


def run_query(query: str):
    index, chunks = load_index()
    hits = retrieve(query, index, chunks)
    print(f"Query: {query}")
    print("Top hits:")
    for h in hits:
        print(f"  [{h['score']:.4f}] {h['doc_id']} ({h['start']}-{h['end']}) -> {h['text'][:140].replace('\n', ' ')}")


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print('Usage: python scripts/query_wa_rag.py "Your question in Armenian"')
        sys.exit(1)

    q = sys.argv[1]
    run_query(q)
