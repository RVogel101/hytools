"""Tests for the morphology engine (core, nouns, verbs, articles, detect, irregular_verbs, difficulty)."""

import pytest

from hytools.linguistics.morphology.core import (
    ARM,
    ARM_UPPER,
    VOWELS,
    DIGRAPH_U,
    is_vowel,
    is_armenian,
    ends_in_vowel,
    get_stem,
    to_lower,
    to_upper_initial,
    count_syllables,
    romanize,
)
from hytools.linguistics.morphology.nouns import (
    DECLENSION_CLASSES,
    NounDeclension,
    decline_noun,
)
from hytools.linguistics.morphology.verbs import (
    VERB_CLASSES,
    VerbConjugation,
    conjugate_verb,
)
from hytools.linguistics.morphology.articles import (
    add_definite,
    add_indefinite,
    remove_definite,
)
from hytools.linguistics.morphology.detect import (
    detect_verb_class,
    detect_noun_class,
    detect_pos_and_class,
)
from hytools.linguistics.morphology.irregular_verbs import (
    get_irregular_overrides,
    is_irregular,
    list_irregular_infinitives,
)
from hytools.linguistics.morphology.difficulty import (
    count_syllables_with_context,
    score_word_difficulty,
    WordDifficultyAnalysis,
    analyze_word,
)


# ── Helpers ──────────────────────────────────────────────────────────

# Build some test words from ARM dict for consistent, non-invented references.
_ye = ARM["ye"]
_l = ARM["l"]
_a = ARM["a"]
_i = ARM["i"]
_n = ARM["n"]
_r = ARM["r"]
_m = ARM["m"]
_s = ARM["s"]
_g = ARM["g"]
_k = ARM["k"]
_d = ARM["d"]
_vo = ARM["vo"]
_yiwn = ARM["yiwn"]
_h = ARM["h"]
_t = ARM["t"]
_b = ARM["b"]
_gh = ARM["gh"]
_p = ARM["p"]
_y_schwa = ARM["y_schwa"]


class TestCore:
    """Tests for core.py: ARM dict, vowels, character functions."""

    def test_arm_dict_has_all_keys(self):
        assert len(ARM) == 38  # 38 Armenian lowercase letter mappings

    def test_arm_upper_dict_has_all_keys(self):
        assert len(ARM_UPPER) == 38

    def test_vowels_contains_expected(self):
        for key in ["a", "ye", "e", "y_schwa", "i", "vo", "o"]:
            assert ARM[key] in VOWELS

    def test_is_vowel_true(self):
        assert is_vowel(ARM["a"])
        assert is_vowel(ARM["ye"])
        assert is_vowel(ARM["i"])

    def test_is_vowel_false(self):
        assert not is_vowel(ARM["p"])
        assert not is_vowel(ARM["m"])
        assert not is_vowel(ARM["l"])

    def test_is_armenian(self):
        assert is_armenian(ARM["a"])
        assert is_armenian(ARM_UPPER["A"])
        assert not is_armenian("A")
        assert not is_armenian("5")

    def test_ends_in_vowel_simple(self):
        word = _m + _a  # ends in vowel
        assert ends_in_vowel(word)

    def test_ends_in_vowel_consonant(self):
        word = _m + _a + _n  # ends in consonant
        assert not ends_in_vowel(word)

    def test_ends_in_vowel_digraph(self):
        word = _k + DIGRAPH_U  # ends in OU digraph
        assert ends_in_vowel(word)

    def test_ends_in_vowel_empty(self):
        assert not ends_in_vowel("")

    def test_get_stem_vowel_ending(self):
        word = _m + _a  # stem = m
        assert get_stem(word) == _m

    def test_get_stem_consonant_ending(self):
        word = _m + _a + _n
        assert get_stem(word) == word

    def test_get_stem_digraph(self):
        word = _k + DIGRAPH_U
        assert get_stem(word) == _k

    def test_to_lower(self):
        upper_a = ARM_UPPER["A"]
        result = to_lower(upper_a)
        assert result == ARM["a"]

    def test_to_lower_mixed(self):
        mixed = ARM_UPPER["A"] + ARM["m"]
        result = to_lower(mixed)
        assert result == ARM["a"] + ARM["m"]

    def test_to_upper_initial(self):
        word = ARM["a"] + ARM["m"]
        result = to_upper_initial(word)
        assert result == ARM_UPPER["A"] + ARM["m"]

    def test_to_upper_initial_empty(self):
        assert to_upper_initial("") == ""

    def test_count_syllables_single(self):
        word = _m + _a + _n  # man — 1 vowel = 1 syllable
        assert count_syllables(word) == 1

    def test_count_syllables_digraph(self):
        # OU digraph counts as 1 vowel
        word = _k + _vo + _yiwn + _r  # kour — 1 syllable
        assert count_syllables(word) == 1

    def test_count_syllables_two(self):
        word = _m + _a + _r + _i  # mari — 2 syllables
        assert count_syllables(word) == 2

    def test_digraph_u_value(self):
        assert DIGRAPH_U == _vo + _yiwn

    def test_romanize_basic(self):
        word = ARM["a"]  # single ա
        result = romanize(word)
        assert isinstance(result, str)
        assert len(result) > 0


class TestNouns:
    """Tests for nouns.py: declension classes and decline_noun."""

    def test_declension_classes_exist(self):
        assert "i_class" in DECLENSION_CLASSES
        assert "u_class" in DECLENSION_CLASSES
        assert "a_class" in DECLENSION_CLASSES
        assert "o_class" in DECLENSION_CLASSES

    def test_declension_class_has_suffixes(self):
        for name, cls in DECLENSION_CLASSES.items():
            assert "suffixes" in cls
            assert "plural_suffixes" in cls

    def test_decline_noun_returns_dataclass(self):
        # Use a simple i_class word
        word = _m + _a + _n  # man
        result = decline_noun(word, declension_class="i_class")
        assert isinstance(result, NounDeclension)
        assert result.word == word
        assert result.declension_class == "i_class"

    def test_decline_noun_nominative(self):
        word = _m + _a + _n
        result = decline_noun(word, declension_class="i_class")
        assert result.nom_sg == word

    def test_decline_noun_definite(self):
        word = _m + _a + _n
        result = decline_noun(word, declension_class="i_class")
        # Definite after consonant adds ը
        assert result.nom_sg_def.endswith(_y_schwa)

    def test_decline_noun_invalid_class(self):
        with pytest.raises(ValueError, match="Unknown declension class"):
            decline_noun("test", declension_class="z_class")

    def test_decline_noun_as_dict(self):
        word = _m + _a + _n
        result = decline_noun(word, declension_class="i_class")
        d = result.as_dict()
        assert isinstance(d, dict)
        assert "nom_sg" in d

    def test_decline_noun_summary_table(self):
        word = _m + _a + _n
        result = decline_noun(word, declension_class="i_class")
        table = result.summary_table()
        assert isinstance(table, str)
        assert len(table) > 0

    def test_decline_noun_stem_override(self):
        word = _m + _a + _n
        stem = _m + _a
        result = decline_noun(word, declension_class="i_class", stem_override=stem)
        # Gen-dat should use the overridden stem
        assert result.gen_dat_sg.startswith(stem)


class TestVerbs:
    """Tests for verbs.py: verb classes and conjugate_verb."""

    def test_verb_classes_exist(self):
        assert "e_class" in VERB_CLASSES
        assert "a_class" in VERB_CLASSES

    def test_verb_class_has_required_keys(self):
        for name, cls in VERB_CLASSES.items():
            assert "subjunctive" in cls
            assert "aorist" in cls
            assert "imperfect" in cls
            assert "conditional" in cls

    def test_conjugate_verb_returns_dataclass(self):
        infinitive = _k + _d + _r + _ye + _l  # kdr-el
        result = conjugate_verb(infinitive, verb_class="e_class")
        assert isinstance(result, VerbConjugation)
        assert result.infinitive == infinitive
        assert result.verb_class == "e_class"

    def test_conjugate_verb_has_all_tenses(self):
        infinitive = _k + _d + _r + _ye + _l
        result = conjugate_verb(infinitive, verb_class="e_class")
        assert isinstance(result.present, dict) and len(result.present) > 0
        assert isinstance(result.subjunctive, dict) and len(result.subjunctive) > 0
        assert isinstance(result.past_aorist, dict) and len(result.past_aorist) > 0
        assert isinstance(result.imperfect, dict) and len(result.imperfect) > 0
        assert isinstance(result.future, dict) and len(result.future) > 0
        assert isinstance(result.conditional, dict) and len(result.conditional) > 0

    def test_conjugate_verb_invalid_class(self):
        with pytest.raises(ValueError, match="Unknown verb class"):
            conjugate_verb("test", verb_class="z_class")

    def test_conjugate_verb_as_dict(self):
        infinitive = _k + _d + _r + _ye + _l
        result = conjugate_verb(infinitive, verb_class="e_class")
        d = result.as_dict()
        assert isinstance(d, dict)

    def test_conjugate_verb_summary_table(self):
        infinitive = _k + _d + _r + _ye + _l
        result = conjugate_verb(infinitive, verb_class="e_class")
        table = result.summary_table()
        assert isinstance(table, str)
        assert len(table) > 0

    def test_conjugate_verb_root_override(self):
        infinitive = _k + _d + _r + _ye + _l
        root = _k + _d + _r
        result = conjugate_verb(infinitive, verb_class="e_class", root_override=root)
        assert result.root == root


class TestArticles:
    """Tests for articles.py: definite/indefinite article generation."""

    def test_add_definite_consonant_ending(self):
        word = _m + _a + _n  # ends in consonant
        result = add_definite(word)
        assert result == word + _y_schwa

    def test_add_definite_vowel_ending(self):
        word = _m + _a  # ends in vowel
        result = add_definite(word)
        assert result == word + _n

    def test_add_definite_empty(self):
        assert add_definite("") == ""

    def test_add_definite_already_ends_n(self):
        word = _m + _a + _n  # ends in ն — consonant, not same as article logic
        result = add_definite(word)
        # ն is NOT a vowel, so it gets ը
        assert result.endswith(_y_schwa)

    def test_add_indefinite(self):
        word = _m + _a + _n
        result = add_indefinite(word)
        assert " " in result  # indefinite is appended with space

    def test_add_indefinite_empty(self):
        assert add_indefinite("") == ""

    def test_remove_definite_consonant(self):
        word = _m + _a + _n + _y_schwa  # definite form
        result = remove_definite(word)
        assert result == _m + _a + _n

    def test_remove_definite_no_article(self):
        word = _m + _a + _n
        assert remove_definite(word) == word

    def test_remove_definite_empty(self):
        assert remove_definite("") == ""


class TestDetect:
    """Tests for detect.py: POS and class auto-detection."""

    def test_detect_verb_class_e(self):
        infinitive = _k + _d + _r + _ye + _l  # ends in -el
        assert detect_verb_class(infinitive) == "e_class"

    def test_detect_verb_class_a(self):
        infinitive = _k + _d + _r + _a + _l  # ends in -al
        assert detect_verb_class(infinitive) == "a_class"

    def test_detect_noun_class_default(self):
        word = _m + _a + _n  # simple noun → i_class
        assert detect_noun_class(word) == "i_class"

    def test_detect_noun_class_u(self):
        word = _k + DIGRAPH_U  # ends in OU → u_class
        assert detect_noun_class(word) == "u_class"

    def test_detect_pos_and_class_verb(self):
        infinitive = _k + _d + _r + _ye + _l
        pos, cls = detect_pos_and_class(infinitive)
        assert pos == "verb"
        assert cls == "e_class"

    def test_detect_pos_and_class_noun(self):
        word = _m + _a + _n
        pos, cls = detect_pos_and_class(word)
        assert pos == "noun"

    def test_detect_pos_and_class_a_verb(self):
        infinitive = _k + _d + _r + _a + _l
        pos, cls = detect_pos_and_class(infinitive)
        assert pos == "verb"
        assert cls == "a_class"


class TestIrregularVerbs:
    """Tests for irregular_verbs.py: irregular verb lookup."""

    def test_list_irregular_infinitives_not_empty(self):
        result = list_irregular_infinitives()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_is_irregular_known_verb(self):
        infinitives = list_irregular_infinitives()
        assert is_irregular(infinitives[0])

    def test_is_irregular_regular_verb(self):
        regular = _k + _d + _r + _ye + _l
        assert not is_irregular(regular)

    def test_get_irregular_overrides_known(self):
        infinitives = list_irregular_infinitives()
        overrides = get_irregular_overrides(infinitives[0])
        assert overrides is not None
        assert isinstance(overrides, dict)

    def test_get_irregular_overrides_unknown(self):
        regular = _k + _d + _r + _ye + _l
        assert get_irregular_overrides(regular) is None

    def test_conjugate_verb_applies_overrides(self):
        infinitives = list_irregular_infinitives()
        inf = infinitives[0]
        result = conjugate_verb(inf, verb_class="e_class")
        # Should have some forms populated
        assert result.infinitive == inf


class TestDifficulty:
    """Tests for difficulty.py: word difficulty scoring."""

    def test_count_syllables_with_context(self):
        word = _m + _a + _n
        result = count_syllables_with_context(word)
        assert isinstance(result, int)
        assert result >= 1

    def test_score_word_difficulty_noun(self):
        word = _m + _a + _n
        score = score_word_difficulty(word, pos="noun")
        assert isinstance(score, float)
        assert 1.0 <= score <= 10.0

    def test_score_word_difficulty_verb(self):
        word = _k + _d + _r + _ye + _l
        score = score_word_difficulty(word, pos="verb")
        assert isinstance(score, float)
        assert 1.0 <= score <= 10.0

    def test_analyze_word_returns_dataclass(self):
        word = _m + _a + _n
        result = analyze_word(word, pos="noun")
        assert isinstance(result, WordDifficultyAnalysis)

    def test_word_difficulty_analysis_has_score(self):
        word = _m + _a + _n
        result = analyze_word(word, pos="noun")
        assert hasattr(result, "overall_difficulty")
        assert result.overall_difficulty >= 1.0
