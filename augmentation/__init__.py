"""Western Armenian data augmentation pipeline.

Generates additional WA training data using a local LLM (Llama 3.1 8B
via Ollama) and non-LLM text transforms, with full retry logic,
checkpointing, and background-process support.

Usage
-----
Estimate time::

    python -m src.augmentation.runner estimate

Run augmentation (foreground)::

    python -m src.augmentation.runner run

Run augmentation (background)::

    python -m src.augmentation.runner run --background

Check progress::

    python -m src.augmentation.runner status
"""
