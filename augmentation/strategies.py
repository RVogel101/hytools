"""Augmentation strategies — both LLM-based and non-LLM transforms.

Each strategy is a callable that takes a paragraph string and returns
the augmented text (or ``None`` if it should be skipped / failed
validation).  LLM strategies accept an ``LLMClient`` at construction.
"""

from __future__ import annotations

import logging
import random
import re
from abc import ABC, abstractmethod

from cleaning.language_filter import is_western_armenian
from linguistics.metrics import (
    validate_augmentation_output,
    generate_regeneration_prompt,
)

logger = logging.getLogger(__name__)

# Armenian sentence-ending punctuation (standard + Armenian full-stop ։)
_SENTENCE_RE = re.compile(r"(?<=[։.!?])\s+")

# Minimum Armenian character ratio for output validation
_MIN_ARMENIAN_RATIO = 0.50


def _armenian_ratio(text: str) -> float:
    """Fraction of characters that are in the Armenian Unicode block."""
    if not text:
        return 0.0
    arm = sum(1 for c in text if "\u0530" <= c <= "\u058F" or "\uFB13" <= c <= "\uFB17")
    return arm / len(text)


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text.strip())
    return [s.strip() for s in parts if s.strip()]


# ═══════════════════════════════════════════════════════════════════════
# Base
# ═══════════════════════════════════════════════════════════════════════

class Strategy(ABC):
    """Base class for all augmentation strategies."""

    name: str = "base"
    requires_llm: bool = False

    @abstractmethod
    def __call__(self, text: str) -> str | None:
        """Return augmented text, or None to skip."""
        ...


# ═══════════════════════════════════════════════════════════════════════
# LLM strategies
# ═══════════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = (
    "You are an expert in Western Armenian (\u0531\u0580\u0565\u0582\u0574\u057f\u0561\u0570\u0561\u0575\u0565\u0580\u0567\u0576). "
    "Always respond ONLY in Western Armenian using classical orthography. "
    "Do not include any English, explanations, or meta-commentary."
)


class ParaphraseStrategy(Strategy):
    """Ask the LLM to paraphrase a WA paragraph."""

    name = "paraphrase"
    requires_llm = True

    def __init__(
        self,
        llm_client,
        validate_wa: bool = True,
        max_retries: int = 3,
        strict_classical: bool = True,
        check_nayiri: bool = False,
    ) -> None:
        from augmentation.llm_client import LLMClient
        self._llm: LLMClient = llm_client
        self._validate = validate_wa
        self._max_retries = max_retries
        self._strict_classical = strict_classical
        self._check_nayiri = check_nayiri

    def __call__(self, text: str) -> str | None:
        prompt = (
            "Paraphrase the following Western Armenian text. "
            "Keep the same meaning but change the wording. "
            "Write ONLY in Western Armenian using classical orthography.\n\n"
            f"Original:\n{text}\n\n"
            "Paraphrased version:"
        )
        last_validation = None
        # Attempt generation with retries on validation failure
        for attempt in range(self._max_retries + 1):
            if attempt == 0:
                # First attempt: use original prompt
                current_prompt = prompt
            else:
                # Regeneration attempt: use feedback from previous failure
                logger.debug(
                    f"Paraphrase regeneration attempt {attempt}/{self._max_retries} "
                    f"after validation failure"
                )
                assert last_validation is not None  # set when previous attempt failed validation
                current_prompt = generate_regeneration_prompt(
                    text, last_validation, "paraphrase"
                )
            
            result = self._llm.generate(current_prompt, system=_SYSTEM_PROMPT)
            out = result["text"].strip()
            
            # Validate output
            if self._validate:
                validation = validate_augmentation_output(
                    out,
                    strict_classical=self._strict_classical,
                    check_nayiri=self._check_nayiri,
                )
                
                if validation.passed:
                    if attempt > 0:
                        logger.info(
                            f"Paraphrase succeeded after {attempt} regeneration(s) "
                            f"(WA score: {validation.wa_score:.1f})"
                        )
                    return out
                else:
                    # Validation failed - store for regeneration feedback
                    last_validation = validation
                    logger.debug(
                        f"Paraphrase validation failed (attempt {attempt + 1}): "
                        f"{', '.join(validation.issues)}"
                    )
                    
                    if attempt == self._max_retries:
                        logger.warning(
                            f"Paraphrase failed after {self._max_retries} retries: "
                            f"{validation.feedback}"
                        )
                        return None
                    # Continue to next retry
            else:
                # Validation disabled - accept output
                return out
        
        return None


class ContinueStrategy(Strategy):
    """Give the LLM the first half of a paragraph and ask it to continue."""

    name = "continue"
    requires_llm = True

    def __init__(
        self,
        llm_client,
        validate_wa: bool = True,
        max_retries: int = 3,
        strict_classical: bool = True,
        check_nayiri: bool = False,
    ) -> None:
        from augmentation.llm_client import LLMClient
        self._llm: LLMClient = llm_client
        self._validate = validate_wa
        self._max_retries = max_retries
        self._strict_classical = strict_classical
        self._check_nayiri = check_nayiri

    def __call__(self, text: str) -> str | None:
        sentences = _split_sentences(text)
        if len(sentences) < 2:
            return None
        mid = max(1, len(sentences) // 2)
        seed = " ".join(sentences[:mid])
        
        prompt = (
            "Continue writing the following Western Armenian text in the same "
            "style and register. Write ONLY in Western Armenian using classical "
            "orthography.\n\n"
            f"{seed}"
        )
        last_validation = None
        # Attempt generation with retries on validation failure
        for attempt in range(self._max_retries + 1):
            if attempt == 0:
                # First attempt: use original prompt
                current_prompt = prompt
            else:
                # Regeneration attempt: use feedback from previous failure
                logger.debug(
                    f"Continue regeneration attempt {attempt}/{self._max_retries} "
                    f"after validation failure"
                )
                assert last_validation is not None
                current_prompt = generate_regeneration_prompt(
                    seed, last_validation, "continue"
                )
            
            result = self._llm.generate(current_prompt, system=_SYSTEM_PROMPT)
            continuation = result["text"].strip()
            out = seed + " " + continuation
            
            # Validate output
            if self._validate:
                validation = validate_augmentation_output(
                    out,
                    strict_classical=self._strict_classical,
                    check_nayiri=self._check_nayiri,
                )
                
                if validation.passed:
                    if attempt > 0:
                        logger.info(
                            f"Continue succeeded after {attempt} regeneration(s) "
                            f"(WA score: {validation.wa_score:.1f})"
                        )
                    return out
                else:
                    # Validation failed - store for regeneration feedback
                    last_validation = validation
                    logger.debug(
                        f"Continue validation failed (attempt {attempt + 1}): "
                        f"{', '.join(validation.issues)}"
                    )
                    
                    if attempt == self._max_retries:
                        logger.warning(
                            f"Continue failed after {self._max_retries} retries: "
                            f"{validation.feedback}"
                        )
                        return None
                    # Continue to next retry
            else:
                # Validation disabled - accept output
                return out
        
        return None


class TopicWriteStrategy(Strategy):
    """Generate a new WA paragraph on a topic extracted from source text."""

    name = "topic_write"
    requires_llm = True

    def __init__(
        self,
        llm_client,
        validate_wa: bool = True,
        max_retries: int = 3,
        strict_classical: bool = True,
        check_nayiri: bool = False,
    ) -> None:
        from augmentation.llm_client import LLMClient
        self._llm: LLMClient = llm_client
        self._validate = validate_wa
        self._max_retries = max_retries
        self._strict_classical = strict_classical
        self._check_nayiri = check_nayiri

    def __call__(self, text: str) -> str | None:
        # Extract topic from source text (simplified: just use first sentence)
        sentences = _split_sentences(text)
        if not sentences:
            return None
        topic = sentences[0][:100] + "..." if len(sentences[0]) > 100 else sentences[0]
        
        prompt = (
            "Read the following Western Armenian passage and identify its main topic. "
            "Then write a NEW, ORIGINAL paragraph about the same topic in Western Armenian "
            "using classical orthography. Do NOT copy the original text.\n\n"
            f"Original passage:\n{text}\n\n"
            "New paragraph on the same topic:"
        )
        last_validation = None
        # Attempt generation with retries on validation failure
        for attempt in range(self._max_retries + 1):
            if attempt == 0:
                # First attempt: use original prompt
                current_prompt = prompt
            else:
                # Regeneration attempt: use feedback from previous failure
                logger.debug(
                    f"TopicWrite regeneration attempt {attempt}/{self._max_retries} "
                    f"after validation failure"
                )
                assert last_validation is not None
                current_prompt = generate_regeneration_prompt(
                    topic, last_validation, "topic_write"
                )
            
            result = self._llm.generate(current_prompt, system=_SYSTEM_PROMPT)
            out = result["text"].strip()
            
            # Validate output
            if self._validate:
                validation = validate_augmentation_output(
                    out,
                    strict_classical=self._strict_classical,
                    check_nayiri=self._check_nayiri,
                )
                
                if validation.passed:
                    if attempt > 0:
                        logger.info(
                            f"TopicWrite succeeded after {attempt} regeneration(s) "
                            f"(WA score: {validation.wa_score:.1f})"
                        )
                    return out
                else:
                    # Validation failed - store for regeneration feedback
                    last_validation = validation
                    logger.debug(
                        f"TopicWrite validation failed (attempt {attempt + 1}): "
                        f"{', '.join(validation.issues)}"
                    )
                    
                    if attempt == self._max_retries:
                        logger.warning(
                            f"TopicWrite failed after {self._max_retries} retries: "
                            f"{validation.feedback}"
                        )
                        return None
                    # Continue to next retry
            else:
                # Validation disabled - accept output
                return out
        
        return None


# ═══════════════════════════════════════════════════════════════════════
# Non-LLM strategies (fast, CPU-only)
# ═══════════════════════════════════════════════════════════════════════

class SentenceShuffleStrategy(Strategy):
    """Randomly reorder sentences within a paragraph."""

    name = "sentence_shuffle"
    requires_llm = False

    def __init__(self, min_sentences: int = 3) -> None:
        self._min = min_sentences

    def __call__(self, text: str) -> str | None:
        sentences = _split_sentences(text)
        if len(sentences) < self._min:
            return None
        shuffled = sentences[:]
        random.shuffle(shuffled)
        if shuffled == sentences:
            # Guarantee a different order.
            shuffled.reverse()
        return " ".join(shuffled)


class RandomDeletionStrategy(Strategy):
    """Randomly drop sentences from a paragraph."""

    name = "random_deletion"
    requires_llm = False

    def __init__(self, deletion_prob: float = 0.15, min_remaining: int = 2) -> None:
        self._prob = deletion_prob
        self._min_remaining = min_remaining

    def __call__(self, text: str) -> str | None:
        sentences = _split_sentences(text)
        if len(sentences) <= self._min_remaining:
            return None
        kept = [s for s in sentences if random.random() > self._prob]
        if len(kept) < self._min_remaining:
            kept = sentences[: self._min_remaining]
        if len(kept) == len(sentences):
            # Ensure at least one deletion.
            kept.pop(random.randrange(len(kept)))
        return " ".join(kept) if kept else None


class WordDropoutStrategy(Strategy):
    """Randomly remove individual words (token-level noise)."""

    name = "word_dropout"
    requires_llm = False

    def __init__(self, dropout_prob: float = 0.10) -> None:
        self._prob = dropout_prob

    def __call__(self, text: str) -> str | None:
        words = text.split()
        if len(words) < 6:
            return None
        kept = [w for w in words if random.random() > self._prob]
        if len(kept) < 4:
            return None
        return " ".join(kept)


# ═══════════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════════

def build_strategies(
    llm_client=None,
    *,
    validate_wa: bool = True,
    max_retries: int = 3,
    strict_classical: bool = True,
    check_nayiri: bool = False,
    enabled: dict[str, bool] | None = None,
) -> list[Strategy]:
    """Instantiate all enabled strategies.

    Parameters
    ----------
    llm_client:
        Required for LLM strategies.  If *None*, only non-LLM strategies
        are returned.
    validate_wa:
        If True, validate LLM outputs for Western Armenian dialect markers.
    max_retries:
        Maximum number of regeneration attempts when validation fails.
    strict_classical:
        If True, enforce classical orthography requirements.
    check_nayiri:
        If True, validate vocabulary against Nayiri dictionary (future feature).
    enabled:
        Map of ``strategy_name -> bool``.  Strategies not listed default to
        enabled.
    """
    en = enabled or {}
    strats: list[Strategy] = []

    # LLM strategies
    if llm_client is not None:
        if en.get("paraphrase", True):
            strats.append(ParaphraseStrategy(
                llm_client,
                validate_wa=validate_wa,
                max_retries=max_retries,
                strict_classical=strict_classical,
                check_nayiri=check_nayiri,
            ))
        if en.get("continue", True):
            strats.append(ContinueStrategy(
                llm_client,
                validate_wa=validate_wa,
                max_retries=max_retries,
                strict_classical=strict_classical,
                check_nayiri=check_nayiri,
            ))
        if en.get("topic_write", True):
            strats.append(TopicWriteStrategy(
                llm_client,
                validate_wa=validate_wa,
                max_retries=max_retries,
                strict_classical=strict_classical,
                check_nayiri=check_nayiri,
            ))

    # Non-LLM strategies
    if en.get("sentence_shuffle", True):
        strats.append(SentenceShuffleStrategy())
    if en.get("random_deletion", True):
        strats.append(RandomDeletionStrategy())
    if en.get("word_dropout", True):
        strats.append(WordDropoutStrategy())

    return strats
