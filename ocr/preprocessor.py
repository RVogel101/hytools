"""Image preprocessing for scanned Armenian pages.

Converts raw PDF pages (as PIL Images) into binarized, deskewed, denoised
images suitable for high-quality Tesseract OCR.

Supports cursive detection: when enabled, pages with cursive-like strokes
get stronger binarization (smaller block, optional morphology) and deskewing.
"""

from __future__ import annotations

import logging
from enum import Enum

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class BinarizationMethod(str, Enum):
    SAUVOLA = "sauvola"
    NIBLACK = "niblack"
    OTSU = "otsu"


def estimate_cursive_likelihood(binary: np.ndarray) -> float:
    """Estimate cursive likelihood from contour elongation and stroke variance.

    Cursive/handwritten text tends to have elongated contours and variable
    stroke widths. Returns 0–1 score; higher = more cursive-like.

    Parameters
    ----------
    binary : np.ndarray
        Binary image (0/255 uint8).

    Returns
    -------
    float
        Score in [0, 1].
    """
    contours, _ = cv2.findContours(
        binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    valid = [c for c in contours if cv2.contourArea(c) > 50]
    if len(valid) < 5:
        return 0.0

    elongations = []
    for c in valid:
        x, y, w, h = cv2.boundingRect(c)
        mn, mx = min(w, h), max(w, h)
        if mn > 0:
            elongations.append(mx / mn)

    if not elongations:
        return 0.0

    mean_el = float(np.mean(elongations))
    var_el = float(np.var(elongations))
    # Cursive: higher elongation (strokes), higher variance
    score = min(1.0, (mean_el - 1.5) * 0.2 + var_el * 0.02)
    return max(0.0, score)


def pil_to_cv2(image: Image.Image) -> np.ndarray:
    """Convert a PIL RGB/RGBA/grayscale image to an OpenCV BGR array."""
    img = image.convert("RGB")
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def cv2_to_pil(img: np.ndarray) -> Image.Image:
    """Convert an OpenCV BGR array to a PIL RGB image."""
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def to_grayscale(img: np.ndarray) -> np.ndarray:
    """Convert a BGR image to grayscale."""
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def denoise(gray: np.ndarray, kernel_size: int = 3) -> np.ndarray:
    """Apply Gaussian denoising to a grayscale image."""
    k = kernel_size if kernel_size % 2 else kernel_size + 1
    return cv2.GaussianBlur(gray, (k, k), 0)


def binarize(
    gray: np.ndarray,
    method: BinarizationMethod = BinarizationMethod.SAUVOLA,
    block_size: int | None = None,
    cursive_mode: bool = False,
) -> np.ndarray:
    """Binarize a grayscale image using the specified method.

    When cursive_mode=True: smaller block (31), stronger denoise (5x5).
    Returns a binary (0/255) uint8 image.
    """
    denoise_kernel = 5 if cursive_mode else 3
    denoised = denoise(gray, kernel_size=denoise_kernel)

    if method == BinarizationMethod.OTSU:
        _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    if method in (BinarizationMethod.SAUVOLA, BinarizationMethod.NIBLACK):
        block = block_size or (31 if cursive_mode else 51)
        block = block if block % 2 else block + 1
        c_val = 10 if method == BinarizationMethod.SAUVOLA else 5
        binary = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block,
            c_val,
        )
        if cursive_mode:
            kernel = np.ones((2, 2), np.uint8)
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        return binary

    raise ValueError(f"Unknown binarization method: {method}")


def deskew(binary: np.ndarray) -> np.ndarray:
    """Rotate *binary* to correct skew using Hough-line-based angle estimation.

    Returns the deskewed binary image.
    """
    coords = np.column_stack(np.where(binary < 128))  # dark pixel coords
    if len(coords) < 10:
        return binary
    angle = cv2.minAreaRect(coords.astype(np.float32))[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5:
        return binary  # negligible skew

    h, w = binary.shape
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(binary, M, (w, h), flags=cv2.INTER_CUBIC, borderValue=(255.0,))
    logger.debug("Deskewed by %.2f degrees", angle)
    return rotated


def preprocess(
    image: Image.Image,
    method: BinarizationMethod = BinarizationMethod.SAUVOLA,
    cursive_mode: bool = False,
    detect_cursive: bool = False,
    cursive_threshold: float = 0.5,
) -> Image.Image:
    """Full preprocessing pipeline: grayscale → binarize → deskew.

    When detect_cursive=True, estimates cursive likelihood from an initial
    binarization. If score >= cursive_threshold, re-runs with cursive_mode.

    Parameters
    ----------
    image:
        Input PIL image (any mode).
    method:
        Binarization algorithm to apply.
    cursive_mode:
        Use cursive-optimized preprocessing (smaller block, morphology).
    detect_cursive:
        Auto-detect cursive and apply cursive_mode when score >= threshold.
    cursive_threshold:
        Score above which to treat as cursive (default 0.5).

    Returns
    -------
    PIL.Image.Image
        Preprocessed grayscale (mode ``"L"``) image.
    """
    bgr = pil_to_cv2(image)
    gray = to_grayscale(bgr)
    binary = binarize(gray, method=method, cursive_mode=cursive_mode)

    if detect_cursive and not cursive_mode:
        score = estimate_cursive_likelihood(binary)
        if score >= cursive_threshold:
            logger.debug("Cursive detected (score=%.2f), re-preprocessing", score)
            cursive_mode = True
            binary = binarize(gray, method=method, cursive_mode=True)

    deskewed = deskew(binary)
    return Image.fromarray(deskewed)
