TrOCR (optional GPU fallback) installation and notes

- The TrOCR fallback uses the Hugging Face `transformers` pipeline for `image-to-text`.
- Install the optional dependencies when you want to use TrOCR on GPU:

  pip install "torch" "transformers" "diffusers" "accelerate"

- For CUDA / GPU, prefer a torch wheel matching your CUDA version. Example (CUDA 11.8):

  pip install --index-url https://download.pytorch.org/whl/cu118 torch torchvision torchaudio --extra-index-url https://pypi.org/simple

- Example usage in the OCR script (GPU device 0):

  python scripts/reprocess_textbook_ocr.py --pdf data/textbook-of-modern-western-armenian.pdf \
    --output data/ocr_run_trocr --reprocess-missing 200 --thresholds 100,200,400 \
    --use-trocr-fallback --trocr-device 0 --save-variants

- Notes:
  - The recommended TrOCR model for printed text is `microsoft/trocr-base-printed` (default used by the script).
  - For handwritten or mixed scripts, try `microsoft/trocr-base-handwritten`.
  - TrOCR may be slower and require significant GPU memory for large batches; the script runs it only on pages that remain low-quality after Tesseract attempts.
