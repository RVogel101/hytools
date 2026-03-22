"""
FSRS-4 (Free Spaced Repetition Scheduler) implementation.

Implements the FSRS v4 algorithm for spaced repetition scheduling.
The algorithm models memory with two parameters:
  - **Stability** (S): expected number of days until recall probability drops to 90%.
  - **Difficulty** (D): intrinsic difficulty of the card (1–10 scale).

Ratings follow the Anki convention:
  1 = Again — forgot the card
  2 = Hard  — recalled with difficulty
  3 = Good  — recalled correctly
  4 = Easy  — recalled effortlessly

Reference: https://github.com/open-spaced-repetition/fsrs4anki

Usage
-----
::

    scheduler = FSRSScheduler()

    # First review of a new card
    state = scheduler.first_review(rating=3)
    # state.stability ≈ 4.93 days,  state.interval = 5

    # Subsequent review
    state = scheduler.review(state, rating=3, elapsed_days=5)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional


# ─── FSRS v4 default parameters ──────────────────────────────────────
# 17 optimised weights from the FSRS-4 paper / open-spaced-repetition.
# These are the same defaults shipped in fsrs4anki v4.0.
DEFAULT_WEIGHTS: tuple[float, ...] = (
    0.4,       # w0  — initial stability for rating 1 (Again)
    0.6,       # w1  —                           2 (Hard)
    2.4,       # w2  —                           3 (Good)
    5.8,       # w3  —                           4 (Easy)
    4.93,      # w4  — initial difficulty mean
    0.94,      # w5  — initial difficulty variance
    0.86,      # w6  — difficulty reversion factor
    0.01,      # w7  — stability increase (base)
    1.49,      # w8  — stability increase exponent (difficulty)
    0.14,      # w9  — stability increase exponent (stability)
    0.94,      # w10 — stability increase exponent (retrievability)
    2.18,      # w11 — fail stability decay (base)
    0.05,      # w12 — fail stability decay (difficulty)
    0.34,      # w13 — fail stability decay (stability)
    1.26,      # w14 — fail stability decay (retrievability)
    0.29,      # w15 — hard penalty multiplier
    2.61,      # w16 — easy bonus multiplier
)


# ─── Card State ───────────────────────────────────────────────────────

@dataclass
class CardState:
    """Scheduling state for a single card."""
    stability: float = 0.0        # S — days until R drops to 90%
    difficulty: float = 5.0       # D — card difficulty (1–10)
    interval: int = 0             # computed next interval (days), for convenience
    last_review: Optional[str] = None  # ISO-8601 timestamp
    next_due: Optional[str] = None     # ISO-8601 timestamp
    reps: int = 0                 # total number of reviews

    def as_dict(self) -> dict:
        return {
            "stability": round(self.stability, 4),
            "difficulty": round(self.difficulty, 4),
            "interval": self.interval,
            "last_review": self.last_review,
            "next_due": self.next_due,
            "reps": self.reps,
        }


# ─── FSRS Scheduler ──────────────────────────────────────────────────

class FSRSScheduler:
    """FSRS v4 scheduler.

    Args:
        weights: 17-element tuple of model parameters. Uses DEFAULT_WEIGHTS
                 when not specified.
        desired_retention: target recall probability (default 0.9 = 90%).
    """

    def __init__(
        self,
        weights: tuple[float, ...] = DEFAULT_WEIGHTS,
        desired_retention: float = 0.9,
    ):
        if len(weights) != 17:
            raise ValueError(f"FSRS v4 requires exactly 17 weights, got {len(weights)}")
        if not 0.5 <= desired_retention <= 0.99:
            raise ValueError(f"desired_retention must be in [0.5, 0.99], got {desired_retention}")
        self.w = weights
        self.desired_retention = desired_retention

    # ── Public API ────────────────────────────────────────────────────

    def first_review(
        self,
        rating: int,
        now: Optional[datetime] = None,
    ) -> CardState:
        """Schedule a brand-new card after its first review.

        Args:
            rating: 1 (Again) | 2 (Hard) | 3 (Good) | 4 (Easy)
            now: current UTC datetime (defaults to utcnow)

        Returns:
            Filled CardState with stability, difficulty, interval, timestamps.
        """
        _validate_rating(rating)
        now = now or datetime.now(timezone.utc)

        s = self._init_stability(rating)
        d = self._init_difficulty(rating)
        interval = self._next_interval(s)

        due = now + timedelta(days=interval)
        return CardState(
            stability=s,
            difficulty=d,
            interval=interval,
            last_review=now.isoformat(),
            next_due=due.isoformat(),
            reps=1,
        )

    def review(
        self,
        state: CardState,
        rating: int,
        elapsed_days: float,
        now: Optional[datetime] = None,
    ) -> CardState:
        """Update a card's scheduling state after a review.

        Args:
            state: current CardState from the previous review.
            rating: 1–4  (Again / Hard / Good / Easy)
            elapsed_days: days since the last review (can be fractional).
            now: current UTC datetime.

        Returns:
            New CardState with updated stability, difficulty, interval.
        """
        _validate_rating(rating)
        now = now or datetime.now(timezone.utc)

        retrievability = self._retrievability(elapsed_days, state.stability)
        new_d = self._next_difficulty(state.difficulty, rating)
        new_d = self._mean_reversion(new_d)
        new_d = _clamp(new_d, 1.0, 10.0)

        if rating == 1:  # Again → lapse
            new_s = self._next_forget_stability(
                state.stability, new_d, retrievability
            )
        else:
            new_s = self._next_recall_stability(
                state.stability, new_d, retrievability, rating
            )

        interval = self._next_interval(new_s)
        due = now + timedelta(days=interval)

        return CardState(
            stability=new_s,
            difficulty=new_d,
            interval=interval,
            last_review=now.isoformat(),
            next_due=due.isoformat(),
            reps=state.reps + 1,
        )

    # ── Core formulas ─────────────────────────────────────────────────

    def _init_stability(self, rating: int) -> float:
        """S_0(G) — initial stability based on first-review rating."""
        return max(self.w[rating - 1], 0.1)

    def _init_difficulty(self, rating: int) -> float:
        """D_0(G) — initial difficulty based on first-review rating."""
        d = self.w[4] - (rating - 3) * self.w[5]
        return _clamp(d, 1.0, 10.0)

    def _retrievability(self, elapsed_days: float, stability: float) -> float:
        """R(t, S) — probability of recall at time t given stability S."""
        if stability <= 0:
            return 0.0
        return (1 + elapsed_days / (9 * stability)) ** -1

    def _next_difficulty(self, d: float, rating: int) -> float:
        """D'(D, G) — updated difficulty after a review."""
        delta = -(self.w[6] * (rating - 3))
        return d + delta

    def _mean_reversion(self, d: float) -> float:
        """Apply mean reversion to difficulty (pull toward w[4])."""
        return self.w[7] * self.w[4] + (1 - self.w[7]) * d

    def _next_recall_stability(
        self, s: float, d: float, r: float, rating: int,
    ) -> float:
        """S'_r(S, D, R, G) — new stability after a successful recall."""
        # Base factor
        factor = math.exp(self.w[8]) * (
            (11 - d) ** self.w[9]
            * s ** (-self.w[10])
            * (math.exp((1 - r) * self.w[11]) - 1)
        )
        # Hard penalty / easy bonus
        if rating == 2:
            factor *= self.w[15]
        elif rating == 4:
            factor *= self.w[16]

        new_s = s * (1 + factor)
        return max(new_s, 0.1)

    def _next_forget_stability(
        self, s: float, d: float, r: float,
    ) -> float:
        """S'_f(S, D, R) — new stability after a lapse (rating=1)."""
        new_s = (
            self.w[11]
            * d ** (-self.w[12])
            * ((s + 1) ** self.w[13] - 1)
            * math.exp((1 - r) * self.w[14])
        )
        return _clamp(new_s, 0.1, s)  # never increase stability on lapse

    def _next_interval(self, stability: float) -> int:
        """Compute the next review interval from stability and desired retention."""
        interval = (stability / 9) * (1 / self.desired_retention - 1)
        return max(1, round(interval))


# ─── Helpers ──────────────────────────────────────────────────────────

def _validate_rating(rating: int) -> None:
    if rating not in (1, 2, 3, 4):
        raise ValueError(f"Rating must be 1–4, got {rating}")


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
