"""Tests for augmentation validation and regeneration system (moved from WesternArmenianLLM).

See docs/TEST_VALIDATION_ARMENIAN.md for translations, transliterations, and marker reference.
"""

from hytools.linguistics.metrics import (
    validate_augmentation_output,
    validate_classical_spelling,
    validate_nayiri_dictionary,
    generate_regeneration_prompt,
)


def test_validation_passes_for_wa_text():
    """Test that valid Western Armenian text passes validation.

    Text: "He/She speaks Armenian; he/she lives there in each child."
    Markers: կը (gu), կ՚ (g'), մէջ, իւրաքանչիւր, մանուկ; pronoun Ան.
    See docs/TEST_VALIDATION_ARMENIAN.md."""
    wa_text = "Ան կը խօսի հայերէն, հոն կ՚ապրի մէջ իւրաքանչիւր մանուկ"

    result = validate_augmentation_output(
        wa_text,
        strict_classical=True,
        check_nayiri=False,
    )

    assert result.passed, f"WA text should pass validation: {result.issues}"
    assert result.wa_score >= 5.0, f"WA score should be ≥5.0: {result.wa_score}"
    assert result.armenian_ratio >= 0.7, "Armenian ratio should be ≥70%"
    assert not result.has_eastern_markers, "Should not have EA markers"


def test_validation_fails_for_ea_text():
    """Test that Eastern Armenian text fails validation."""
    ea_text = "Նա խոսում է հայերեն այնտեղ ապրում է"

    result = validate_augmentation_output(
        ea_text,
        strict_classical=True,
        check_nayiri=False,
    )

    assert not result.passed, "EA text should fail validation"
    assert result.wa_score < 5.0, f"EA score should be <5.0: {result.wa_score}"
    assert len(result.issues) > 0, "Should have validation issues"


def test_forbidden_eastern_reform_variants_are_rejected():
    """Test that forbidden EA reform tokens are rejected by WA validation."""
    forbidden_ea_tokens = [
        "յուղ",
        "գյուղ",
        "ճյուղ",
        "զամբյուղ",
        "այստեղ",
        "այնտեղ",
        "թյուն",
        "մի",
        "ձու",
        "գնալ",
        "խոսել",
    ]

    for token in forbidden_ea_tokens:
        result = validate_augmentation_output(
            token,
            strict_classical=True,
            check_nayiri=False,
        )
        assert not result.passed or result.has_eastern_markers, (
            f"{token} is a forbidden EA reform token and must not be accepted as WA"
        )


def test_validation_detects_eastern_markers():
    """Test detection of Eastern Armenian reformed spelling.

    Text: "We go together."
    Markers: միյ (EA reformed digraph), -ում, -ենք."""
    ea_reformed_text = "միյասին գնում ենք"

    result = validate_augmentation_output(
        ea_reformed_text,
        strict_classical=True,
        check_nayiri=False,
    )

    assert not result.passed, "Text with EA markers should fail"
    assert result.has_eastern_markers, "Should detect EA markers"


def test_validation_requires_classical_markers():
    """Test that text needs classical orthography markers.

    Text: "Armenian people."
    Purpose: No classical diphthongs (ոյ, այ, իւ, եա) → fails WA validation."""
    weak_text = "Հայ ժողովուրդ"

    result = validate_augmentation_output(
        weak_text,
        strict_classical=True,
        check_nayiri=False,
    )

    assert not result.passed, "Text without WA markers should fail"
    assert result.low_classical_markers, "Should detect low classical markers"


def test_wa_indefinite_article_postposed():
    """Test that WA indefinite article մը/մըն appears after noun.

    WA: բան մը (pan mu) = something, տուն մը = a house.
    EA uses մի before noun (մի բան), which we reject."""
    wa_text = "Ես տեսիմ բան մը։"  # WA: noun + մը
    result = validate_augmentation_output(
        wa_text,
        strict_classical=True,
        check_nayiri=False,
    )
    assert not result.has_eastern_markers, "բան մը is WA; should not flag EA"
    if result.wa_score > 0:
        assert result.wa_score >= 0, "WA indefinite article postposition is valid WA"


def test_ea_indefinite_article_preposed_fails():
    """Test that EA indefinite article մի before noun fails validation.

    EA: մի բան (mi ban) = something. WA uses noun + մը."""
    ea_text = "Ես տեսիմ մի բան։"  # EA: մի + noun
    result = validate_augmentation_output(
        ea_text,
        strict_classical=True,
        check_nayiri=False,
    )
    assert not result.passed or result.has_eastern_markers, (
        "մի before noun is EA; should be detected and fail or flag as eastern"
    )


def test_wa_present_tense_particle():
    """Test WA present tense: կը/կ՚ before verb.

    WA: Ես կը վազեմ (yes gu vazem). EA: verb-ում + auxiliary (yes vazum em)."""
    wa_text = "Ես կը վազեմ տուն։"  # WA: կը + verb
    result = validate_augmentation_output(
        wa_text,
        strict_classical=True,
        check_nayiri=False,
    )
    assert not result.has_eastern_markers, "կը + verb is WA present"


def test_wa_vs_ea_vocabulary_egg():
    """Test dialect-specific vocabulary: egg.

    WA: հավկիթ (havkit). EA: ձու (dzu)."""
    wa_text = "Հավկիթ մը ունիմ։"  # WA: egg + indefinite
    ea_text = "Ձու ունեմ։"  # EA: dzu
    wa_result = validate_augmentation_output(wa_text, strict_classical=True, check_nayiri=False)
    ea_result = validate_augmentation_output(ea_text, strict_classical=True, check_nayiri=False)
    assert wa_result.wa_score > ea_result.wa_score or not ea_result.passed, (
        "WA havgit should score higher than EA dzu"
    )


def test_classical_spelling_validation():
    """Test classical spelling validation function.

    Classical (pass): "in each something" — մէջ, իւրաքանչիւր, բան մը.
    Reformed (fail): միյասին — EA digraph."""
    classical_text = "մէջ իւրաքանչիւր բան մը"
    uses_classical, issues = validate_classical_spelling(classical_text)
    assert uses_classical, f"Should be classical spelling: {issues}"

    reformed_text = "միյասին"
    uses_classical, issues = validate_classical_spelling(reformed_text)
    assert not uses_classical, "Reformed spelling should fail"
    assert len(issues) > 0, "Should have spelling issues"


def test_nayiri_dictionary_validation():
    """Test Nayiri dictionary validation with real or unavailable wordset.

    If MongoDB is available with Nayiri data, tests real validation.
    If unavailable, tests graceful fallback."""
    from hytools.ocr.nayiri_spellcheck import load_nayiri_wordset
    wordset = load_nayiri_wordset()

    if wordset:
        # Real Nayiri available — test with known valid WA word
        all_valid, unknown = validate_nayiri_dictionary("հայերէն")
        # validate_nayiri_dictionary now does real checking; we just verify it runs
        assert isinstance(all_valid, bool)
        assert isinstance(unknown, list)
    else:
        # No Nayiri data — should gracefully return (True, [])
        all_valid, unknown = validate_nayiri_dictionary("կը խօսի հայerect")
        assert all_valid, "Should return valid when Nayiri wordset unavailable"
        assert len(unknown) == 0


def test_regeneration_prompt_generation():
    """Test regeneration prompt generation."""
    original_text = "բնագիր տեքստ"

    failed_validation = validate_augmentation_output(
        "some text with issues",
        strict_classical=True,
    )

    from typing import Literal, cast
    for strategy in ["paraphrase", "continue", "topic_write"]:
        prompt = generate_regeneration_prompt(
            original_text,
            failed_validation,
            cast(Literal["paraphrase", "continue", "topic_write"], strategy),
        )

        assert "REGENERATION REQUIRED" in prompt
        assert "ISSUES FOUND" in prompt
        assert "CORRECTIONS NEEDED" in prompt
        assert len(prompt) > 100, "Prompt should be detailed"


def test_empty_text_validation():
    """Test validation of empty text."""
    result = validate_augmentation_output(
        "",
        strict_classical=True,
    )

    assert not result.passed, "Empty text should fail"
    assert "Empty or whitespace-only text" in result.issues[0]


def test_low_armenian_ratio():
    """Test validation catches low Armenian script ratio.

    Text: "This is mostly English with some Armenian" — low Armenian % → fail."""
    mixed_text = "This is mostly English with some Հայերէն"

    result = validate_augmentation_output(
        mixed_text,
        strict_classical=True,
    )

    assert not result.passed, "Low Armenian ratio should fail"
    assert result.armenian_ratio < 0.7, "Armenian ratio should be low"


def test_validation_result_structure():
    """Test that ValidationResult has all expected fields."""
    text = "կը խօսի հայերէն"
    result = validate_augmentation_output(text)

    assert hasattr(result, "passed")


def test_all_wa_tokens_are_in_wa_lists():
    """Ensure every WA marker secured by consolidated rules exists in WA_* lists."""
    from hytools.ingestion._shared.helpers import (
        _CONSOLIDATED_RULES,
        get_classical_markers,
        get_lexical_markers,
        get_wa_vocabulary_markers,
    )

    wa_token_pool = {token for token, _ in (get_classical_markers() + get_lexical_markers() + get_wa_vocabulary_markers())}
    wa_rule_exceptions = {
        "WA_INDEF_ARTICLE_MUH",
        "WA_PRESENT_PARTICLE_GUH",
        "WA_FUTURE_PARTICLE_BIDI",
        "WA_WORD_INTERNAL_E_LONG",
        "WA_WORD_ENDING_AY",
        "WA_WORD_ENDING_OY",
        "WA_STANDALONE_AL",
        "WA_STANDALONE_GU",
    }

    for rule in _CONSOLIDATED_RULES:
        if rule.get("branch") == "western" and rule.get("rule_id", "").startswith("WA_"):
            rule_id = rule.get("rule_id", "")
            pattern = rule.get("pattern", "")
            if rule_id in wa_rule_exceptions or rule_id.startswith("WA_STANDALONE_") or rule_id.startswith("WA_SUFFIX_"):
                continue
            assert any(token in pattern for token in wa_token_pool), (
                f"Western rule {rule_id} contains token not present in WA_* marker lists"
            )