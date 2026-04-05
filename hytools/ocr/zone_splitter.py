"""Per-page mixed-language zone OCR.

On pages that contain both Armenian and English text (e.g. bilingual textbooks),
using a single ``hye+eng`` pass forces Tesseract to compromise.  This module:

1. Runs a quick probe pass in mixed mode to get word-level bounding boxes.
2. Classifies each word box as *Armenian* or *Latin* by script ratio.
3. Clusters adjacent same-script boxes into rectangular zones.
4. Re-OCRs each zone with the best single-language model.
5. Recombines zone texts in top-to-bottom reading order.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from PIL import Image

from ._tesseract_lazy import get_pytesseract
from .postprocessor import postprocess
from .preprocessor import BinarizationMethod, preprocess
from .tesseract_config import (
    ARMENIAN_RANGE_END,
    ARMENIAN_RANGE_START,
    TESSERACT_LANG_ARMENIAN,
    TESSERACT_LANG_ENGLISH,
    TESSERACT_LANG_MIXED,
    build_config,
)

logger = logging.getLogger(__name__)

# Minimum fraction of Armenian characters in a word to classify it as Armenian.
_ARMENIAN_WORD_THRESHOLD = 0.5

# Minimum word confidence from Tesseract to consider a box for zone building.
_MIN_WORD_CONF = 10

# Vertical gap (in pixels) allowed between two boxes before they are split
# into separate zones.
_MAX_VERTICAL_GAP_PX = 60

# Horizontal gap (in pixels) allowed between two boxes on the same line.
_MAX_HORIZONTAL_GAP_PX = 120

# Minimum number of characters in a zone for it to be re-OCR'd separately.
_MIN_ZONE_CHARS = 3


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class WordBox:
    """A single word detected by Tesseract ``image_to_data``."""
    text: str
    left: int
    top: int
    width: int
    height: int
    conf: float
    script: str  # "arm" | "lat" | "other"


@dataclass
class Zone:
    """A rectangular region containing words of the same script."""
    script: str  # "arm" | "lat"
    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0
    boxes: list[WordBox] = field(default_factory=list)

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def add(self, box: WordBox) -> None:
        self.boxes.append(box)
        if not self.boxes[:-1]:  # first box
            self.left = box.left
            self.top = box.top
            self.right = box.left + box.width
            self.bottom = box.top + box.height
        else:
            self.left = min(self.left, box.left)
            self.top = min(self.top, box.top)
            self.right = max(self.right, box.left + box.width)
            self.bottom = max(self.bottom, box.top + box.height)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _classify_word(text: str) -> str:
    """Classify a word as ``"arm"``, ``"lat"``, or ``"other"``."""
    arm = 0
    lat = 0
    for ch in text:
        cp = ord(ch)
        if ARMENIAN_RANGE_START <= cp <= ARMENIAN_RANGE_END:
            arm += 1
        elif (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A):
            lat += 1
    total = arm + lat
    if total == 0:
        return "other"
    if arm / total >= _ARMENIAN_WORD_THRESHOLD:
        return "arm"
    return "lat"


def _extract_word_boxes(
    pil_image: Image.Image,
    lang: str = TESSERACT_LANG_MIXED,
    psm: int = 6,
    binarization: str = "sauvola",
) -> list[WordBox]:
    """Run Tesseract ``image_to_data`` and return classified word boxes."""
    method = BinarizationMethod(binarization)
    preprocessed = preprocess(pil_image, method=method)
    cfg = build_config(psm=psm)
    pt = get_pytesseract()
    data = pt.image_to_data(
        preprocessed, lang=lang, config=cfg, output_type=pt.Output.DICT,
    )

    boxes: list[WordBox] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = 0.0
        if conf < _MIN_WORD_CONF:
            continue

        boxes.append(WordBox(
            text=text,
            left=int(data["left"][i]),
            top=int(data["top"][i]),
            width=int(data["width"][i]),
            height=int(data["height"][i]),
            conf=conf,
            script=_classify_word(text),
        ))

    return boxes


def _should_merge(zone: Zone, box: WordBox) -> bool:
    """Decide whether *box* belongs in *zone* based on proximity."""
    # Vertical overlap or close gap
    box_bottom = box.top + box.height
    v_gap = max(0, box.top - zone.bottom, zone.top - box_bottom)
    if v_gap > _MAX_VERTICAL_GAP_PX:
        return False

    # Horizontal overlap or close gap
    box_right = box.left + box.width
    h_gap = max(0, box.left - zone.right, zone.left - box_right)
    if h_gap > _MAX_HORIZONTAL_GAP_PX:
        return False

    return True


def build_zones(boxes: list[WordBox]) -> list[Zone]:
    """Cluster word boxes into same-script rectangular zones.

    Boxes are processed top-to-bottom, left-to-right.  A box is merged into
    the most recent zone of the same script if it is within the gap thresholds;
    otherwise a new zone is started.
    """
    if not boxes:
        return []

    # Sort by reading order: top then left
    sorted_boxes = sorted(boxes, key=lambda b: (b.top, b.left))

    zones: list[Zone] = []
    for box in sorted_boxes:
        if box.script == "other":
            continue

        # Try to merge into an existing zone of the same script
        merged = False
        for zone in reversed(zones):  # recent zones first
            if zone.script == box.script and _should_merge(zone, box):
                zone.add(box)
                merged = True
                break

        if not merged:
            z = Zone(script=box.script)
            z.add(box)
            zones.append(z)

    return zones


def _lang_for_script(
    script: str,
    lang_armenian: str = TESSERACT_LANG_ARMENIAN,
    lang_english: str = TESSERACT_LANG_ENGLISH,
    lang_mixed: str = TESSERACT_LANG_MIXED,
) -> str:
    if script == "arm":
        return lang_armenian
    if script == "lat":
        return lang_english
    return lang_mixed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_mixed_page(boxes: list[WordBox], min_minority_ratio: float = 0.10) -> bool:
    """Return *True* when both Armenian and Latin words appear on the page.

    *min_minority_ratio* is the minimum fraction the smaller script must
    represent for the page to be considered "mixed" (avoids triggering on a
    single stray English word in an otherwise Armenian page).
    """
    arm = sum(1 for b in boxes if b.script == "arm")
    lat = sum(1 for b in boxes if b.script == "lat")
    total = arm + lat
    if total == 0:
        return False
    minority = min(arm, lat)
    return minority / total >= min_minority_ratio


def zone_ocr_page(
    pil_image: Image.Image,
    *,
    probe_lang: str = TESSERACT_LANG_MIXED,
    binarization: str = "sauvola",
    psm: int = 6,
    lang_armenian: str = TESSERACT_LANG_ARMENIAN,
    lang_english: str = TESSERACT_LANG_ENGLISH,
    lang_mixed: str = TESSERACT_LANG_MIXED,
    min_minority_ratio: float = 0.10,
    padding: int = 10,
) -> Optional[str]:
    """Perform zone-based OCR on a mixed-language page.

    Returns the recombined text (Armenian and English zones OCR'd with their
    optimal single-language model), or ``None`` when the page is not mixed
    enough to benefit from zone splitting.

    Parameters
    ----------
    pil_image:
        The full-page PIL image (already rasterized at the target DPI).
    probe_lang:
        Language used for the initial word-detection probe.
    binarization:
        Binarization method for preprocessing.
    psm:
        Tesseract page segmentation mode.
    lang_armenian, lang_english, lang_mixed:
        Tesseract language strings for zone re-OCR.
    min_minority_ratio:
        Minimum fraction that the smaller script must represent.
    padding:
        Extra pixels to include around each zone crop (avoids clipping).
    """
    boxes = _extract_word_boxes(pil_image, lang=probe_lang, psm=psm, binarization=binarization)
    if not is_mixed_page(boxes, min_minority_ratio=min_minority_ratio):
        return None

    zones = build_zones(boxes)
    if len(zones) < 2:
        return None

    logger.debug("Zone OCR: %d zones detected (%s)",
                 len(zones),
                 ", ".join(f"{z.script}:{len(z.boxes)}w" for z in zones))

    # Sort zones top-to-bottom for final reading order
    zones.sort(key=lambda z: (z.top, z.left))

    w, h = pil_image.size
    parts: list[str] = []
    pt = get_pytesseract()

    for zone in zones:
        # Skip tiny zones
        char_count = sum(len(b.text) for b in zone.boxes)
        if char_count < _MIN_ZONE_CHARS:
            # Keep the probe text for tiny zones
            parts.append(" ".join(b.text for b in zone.boxes))
            continue

        # Crop with padding
        x0 = max(0, zone.left - padding)
        y0 = max(0, zone.top - padding)
        x1 = min(w, zone.right + padding)
        y1 = min(h, zone.bottom + padding)
        crop = pil_image.crop((x0, y0, x1, y1))

        lang = _lang_for_script(zone.script, lang_armenian, lang_english, lang_mixed)
        method = BinarizationMethod(binarization)
        preprocessed = preprocess(crop, method=method)
        cfg = build_config(psm=psm)
        raw = pt.image_to_string(preprocessed, lang=lang, config=cfg)
        text = postprocess(raw) if raw else ""

        if text.strip():
            parts.append(text.strip())
            logger.debug("  Zone %s (%d,%d)-(%d,%d): %d chars, lang=%s",
                         zone.script, zone.left, zone.top, zone.right, zone.bottom,
                         len(text), lang)

    if not parts:
        return None

    return "\n\n".join(parts)
