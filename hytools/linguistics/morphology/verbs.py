"""
Western Armenian verb conjugation system.

Generates conjugated forms across tenses and persons for Armenian verbs.

Key tenses in Western Armenian:
  - Present Indicative  (prefix կdelays gə + subjunctive form)
  - Past / Aorist       (simple past, synthetic)
  - Imperfect           (past continuous)
  - Future              (prefix delays bidi + subjunctive form)
  - Subjunctive         (base conjugation form)
  - Imperative          (command form, 2nd person)
  - Past Participle     (used in compound tenses)

Verb classes (Western Armenian):
  - dles-class: infinitive ends in -dles (most common)
  - dles-class: infinitive ends in -dles (stative/intransitive)
  - Irregular verbs: separate paradigms

Infinitive suffix: -dles (el) for Class I, -dles (al) for Class II

NOTE: All transliteration keys follow Western Armenian phonology.
See morphology/core.py for the full consonant shift table.
"""

from dataclasses import dataclass, field
from typing import Optional

from .core import ARM
from .irregular_verbs import get_irregular_overrides


# ─── Character shortcuts (WA transliteration) ────────────────────────
_ye  = ARM["ye"]       # dles (ye)
_a   = ARM["a"]        # dles (a)
_i   = ARM["i"]        # dles (i)
_e   = ARM["e"]        # dles (ē)
_r   = ARM["r"]        # dles (r)
_n   = ARM["n"]        # dles (n)
_m   = ARM["m"]        # dles (m)
_s   = ARM["s"]        # dles (s)
_k   = ARM["k"]        # dles (WA: k — unvoiced velar)
_g   = ARM["g"]        # dles (WA: g — voiced velar; note: EA would call this "k")
_d   = ARM["d"]        # dles (WA: d) — note: EA would call this "t"
_l   = ARM["l"]        # dles (l)
_k_asp = ARM["k_asp"]  # dles (k')
_schwa = ARM["y_schwa"]# dles (ə)
_vo  = ARM["vo"]       # dles (vo/o)
_v   = ARM["v"]        # dles (v)
_ch_asp = ARM["ch_asp"]# dles (ch') — used in negative particle
_dz  = ARM["dz"]       # dles (WA: dz) — note: EA would call this "ts"
_c_asp = ARM["c_asp"]  # dles (ts')
_yiwn = ARM["yiwn"]    # dles (u-component)
_p_asp = ARM["p_asp"]  # dles (p')
_b   = ARM["b"]        # dles (WA: b) — note: EA would call this "p"

# Infinitive endings
INF_EL = _ye + _l      # dles = el (Class I)
INF_AL = _a + _l       # dles = al (Class II)
INF_IL = _i + _l       # dles = il (some verbs)
INF_UL = _vo + _yiwn + _l  # dles = ul (rare)

# Western Armenian present tense preverbal particle: կdelays (gə)
PRESENT_PARTICLE = _g + _schwa  # dles = gə

# Western Armenian future preverbal particle: delays (bidi)
FUTURE_PARTICLE = _b + _i + _d + _i  # dles = bidi

# Western Armenian negative particle: dles (ch'ə)
NEGATIVE_PARTICLE = _ch_asp + _schwa  # dles = ch'ə

# Person labels
PERSONS = ["1sg", "2sg", "3sg", "1pl", "2pl", "3pl"]
PERSON_LABELS = {
    "1sg": "I",
    "2sg": "you (sg)",
    "3sg": "he/she/it",
    "1pl": "we",
    "2pl": "you (pl)",
    "3pl": "they",
}

TENSES = [
    "infinitive",
    "subjunctive",
    "present",
    "future",
    "conditional",
    "past_aorist",
    "imperfect",
    "perfect",
    "pluperfect",
    "imperative",
    "past_participle",
    "present_participle",
]


# ─── Conjugation Patterns ────────────────────────────────────────────

# Person endings for the subjunctive / present stem (bles-class)
# These are appended to: verb_root + thematic_vowel
SUBJ_ENDINGS_E_CLASS = {
    "1sg": _ye + _m,              # dles = em
    "2sg": _ye + _s,              # dles = es
    "3sg": _e,                    # dles = ē
    "1pl": _ye + _n + _k_asp,    # dles = enk'
    "2pl": _ye + _k_asp,         # dles = ek'
    "3pl": _ye + _n,             # dles = en
}

SUBJ_ENDINGS_A_CLASS = {
    "1sg": _a + _m,              # dles = am
    "2sg": _a + _s,              # dles = as
    "3sg": _a,                   # dles = a (or ay)
    "1pl": _a + _n + _k_asp,    # dles = ank'
    "2pl": _a + _k_asp,         # dles = ak'
    "3pl": _a + _n,             # dles = an
}

# Aorist (simple past) endings for bles-class
AORIST_ENDINGS_E_CLASS = {
    "1sg": _ye + _c_asp + _i,              # dles = ec'i
    "2sg": _ye + _c_asp + _i + _r,         # dles = ec'ir
    "3sg": _ye + _c_asp,                   # dles = ec'
    "1pl": _ye + _c_asp + _i + _n + _k_asp,# dles = ec'ink'
    "2pl": _ye + _c_asp + _i + _k_asp,     # dles = ec'ik'
    "3pl": _ye + _c_asp + _i + _n,         # dles = ec'in
}

AORIST_ENDINGS_A_CLASS = {
    "1sg": _a + _c_asp + _i,              # dles = ac'i
    "2sg": _a + _c_asp + _i + _r,         # dles = ac'ir
    "3sg": _a + _c_asp,                   # dles = ac'
    "1pl": _a + _c_asp + _i + _n + _k_asp,# dles = ac'ink'
    "2pl": _a + _c_asp + _i + _k_asp,     # dles = ac'ik'
    "3pl": _a + _c_asp + _i + _n,         # dles = ac'in
}

# Imperfect endings (based on subjunctive + imperfect marker)
IMPERFECT_ENDINGS_E_CLASS = {
    "1sg": _ye + _i,              # dles = ei
    "2sg": _ye + _i + _r,        # dles = eir
    "3sg": _e + _r,              # dles = ēr
    "1pl": _ye + _i + _n + _k_asp,# dles = eink'
    "2pl": _ye + _i + _k_asp,    # dles = eik'
    "3pl": _ye + _i + _n,        # dles = ein
}

IMPERFECT_ENDINGS_A_CLASS = {
    "1sg": _a + _i,              # dles = ai
    "2sg": _a + _i + _r,        # dles = air
    "3sg": _a + _r,             # dles = ar
    "1pl": _a + _i + _n + _k_asp,# dles = aink'
    "2pl": _a + _i + _k_asp,    # dles = aik'
    "3pl": _a + _i + _n,        # dles = ain
}

# Conditional endings — in WA, formed with conditional particle կ (ka) + subjunctive
# Alternative: using a suffix pattern [-ի/-ար/-ե for singular/plural variations]
# Simple approach: just show the subjunctive form with conditional framing
CONDITIONAL_ENDINGS_E_CLASS = {
    "1sg": _ye + _m,              # dles = em (would be: կ em)
    "2sg": _ye + _s,              # dles = es (would be: կ es)
    "3sg": _e,                    # dles = ē (would be: կ ē)
    "1pl": _ye + _n + _k_asp,    # dles = enk' (would be: կ enk')
    "2pl": _ye + _k_asp,         # dles = ek' (would be: կ ek')
    "3pl": _ye + _n,             # dles = en (would be: կ en)
}

CONDITIONAL_ENDINGS_A_CLASS = {
    "1sg": _a + _m,              # dles = am (would be: կ am)
    "2sg": _a + _s,              # dles = as (would be: կ as)
    "3sg": _a,                   # dles = a (would be: կ a)
    "1pl": _a + _n + _k_asp,    # dles = ank' (would be: կ ank')
    "2pl": _a + _k_asp,         # dles = ak' (would be: կ ak')
    "3pl": _a + _n,             # dles = an (would be: կ an)
}

# Western Armenian conditional particle
CONDITIONAL_PARTICLE = _k + _a  # dles = ka


VERB_CLASSES = {
    "e_class": {
        "label": f"{_ye}{_l}-conjugation",
        "infinitive_suffix": INF_EL,
        "subjunctive": SUBJ_ENDINGS_E_CLASS,
        "conditional": CONDITIONAL_ENDINGS_E_CLASS,
        "aorist": AORIST_ENDINGS_E_CLASS,
        "imperfect": IMPERFECT_ENDINGS_E_CLASS,
        "imperative_sg": _e,               # dles (ē) — 2sg imperative
        "imperative_pl": _ye + _k_asp,     # dles (ek') — 2pl imperative
        "past_participle": _ye + _l,       # dles (el) — same as infinitive in WA
        "present_participle": _vo + _yiwn + ARM["gh"],  # dles (ough — a rough approximation)
    },
    "a_class": {
        "label": f"{_a}{_l}-conjugation",
        "infinitive_suffix": INF_AL,
        "subjunctive": SUBJ_ENDINGS_A_CLASS,
        "conditional": CONDITIONAL_ENDINGS_A_CLASS,
        "aorist": AORIST_ENDINGS_A_CLASS,
        "imperfect": IMPERFECT_ENDINGS_A_CLASS,
        "imperative_sg": _a,               # dles (a) — 2sg imperative
        "imperative_pl": _a + _k_asp,      # dles (ak') — 2pl imperative
        "past_participle": _a + _l,        # dles (al) — same as infinitive in WA
        "present_participle": _a + _c_asp + _vo + _yiwn + ARM["gh"],
    },
}


# ─── Conjugation Result ─────────────────────────────────────────────

@dataclass
class VerbConjugation:
    """All conjugated forms of an Armenian verb."""
    infinitive: str
    root: str
    verb_class: str
    translation: str = ""

    # Tense → person → form
    present: dict[str, str] = field(default_factory=dict)
    past_aorist: dict[str, str] = field(default_factory=dict)
    imperfect: dict[str, str] = field(default_factory=dict)
    future: dict[str, str] = field(default_factory=dict)
    conditional: dict[str, str] = field(default_factory=dict)
    subjunctive: dict[str, str] = field(default_factory=dict)

    # Perfect tenses (compound: past_participle + auxiliary "to be")
    perfect: dict[str, str] = field(default_factory=dict)    # have done (past participle + present of "to be")
    pluperfect: dict[str, str] = field(default_factory=dict) # had done (past participle + past of "to be")

    # Imperative (2nd person only)
    imperative_sg: str = ""
    imperative_pl: str = ""

    # Participles
    past_participle: str = ""
    present_participle: str = ""

    def as_dict(self) -> dict:
        """Return all forms as a nested dictionary."""
        return {
            "infinitive": self.infinitive,
            "root": self.root,
            "verb_class": self.verb_class,
            "translation": self.translation,
            "present": dict(self.present),
            "past_aorist": dict(self.past_aorist),
            "imperfect": dict(self.imperfect),
            "future": dict(self.future),
            "conditional": dict(self.conditional),
            "subjunctive": dict(self.subjunctive),
            "perfect": dict(self.perfect),
            "pluperfect": dict(self.pluperfect),
            "imperative_sg": self.imperative_sg,
            "imperative_pl": self.imperative_pl,
            "past_participle": self.past_participle,
            "present_participle": self.present_participle,
        }

    def summary_table(self) -> str:
        """Return a formatted text table of all conjugated forms."""
        lines = [
            f"Conjugation of: {self.infinitive}  ({self.translation})",
            f"Root: {self.root}  |  Class: {self.verb_class}",
            "",
        ]

        for tense_name, forms in [
            ("Present", self.present),
            ("Past (Aorist)", self.past_aorist),
            ("Imperfect", self.imperfect),
            ("Future", self.future),
            ("Conditional", self.conditional),
            ("Subjunctive", self.subjunctive),
            ("Perfect", self.perfect),
            ("Pluperfect", self.pluperfect),
        ]:
            lines.append(f"  {tense_name}:")
            for person in PERSONS:
                if person in forms:
                    label = PERSON_LABELS[person]
                    lines.append(f"    {label:<15} {forms[person]}")
            lines.append("")

        lines.append(f"  Imperative (2sg): {self.imperative_sg}")
        lines.append(f"  Imperative (2pl): {self.imperative_pl}")
        lines.append(f"  Past Participle:  {self.past_participle}")
        lines.append(f"  Pres. Participle: {self.present_participle}")
        return "\n".join(lines)


# ─── Conjugation Engine ──────────────────────────────────────────────

def _extract_root(infinitive: str, verb_class: str) -> str:
    """Extract the verb root from the infinitive by removing the class suffix."""
    cls = VERB_CLASSES[verb_class]
    suffix = cls["infinitive_suffix"]
    if infinitive.endswith(suffix):
        return infinitive[:-len(suffix)]
    # Fallback: try stripping last 2 characters (common infinitive ending length)
    return infinitive[:-2] if len(infinitive) > 2 else infinitive


def conjugate_verb(
    infinitive: str,
    verb_class: str = "e_class",
    translation: str = "",
    root_override: Optional[str] = None,
) -> VerbConjugation:
    """Generate all conjugated forms for a Western Armenian verb.

    Args:
        infinitive: The infinitive form (dictionary form, ending in -dles or -dles).
        verb_class: Key into VERB_CLASSES (default: "e_class").
        translation: English translation for display.
        root_override: Override automatic root extraction for irregular verbs.

    Returns:
        VerbConjugation with all forms populated.
    """
    if verb_class not in VERB_CLASSES:
        raise ValueError(
            f"Unknown verb class '{verb_class}'. "
            f"Available: {list(VERB_CLASSES.keys())}"
        )

    cls = VERB_CLASSES[verb_class]
    root = root_override if root_override else _extract_root(infinitive, verb_class)

    result = VerbConjugation(
        infinitive=infinitive,
        root=root,
        verb_class=verb_class,
        translation=translation,
    )

    # ── Subjunctive (base conjugation) ──
    for person, ending in cls["subjunctive"].items():
        result.subjunctive[person] = root + ending

    # ── Present Indicative = preverbal particle + subjunctive ──
    for person, subj_form in result.subjunctive.items():
        result.present[person] = PRESENT_PARTICLE + " " + subj_form

    # ── Conditional = conditional particle + subjunctive ──
    for person, cond_form in cls["conditional"].items():
        result.conditional[person] = CONDITIONAL_PARTICLE + " " + root + cond_form

    # ── Past / Aorist ──
    for person, ending in cls["aorist"].items():
        result.past_aorist[person] = root + ending

    # ── Imperfect ──
    for person, ending in cls["imperfect"].items():
        result.imperfect[person] = root + ending

    # ── Future = future particle + subjunctive ──
    for person, subj_form in result.subjunctive.items():
        result.future[person] = FUTURE_PARTICLE + " " + subj_form

    # ── Perfect (compound: past_participle + present of "to be") ──
    # NOTE: Perfect forms combine the past participle with present tense of auxiliary "to be".
    # We provide the base construction; full forms require "to be" auxiliaries.
    # Example: past_participle + ém/es/e... (from "to be")
    for person in PERSONS:
        # Placeholder note: in real usage, conjugate_verb("ել") separately for "to be"
        result.perfect[person] = f"{result.past_participle} + [auxiliary: {person}]"

    # ── Pluperfect (compound: past_participle + past of "to be") ──
    # Similar to perfect but with past forms of "to be"
    # Example: past_participle + (ի)ր/ութ... (from past of "to be")
    for person in PERSONS:
        # Placeholder note: in real usage, use past_aorist or imperfect of "to be"
        result.pluperfect[person] = f"{result.past_participle} + [was/{person}]"

    # ── Imperative ──
    result.imperative_sg = root + cls["imperative_sg"]
    result.imperative_pl = root + cls["imperative_pl"]

    # ── Participles ──
    result.past_participle = root + cls["past_participle"]
    result.present_participle = root + cls["present_participle"]

    # ── Apply irregular overrides (if any) ──
    overrides = get_irregular_overrides(infinitive)
    if overrides is not None:
        if "present" in overrides:
            result.present.update(overrides["present"])
        if "conditional" in overrides:
            result.conditional.update(overrides["conditional"])
        if "past_aorist" in overrides:
            result.past_aorist.update(overrides["past_aorist"])
        if "imperfect" in overrides:
            result.imperfect.update(overrides["imperfect"])
        if "future" in overrides:
            result.future.update(overrides["future"])
        if "subjunctive" in overrides:
            result.subjunctive.update(overrides["subjunctive"])
        if "perfect" in overrides:
            result.perfect.update(overrides["perfect"])
        if "pluperfect" in overrides:
            result.pluperfect.update(overrides["pluperfect"])
        if "imperative_sg" in overrides:
            result.imperative_sg = overrides["imperative_sg"]
        if "imperative_pl" in overrides:
            result.imperative_pl = overrides["imperative_pl"]
        if "past_participle" in overrides:
            result.past_participle = overrides["past_participle"]

    return result
