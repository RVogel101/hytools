"""Classical Armenian orthography OCR pass for stubborn pages.

Some scanned Armenian texts — especially 19th-century and early-20th-century
publications — use classical (grabar / reformed-classical) orthography that
the modern ``hye`` Tesseract model handles poorly.  An extra OCR pass with
a classical-orthography traineddata file (``hye_old``, ``hye_clas``, or
any user-specified model name) can recover text that the standard pass
misses.

Usage in the pipeline
---------------------
After the primary Tesseract / Surya / zone-OCR comparison, if the best
score is still below ``classical_threshold``, ``try_classical_pass`` runs
an additional Tesseract attempt with the classical lang model.  The result
competes on score just like the other engines.

Traineddata discovery
---------------------
``is_classical_available(lang)`` checks whether the model exists by
querying ``tesseract --list-langs``.  The result is cached for the
process lifetime.

Configuration
~~~~~~~~~~~~~
.. code-block:: yaml

    ocr:
      classical_ocr: auto          # true | false | "auto"
      classical_lang: "hye_old"    # Tesseract lang name for classical model
      classical_threshold: 15.0    # score below which the classical pass fires
"""

from __future__ import annotations

import functools
import logging
import subprocess
from typing import Any

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

DEFAULT_CLASSICAL_LANG = "hye_old"
DEFAULT_CLASSICAL_THRESHOLD = 15.0


@functools.lru_cache(maxsize=4)
def is_classical_available(lang: str = DEFAULT_CLASSICAL_LANG) -> bool:
    """Return True if *lang* traineddata is installed in Tesseract.

    The check runs ``tesseract --list-langs`` once and caches the result.
    """
    try:
        result = subprocess.run(
            ["tesseract", "--list-langs"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        available = {
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip() and not line.startswith("List of")
        }
        found = lang in available
        if found:
            logger.debug("Classical traineddata '%s' is available", lang)
        else:
            logger.debug(
                "Classical traineddata '%s' not found (available: %s)",
                lang, ", ".join(sorted(available)),
            )
        return found
    except Exception as exc:
        logger.debug("Could not list Tesseract languages: %s", exc)
        return False


def classical_ocr_image(
    pil_image: Image.Image,
    lang: str = DEFAULT_CLASSICAL_LANG,
    psm: int = 6,
    binarization: str = "sauvola",
) -> tuple[str, float] | None:
    """Run Tesseract with the classical-orthography model on *pil_image*.

    Returns ``(clean_text, mean_confidence)`` or ``None`` if the model
    is unavailable or the attempt fails.
    """
    if not is_classical_available(lang):
        return None

    from ._tesseract_lazy import get_pytesseract
    from .preprocessor import BinarizationMethod, preprocess
    from .postprocessor import postprocess
    from .tesseract_config import build_config

    try:
        method = BinarizationMethod(binarization)
        preprocessed = preprocess(pil_image, method=method)
        config = build_config(psm=psm)
        pt = get_pytesseract()

        data = pt.image_to_data(
            preprocessed, lang=lang, config=config, output_type=pt.Output.DICT,
        )
        confs = [c for c in data["conf"] if isinstance(c, (int, float)) and c >= 0]
        mean_conf = sum(confs) / len(confs) if confs else 0.0

        raw = pt.image_to_string(preprocessed, lang=lang, config=config)
        clean = postprocess(raw) if raw else ""
        return clean, round(mean_conf, 2)
    except Exception as exc:
        logger.warning("Classical OCR pass failed: %s", exc)
        return None
