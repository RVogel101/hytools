"""Production monitoring for OCR pipeline runs.

Tracks per-page outcomes across a full PDF run and emits warnings when
failure rates exceed configurable thresholds.  This catches systemic
problems (wrong DPI, missing traineddata, degraded scans) early, before
an entire batch silently produces blank output.

Integration
-----------
``RunMonitor`` is instantiated at the start of ``ocr_pdf()`` and receives
a ``record(status)`` call at every ``continue`` / success exit path.
After the page loop, ``check_alerts()`` evaluates the accumulated counts
and logs warnings.

Alert thresholds
~~~~~~~~~~~~~~~~
.. code-block:: yaml

    ocr:
      monitor_alert_threshold: 0.10      # fraction (0–1)
      monitor_min_pages: 3               # don't alert on tiny PDFs

MongoDB (optional)
~~~~~~~~~~~~~~~~~~
When a ``db_client`` is present, ``check_alerts()`` also writes a summary
document to the ``ocr_run_alerts`` collection.

Schema for ``ocr_run_alerts``
-----------------------------
.. list-table::
   :header-rows: 1
   :widths: 22 12 66

   * - Field
     - Type
     - Description
   * - ``run_id``
     - ``str``
     - UUID v4 of the OCR run.
   * - ``pdf_name``
     - ``str``
     - Filename of the processed PDF.
   * - ``total_pages``
     - ``int``
     - Number of pages processed (including skipped-existing).
   * - ``status_counts``
     - ``dict``
     - ``{status_string: count}`` dictionary.
   * - ``failure_rate``
     - ``float``
     - Fraction of pages that were non-text / below-confidence /
       empty-after-fallback.
   * - ``alert``
     - ``bool``
     - ``True`` when *failure_rate* exceeds the threshold.
   * - ``alert_message``
     - ``str``
     - Human-readable message (empty when no alert).
   * - ``created_at``
     - ``datetime``
     - UTC time the summary was written.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Statuses considered "failures" for alert purposes
_FAILURE_STATUSES = frozenset({
    "non_text",
    "below_confidence",
    "empty_after_fallback",
})

DEFAULT_ALERT_THRESHOLD = 0.10  # 10 %
DEFAULT_MIN_PAGES = 3


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RunMonitor:
    """Accumulates per-page outcomes and checks alert conditions.

    Parameters
    ----------
    run_id : str
        The UUID for the current ``ocr_pdf()`` run.
    pdf_name : str
        Filename (not path) of the PDF being processed.
    alert_threshold : float
        Fraction of failure pages (0–1) that triggers an alert.
    min_pages : int
        Minimum total pages before alerting (avoids noise on tiny PDFs).
    """

    def __init__(
        self,
        run_id: str,
        pdf_name: str,
        alert_threshold: float = DEFAULT_ALERT_THRESHOLD,
        min_pages: int = DEFAULT_MIN_PAGES,
    ) -> None:
        self.run_id = run_id
        self.pdf_name = pdf_name
        self.alert_threshold = alert_threshold
        self.min_pages = min_pages
        self._counts: Counter[str] = Counter()

    # ── Recording ─────────────────────────────────────────────────────────

    def record(self, status: str) -> None:
        """Record the outcome for one page.

        *status* should match the values written to ``OCRPageMetric.status``:
        ``"success"``, ``"text_layer"``, ``"non_text"``,
        ``"below_confidence"``, ``"empty_after_fallback"``, ``"skipped"``.
        """
        self._counts[status] += 1

    # ── Evaluation ────────────────────────────────────────────────────────

    @property
    def total(self) -> int:
        return sum(self._counts.values())

    @property
    def failure_count(self) -> int:
        return sum(self._counts[s] for s in _FAILURE_STATUSES)

    @property
    def failure_rate(self) -> float:
        t = self.total
        if t == 0:
            return 0.0
        return self.failure_count / t

    def check_alerts(self, collection: Any | None = None) -> str | None:
        """Evaluate alert conditions and log / persist if triggered.

        Parameters
        ----------
        collection
            Optional MongoDB collection (``ocr_run_alerts``).  When
            provided the run summary is always written; the ``alert``
            boolean indicates whether the threshold was exceeded.

        Returns
        -------
        str or None
            The alert message if the threshold was exceeded, else ``None``.
        """
        rate = self.failure_rate
        triggered = (
            self.total >= self.min_pages
            and rate > self.alert_threshold
        )

        msg = ""
        if triggered:
            msg = (
                f"OCR ALERT: {self.pdf_name} — "
                f"{self.failure_count}/{self.total} pages "
                f"({rate:.0%}) are blank or low-confidence "
                f"(threshold {self.alert_threshold:.0%}). "
                f"Breakdown: {dict(self._counts)}"
            )
            logger.warning(msg)

        # Persist summary to MongoDB (always, so dashboards work)
        if collection is not None:
            doc = {
                "run_id": self.run_id,
                "pdf_name": self.pdf_name,
                "total_pages": self.total,
                "status_counts": dict(self._counts),
                "failure_rate": round(rate, 4),
                "alert": triggered,
                "alert_message": msg,
                "created_at": _utcnow(),
            }
            try:
                collection.insert_one(doc)
            except Exception as exc:
                logger.warning("Failed to write run alert summary: %s", exc)

        return msg if triggered else None

    def to_dict(self) -> dict[str, Any]:
        """Serialise current state (useful for testing)."""
        return {
            "run_id": self.run_id,
            "pdf_name": self.pdf_name,
            "total_pages": self.total,
            "status_counts": dict(self._counts),
            "failure_rate": round(self.failure_rate, 4),
            "alert_threshold": self.alert_threshold,
            "min_pages": self.min_pages,
        }
