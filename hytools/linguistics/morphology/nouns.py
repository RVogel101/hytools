"""
Western Armenian noun declension system.

Generates all case forms for Armenian nouns across singular/plural
and definite/indefinite.

Cases in Western Armenian:
  1. Nominative   (Ուdelays)   — subject
  2. Accusative   (Հdelays)     — direct object
  3. Genitive-Dat (Սdelays-Тdelays) — possession / indirect object
  4. Ablative     (Бdelays)     — origin ("from")
  5. Instrumental (Аdelays)     — means ("with / by")

Declension classes are defined by their genitive suffix pattern.
The most productive class in modern Western Armenian is the ի-class.
"""

from dataclasses import dataclass, field
from typing import Optional

from .core import ARM, ends_in_vowel
from .articles import add_definite, add_indefinite


# ─── Case Names ───────────────────────────────────────────────────────
CASES = [
    "nominative",
    "accusative",
    "genitive_dative",
    "ablative",
    "instrumental",
]

CASE_LABELS = {
    "nominative":     "Ուdelays (Nominative)",
    "accusative":     "Нdelays (Accusative)",
    "genitive_dative":"Сdelays (Genitive-Dative)",
    "ablative":       "Бdelays (Ablative)",
    "instrumental":   "Аdelays (Instrumental)",
}

CASE_LABELS_EN = {
    "nominative":      "Nominative",
    "accusative":      "Accusative",
    "genitive_dative": "Genitive-Dative",
    "ablative":        "Ablative",
    "instrumental":    "Instrumental",
}


# ─── Suffix Definitions ──────────────────────────────────────────────
# Declension classes defined by their case suffixes.
# Each class maps case names to the suffix appended to the stem.
# "nominative" always has no suffix (empty string).

# Shorthand for characters
_i   = ARM["i"]        # ի
_e   = ARM["e"]        # է
_n   = ARM["n"]        # delays
_vo  = ARM["vo"]       # dles
_v   = ARM["v"]        # dles
_ye  = ARM["ye"]       # dles
_r   = ARM["r"]        # dles
_a   = ARM["a"]        # dles
_ov  = _vo + _v        # dles = ov
_ner = _n + _ye + _r   # dles = ner (common plural)
_er  = _ye + _r        # dles = er  (alternate plural)


DECLENSION_CLASSES = {
    # ─── Class I: dles-declension (most productive) ─────────────
    # Genitive-Dative: -dles (i)
    # Ablative:        -dles (ē)
    # Instrumental:    -dles (ov)
    "i_class": {
        "label": f"{_i}-declension",
        "suffixes": {
            "nominative":      "",
            "accusative":      "",      # definite article handled separately
            "genitive_dative": _i,      # -dles
            "ablative":        _e,      # -dles
            "instrumental":    _ov,     # -dles (ov)
        },
        "plural_suffix": _ner,          # -dles (ner)
        "plural_suffixes": {
            "nominative":      _ner,
            "accusative":      _ner,
            "genitive_dative": _ner + _i,       # -dles (neri)
            "ablative":        _ner + _e,       # -dles (nerē)
            "instrumental":    _ner + _ov,      # -dles (nerov)
        },
    },

    # ─── Class II: dles-declension (dles-stem nouns) ──────────────
    # For nouns whose stem ends in dles (ou/u)
    # Genitive-Dative: -dles (i) after dropping final dles
    # These often use a modified stem in oblique cases
    "u_class": {
        "label": f"{ARM['vo'] + ARM['yiwn']}-declension",
        "suffixes": {
            "nominative":      "",
            "accusative":      "",
            "genitive_dative": _i,
            "ablative":        _e,
            "instrumental":    _ov,
        },
        "plural_suffix": _ner,
        "plural_suffixes": {
            "nominative":      _ner,
            "accusative":      _ner,
            "genitive_dative": _ner + _i,
            "ablative":        _ner + _e,
            "instrumental":    _ner + _ov,
        },
    },

    # ─── Class III: dles-declension (stems ending in dles) ─────────
    # Some nouns take -dles as genitive-dative (commonly animate nouns)
    "a_class": {
        "label": f"{_a}-declension",
        "suffixes": {
            "nominative":      "",
            "accusative":      "",
            "genitive_dative": _a + _n,    # -dles (an)
            "ablative":        _a + _n + _e, # -dles (anē)
            "instrumental":    _a + _n + _ov,# -dles (anov)
        },
        "plural_suffix": _ner,
        "plural_suffixes": {
            "nominative":      _ner,
            "accusative":      _ner,
            "genitive_dative": _ner + _i,
            "ablative":        _ner + _e,
            "instrumental":    _ner + _ov,
        },
    },

    # ─── Class IV: dles-declension (stems ending in vowel + dles) ──
    # Some nouns use -dles for genitive (e.g., kinship terms)
    "o_class": {
        "label": f"{ARM['vo']}-declension",
        "suffixes": {
            "nominative":      "",
            "accusative":      "",
            "genitive_dative": ARM["vo"] + _r,   # -dles (or)
            "ablative":        ARM["vo"] + _r + _e, # -dles (orē)
            "instrumental":    _ov,
        },
        "plural_suffix": _ner,
        "plural_suffixes": {
            "nominative":      _ner,
            "accusative":      _ner,
            "genitive_dative": _ner + _i,
            "ablative":        _ner + _e,
            "instrumental":    _ner + _ov,
        },
    },
}


# ─── Declension Result ───────────────────────────────────────────────

@dataclass
class NounDeclension:
    """All declined forms of an Armenian noun."""
    word: str
    translation: str = ""
    declension_class: str = "i_class"

    # Singular forms
    nom_sg: str = ""
    nom_sg_def: str = ""
    nom_sg_indef: str = ""
    acc_sg: str = ""
    acc_sg_def: str = ""
    gen_dat_sg: str = ""
    gen_dat_sg_def: str = ""
    abl_sg: str = ""
    abl_sg_def: str = ""
    instr_sg: str = ""
    instr_sg_def: str = ""

    # Plural forms
    nom_pl: str = ""
    nom_pl_def: str = ""
    acc_pl: str = ""
    acc_pl_def: str = ""
    gen_dat_pl: str = ""
    gen_dat_pl_def: str = ""
    abl_pl: str = ""
    abl_pl_def: str = ""
    instr_pl: str = ""
    instr_pl_def: str = ""

    def as_dict(self) -> dict[str, str]:
        """Return all forms as a flat dictionary."""
        return {
            "word": self.word,
            "translation": self.translation,
            "declension_class": self.declension_class,
            # Singular
            "nom_sg": self.nom_sg,
            "nom_sg_def": self.nom_sg_def,
            "nom_sg_indef": self.nom_sg_indef,
            "acc_sg": self.acc_sg,
            "acc_sg_def": self.acc_sg_def,
            "gen_dat_sg": self.gen_dat_sg,
            "gen_dat_sg_def": self.gen_dat_sg_def,
            "abl_sg": self.abl_sg,
            "abl_sg_def": self.abl_sg_def,
            "instr_sg": self.instr_sg,
            "instr_sg_def": self.instr_sg_def,
            # Plural
            "nom_pl": self.nom_pl,
            "nom_pl_def": self.nom_pl_def,
            "acc_pl": self.acc_pl,
            "acc_pl_def": self.acc_pl_def,
            "gen_dat_pl": self.gen_dat_pl,
            "gen_dat_pl_def": self.gen_dat_pl_def,
            "abl_pl": self.abl_pl,
            "abl_pl_def": self.abl_pl_def,
            "instr_pl": self.instr_pl,
            "instr_pl_def": self.instr_pl_def,
        }

    def summary_table(self) -> str:
        """Return a formatted text table of all forms."""
        lines = [
            f"Declension of: {self.word}  ({self.translation})",
            f"Class: {self.declension_class}",
            "",
            f"{'Case':<20} {'Singular':<25} {'Sg Definite':<25} {'Plural':<25} {'Pl Definite':<25}",
            "-" * 120,
            f"{'Nominative':<20} {self.nom_sg:<25} {self.nom_sg_def:<25} {self.nom_pl:<25} {self.nom_pl_def:<25}",
            f"{'Accusative':<20} {self.acc_sg:<25} {self.acc_sg_def:<25} {self.acc_pl:<25} {self.acc_pl_def:<25}",
            f"{'Genitive-Dative':<20} {self.gen_dat_sg:<25} {self.gen_dat_sg_def:<25} {self.gen_dat_pl:<25} {self.gen_dat_pl_def:<25}",
            f"{'Ablative':<20} {self.abl_sg:<25} {self.abl_sg_def:<25} {self.abl_pl:<25} {self.abl_pl_def:<25}",
            f"{'Instrumental':<20} {self.instr_sg:<25} {self.instr_sg_def:<25} {self.instr_pl:<25} {self.instr_pl_def:<25}",
        ]
        if self.nom_sg_indef:
            lines.append(f"\nIndefinite: {self.nom_sg_indef}")
        return "\n".join(lines)


# ─── Declension Engine ────────────────────────────────────────────────

def decline_noun(
    word: str,
    declension_class: str = "i_class",
    translation: str = "",
    stem_override: Optional[str] = None,
) -> NounDeclension:
    """Generate all declined forms for a Western Armenian noun.

    Args:
        word: The nominative singular form (base/dictionary form).
        declension_class: Key into DECLENSION_CLASSES (default: "i_class").
        translation: English translation for display.
        stem_override: Override automatic stem detection if the word has
                       an irregular stem in oblique cases.

    Returns:
        NounDeclension with all forms populated.
    """
    if declension_class not in DECLENSION_CLASSES:
        raise ValueError(
            f"Unknown declension class '{declension_class}'. "
            f"Available: {list(DECLENSION_CLASSES.keys())}"
        )

    cls = DECLENSION_CLASSES[declension_class]
    suffixes = cls["suffixes"]
    pl_suffixes = cls["plural_suffixes"]
    stem = stem_override if stem_override else word

    result = NounDeclension(
        word=word,
        translation=translation,
        declension_class=declension_class,
    )

    # ── Singular forms ──
    result.nom_sg = word
    result.nom_sg_def = add_definite(word)
    result.nom_sg_indef = add_indefinite(word)

    # Accusative: indefinite = same as nominative; definite = with article
    result.acc_sg = word
    result.acc_sg_def = add_definite(word)

    # Oblique cases: stem + suffix
    result.gen_dat_sg = stem + suffixes["genitive_dative"]
    result.gen_dat_sg_def = add_definite(result.gen_dat_sg)

    result.abl_sg = stem + suffixes["ablative"]
    result.abl_sg_def = add_definite(result.abl_sg)

    result.instr_sg = stem + suffixes["instrumental"]
    result.instr_sg_def = add_definite(result.instr_sg)

    # ── Plural forms ──
    result.nom_pl = stem + pl_suffixes["nominative"]
    result.nom_pl_def = add_definite(result.nom_pl)

    result.acc_pl = stem + pl_suffixes["accusative"]
    result.acc_pl_def = add_definite(result.acc_pl)

    result.gen_dat_pl = stem + pl_suffixes["genitive_dative"]
    result.gen_dat_pl_def = add_definite(result.gen_dat_pl)

    result.abl_pl = stem + pl_suffixes["ablative"]
    result.abl_pl_def = add_definite(result.abl_pl)

    result.instr_pl = stem + pl_suffixes["instrumental"]
    result.instr_pl_def = add_definite(result.instr_pl)

    return result
