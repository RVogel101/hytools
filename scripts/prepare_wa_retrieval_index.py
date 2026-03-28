#!/usr/bin/env python
"""Prepare retrieval index for RAG/RAP pipeline.

1. Ingest and clean WA corpus text from `data/staging_text/` + `data/filtered/`.
2. Split into chunks with metadata.
3. Build FAISS index and save index+mapping.

Outputs:
  - data/retrieval/wa_chunks.jsonl
  - data/retrieval/wa_chunks_index.faiss
  - data/retrieval/wa_chunks_meta.json
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Dict

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RETRIEVAL_DIR = DATA_DIR / "retrieval"
RETRIEVAL_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE = 250
CHUNK_STRIDE = 50
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_sources() -> List[Dict[str, str]]:
    sources = []
    for subdir in ["staging_text", "filtered"]:
        dir_path = DATA_DIR / subdir
        if not dir_path.exists():
            continue
        for path in sorted(dir_path.glob("**/*.txt")):
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
            if not text:
                continue
            sources.append({"source": subdir, "path": str(path), "text": text})
    return sources


def chunk_text(text: str, doc_id: str) -> List[Dict[str, str]]:
    words = text.split()
    chunks = []
    for start in range(0, max(1, len(words)), CHUNK_STRIDE):
        end = min(len(words), start + CHUNK_SIZE)
        chunk = " ".join(words[start:end])
        if not chunk.strip():
            continue
        chunks.append({"doc_id": doc_id, "start": start, "end": end, "text": chunk})
        if end == len(words):
            break
    return chunks


def main():
    sources = load_sources()
    print(f"Loaded {len(sources)} source files")

    all_chunks = []
    idx = 0
    for src in sources:
        doc_id = f"{src['source']}:{Path(src['path']).stem}"
        for c in chunk_text(src["text"], doc_id):
            c["chunk_id"] = f"{doc_id}:{idx}"
            all_chunks.append(c)
            idx += 1

    print(f"Total chunks: {len(all_chunks)}")

    if len(all_chunks) == 0:
        raise RuntimeError("No chunks to index. Check source files in data/staging_text and data/filtered.")

    # Save chunks JSONL
    chunks_path = RETRIEVAL_DIR / "wa_chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    # Build embeddings and FAISS index
    model = SentenceTransformer(MODEL_NAME)
    texts = [c["text"] for c in all_chunks]
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=True)

    if embeddings.size == 0 or len(embeddings.shape) != 2:
        raise RuntimeError("Embeddings have invalid shape, likely no text chunks were found.")

    d = embeddings.shape[1]
    faiss.normalize_L2(embeddings)

    use_gpu = False
    index = faiss.IndexFlatIP(d)
    try:
        if faiss.get_num_gpus() > 0:
            print("GPU detected for FAISS. Creating GPU index.")
            res = faiss.StandardGpuResources()
            gpu_index = faiss.index_cpu_to_gpu(res, 0, index)
            gpu_index.add(embeddings)
            index = gpu_index
            use_gpu = True
        else:
            raise RuntimeError("No GPUs available for FAISS")
    except Exception as e:
        print(f"Falling back to CPU FAISS index: {e}")
        index = faiss.IndexFlatIP(d)
        index.add(embeddings)

    faiss.write_index(index, str(RETRIEVAL_DIR / "wa_chunks_index.faiss"))

    meta_path = RETRIEVAL_DIR / "wa_chunks_meta.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump({"chunks_path": str(chunks_path), "index_path": str(RETRIEVAL_DIR / "wa_chunks_index.faiss"), "vector_dim": d}, f, ensure_ascii=False)

    print("Retrieval index creation complete.")


if __name__ == "__main__":
    main()
