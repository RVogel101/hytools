"""Validation module for LLM-generated Western Armenian text.

This module provides detailed validation feedback for text generated during
augmentation. The feedback can be used to guide regeneration when the output
fails quality checks.

Validates:
1. Western Armenian dialect markers (vs Eastern Armenian)
2. Classical orthography (vs reformed Soviet spelling)
3. Vocabulary against approved word lists (Nayiri dictionary - future)
4. Armenian script ratio

Returns detailed feedback for failed validations so the LLM can correct
specific issues in regeneration attempts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from ingestion._shared.helpers import (
    compute_wa_score,
    is_western_armenian,
    _CLASSICAL_ORTHO_MARKERS,
    _LEXICAL_MARKERS,
    _WA_VOCABULARY,
    _EASTERN_ARMENIAN_REFORM_MARKERS,
    _EASTERN_INDEFINITE_ARTICLE,
    _EASTERN_VOCABULARY,
    WA_SCORE_THRESHOLD,
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating LLM-generated text for Western Armenian quality.
    
    Attributes
    ----------
    passed:
        True if text passes all validation checks
    wa_score:
        Western Armenian score from language filter (higher = more WA)
    threshold:
        Threshold required to pass WA validation
    armenia_ratio:
        Fraction of characters that are Armenian script
    issues:
        List of specific validation issues found (empty if passed)
    feedback:
        Human-readable feedback for regeneration (for LLM)
    """
    passed: bool
    wa_score: float
    threshold: float
    armenian_ratio: float
    issues: list[str]
    feedback: str
    
    # Specific issue flags for detailed tracking
    has_eastern_markers: bool = False
    has_reformed_spelling: bool = False
    low_classical_markers: bool = False
    low_wa_vocabulary: bool = False


def _compute_armenian_ratio(text: str) -> float:
    """Calculate fraction of Armenian script characters in text."""
    if not text:
        return 0.0
    armenian = sum(1 for c in text if "\u0530" <= c <= "\u058F")
    return armenian / len(text)


def _detect_eastern_armenian_markers(text: str) -> tuple[int, list[str]]:
    """Count Eastern Armenian markers (reform, indefinite article, vocabulary).
    
    Returns
    -------
    tuple[int, list[str]]
        (count_of_ea_markers, list_of_examples)
    """
    ea_count = 0
    examples = []
    all_ea_markers = (
        _EASTERN_ARMENIAN_REFORM_MARKERS
        + _EASTERN_INDEFINITE_ARTICLE
        + _EASTERN_VOCABULARY
    )
    for marker, weight in all_ea_markers:
        count = text.count(marker)
        if count > 0 and weight > 0:
            ea_count += count
            if len(examples) < 5:
                examples.append(f"Found EA marker '{marker}' ({count}x)")
    return ea_count, examples


def _detect_classical_markers(text: str) -> tuple[int, int]:
    """Count classical orthography markers (WA signal).
    
    Returns
    -------
    tuple[int, int]
        (count_of_classical_markers, expected_minimum_for_length)
    """
    classical_count = 0
    
    for marker, weight in _CLASSICAL_ORTHO_MARKERS:
        count = text.count(marker)
        if count > 0:
            classical_count += count
    
    # Estimate expected minimum: ~1 classical marker per 50 characters in WA text
    text_length = len(text)
    expected_min = max(2, text_length // 50)
    
    return classical_count, expected_min


def _detect_wa_vocabulary(text: str) -> int:
    """Count Western Armenian specific vocabulary markers."""
    wa_vocab_count = 0
    
    for word, weight in _WA_VOCABULARY:
        count = text.count(word)
        if count > 0:
            wa_vocab_count += count
    
    return wa_vocab_count


def validate_nayiri_dictionary(text: str) -> tuple[bool, list[str]]:
    """Validate that all words exist in Nayiri dictionary (FUTURE FEATURE).
    
    This is a stub for future implementation. When implemented, this will:
    1. Tokenize the text into individual words
    2. Check each word against the Nayiri dictionary database
    3. Return validation status and list of unknown words
    
    Parameters
    ----------
    text:
        Input text to validate
        
    Returns
    -------
    tuple[bool, list[str]]
        (all_words_valid, list_of_unknown_words)
        
    Notes
    -----
    Current implementation always returns (True, []) as a placeholder.
    TODO: Implement actual Nayiri dictionary lookup once database is ready.
    """
    # TODO: Implement actual Nayiri dictionary validation
    # Steps for future implementation:
    # 1. from cleaning.armenian_tokenizer import extract_words
    # 2. words = extract_words(text)
    # 3. unknown = [w for w in words if not nayiri_db.contains(w)]
    # 4. return (len(unknown) == 0, unknown)
    
    logger.debug("Nayiri dictionary validation not yet implemented (stub)")
    return True, []


def validate_classical_spelling(text: str) -> tuple[bool, list[str]]:
    """Validate that text uses classical Armenian orthography (not reformed).
    
    Checks for:
    - Classical digraphs (եա, իւ) are present
    - Eastern Armenian reformed spellings (յա for եա) are absent
    - Word-internal long-e (classical) vs short-e (reformed)
    
    Parameters
    ----------
    text:
        Input text to validate
        
    Returns
    -------
    tuple[bool, list[str]]
        (uses_classical_spelling, list_of_reform_issues)
    """
    issues = []
    
    # Check for Eastern Armenian reformed markers
    ea_count, ea_examples = _detect_eastern_armenian_markers(text)
    if ea_count > 0:
        issues.extend(ea_examples)
        issues.append(f"Total Eastern Armenian reform markers: {ea_count}")
    
    # Check for sufficient classical markers
    classical_count, expected_min = _detect_classical_markers(text)
    if classical_count < expected_min:
        issues.append(
            f"Low classical orthography markers: {classical_count} "
            f"(expected ≥{expected_min} for text length)"
        )
    
    uses_classical = len(issues) == 0
    return uses_classical, issues


def validate_augmentation_output(
    text: str,
    threshold: float | None = None,
    strict_classical: bool = True,
    check_nayiri: bool = False,
) -> ValidationResult:
    """Comprehensive validation of LLM-generated Western Armenian text.
    
    Validates dialect markers, classical orthography, and optionally vocabulary.
    Returns detailed feedback that can be used to guide regeneration.
    
    Parameters
    ----------
    text:
        Generated text to validate
    threshold:
        Minimum WA score to pass (default: WA_SCORE_THRESHOLD)
    strict_classical:
        If True, enforce classical orthography requirements
    check_nayiri:
        If True, validate against Nayiri dictionary (future feature)
        
    Returns
    -------
    ValidationResult
        Detailed validation result with feedback for regeneration
    """
    if not text or not text.strip():
        return ValidationResult(
            passed=False,
            wa_score=0.0,
            threshold=threshold or WA_SCORE_THRESHOLD,
            armenian_ratio=0.0,
            issues=["Empty or whitespace-only text"],
            feedback="Generated text was empty. Please generate actual Western Armenian text.",
        )
    
    # Compute scores
    wa_score = compute_wa_score(text)
    armenian_ratio = _compute_armenian_ratio(text)
    thresh = threshold or WA_SCORE_THRESHOLD
    passes_wa = wa_score >= thresh
    
    issues = []
    feedback_parts = []
    
    # Check 1: Armenian script ratio
    if armenian_ratio < 0.7:
        issues.append(f"Low Armenian script ratio: {armenian_ratio:.1%}")
        feedback_parts.append(
            f"Text contains too much non-Armenian content ({armenian_ratio:.1%} Armenian). "
            "Write ONLY in Armenian script using Western Armenian."
        )
    
    # Check 2: Western Armenian dialect score
    if not passes_wa:
        issues.append(f"WA score too low: {wa_score:.1f} < {thresh}")
        
        # Detect specific issues
        ea_count, ea_examples = _detect_eastern_armenian_markers(text)
        classical_count, expected_min = _detect_classical_markers(text)
        wa_vocab_count = _detect_wa_vocabulary(text)
        
        has_eastern_markers = ea_count > 0
        low_classical_markers = classical_count < expected_min
        low_wa_vocabulary = wa_vocab_count < 2
        
        feedback_parts.append(
            f"Text does not have sufficient Western Armenian markers (score: {wa_score:.1f}, needed: {thresh})."
        )
        
        if has_eastern_markers:
            issues.append(f"Contains {ea_count} Eastern Armenian markers")
            feedback_parts.append(
                "CRITICAL: Text contains Eastern Armenian reformed spelling. "
                "You must use WESTERN ARMENIAN classical orthography: "
                "use 'եա' (ea) not 'յա' (ya), "
                "use 'իւ' (iw) digraph, "
                "use long-ե in word-internal positions."
            )
        
        if low_classical_markers:
            issues.append(f"Low classical markers: {classical_count} < {expected_min}")
            feedback_parts.append(
                "Text lacks classical orthography markers. "
                "Use Western Armenian classical spelling with digraphs like 'եա', 'իւ', 'օյ'."
            )
        
        if low_wa_vocabulary:
            issues.append(f"Low WA vocabulary: {wa_vocab_count} markers")
            feedback_parts.append(
                "Use Western Armenian specific vocabulary: "
                "կը (present tense), պիտի (future), հոն/հոս (there/here), խօսիլ (speak)."
            )
    else:
        has_eastern_markers = False
        low_classical_markers = False
        low_wa_vocabulary = False
    
    # Check 3: Classical spelling enforcement
    if strict_classical:
        uses_classical, spelling_issues = validate_classical_spelling(text)
        if not uses_classical:
            issues.extend(spelling_issues)
            feedback_parts.append(
                "Spelling issues detected: " + "; ".join(spelling_issues)
            )
    
    # Check 4: Nayiri dictionary (future)
    if check_nayiri:
        all_valid, unknown_words = validate_nayiri_dictionary(text)
        if not all_valid:
            issues.append(f"Contains {len(unknown_words)} words not in Nayiri dictionary")
            feedback_parts.append(
                f"Some words are not standard Western Armenian: {', '.join(unknown_words[:5])}"
                + (" ..." if len(unknown_words) > 5 else "")
            )
    
    # Build result
    passed = len(issues) == 0
    feedback = " ".join(feedback_parts) if feedback_parts else ""
    
    if passed:
        feedback = "Text passes all Western Armenian validation checks."
    
    return ValidationResult(
        passed=passed,
        wa_score=wa_score,
        threshold=thresh,
        armenian_ratio=armenian_ratio,
        issues=issues,
        feedback=feedback,
        has_eastern_markers=has_eastern_markers,
        low_classical_markers=low_classical_markers,
        low_wa_vocabulary=low_wa_vocabulary,
    )


def generate_regeneration_prompt(
    original_text: str,
    validation_result: ValidationResult,
    strategy: Literal["paraphrase", "continue", "topic_write"],
) -> str:
    """Generate a prompt for LLM to regenerate text based on validation feedback.
    
    Parameters
    ----------
    original_text:
        The original source text (not the failed generation)
    validation_result:
        Validation result with specific issues
    strategy:
        Which augmentation strategy is being used
        
    Returns
    -------
    str
        Regeneration prompt with specific corrections needed
    """
    prompt_parts = [
        "REGENERATION REQUIRED: The previous output failed Western Armenian validation.",
        "",
        "ISSUES FOUND:",
    ]
    
    for issue in validation_result.issues:
        prompt_parts.append(f"  - {issue}")
    
    prompt_parts.extend([
        "",
        "CORRECTIONS NEEDED:",
        validation_result.feedback,
        "",
        "REQUIREMENTS:",
        "- Write ONLY in Western Armenian using classical orthography",
        "- Use classical digraphs: եա (ea), իւ (iw), օյ (oy)",
        "- Use Western Armenian vocabulary: կը, պիտի, հոն, հոս, խօսիլ",
        "- Do NOT use Eastern Armenian reformed spelling (յա, etc.)",
        "- Ensure high density of Western Armenian markers",
        "",
    ])
    
    if strategy == "paraphrase":
        prompt_parts.extend([
            "TASK: Paraphrase the following Western Armenian text.",
            f"Original: {original_text}",
            "",
            "Paraphrased version (Western Armenian, classical orthography):",
        ])
    elif strategy == "continue":
        prompt_parts.extend([
            "TASK: Continue the following Western Armenian text.",
            f"Beginning: {original_text}",
            "",
            "Continuation (Western Armenian, classical orthography):",
        ])
    elif strategy == "topic_write":
        prompt_parts.extend([
            f"TASK: Write a new paragraph about: {original_text}",
            "",
            "New paragraph (Western Armenian, classical orthography):",
        ])
    
    return "\n".join(prompt_parts)
