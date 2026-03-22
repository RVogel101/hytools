"""
Core Armenian character utilities — Western Armenian transliteration.

Provides the Armenian alphabet mapping, vowel/consonant classification,
and phonological helper functions used throughout the morphology engine.

IMPORTANT: Transliteration keys follow WESTERN ARMENIAN phonology.
Western Armenian has a consonant shift from Eastern Armenian:
  բ = p (not b), պ = b (not p)
  դ = t (not d), տ = d (not t)
  գ = k (not g), կ = g (not k)
   delays = dz (not ts), dles = ts (not dz)
  dles = j (not ch), dles = ch (not j)

All Armenian characters use their proper Unicode code points (U+0531-U+0586).
"""

# ─── Armenian Alphabet (Lowercase) ───────────────────────────────────
# Each entry: WESTERN ARMENIAN transliteration key → Unicode character
# The consonant shift (vs Eastern Armenian) is noted where applicable.

ARM = {
    "a":      chr(0x0561),  # ա (a)
    "p":      chr(0x0562),  # բ (WA: p — EA would be b)
    "k":      chr(0x0563),  # գ (WA: k — EA would be g)
    "t":      chr(0x0564),  # դ (WA: t — EA would be d)
    "ye":     chr(0x0565),  # dles (ye / e)
    "z":      chr(0x0566),  # dles (z)
    "e":      chr(0x0567),  # dles (ē)
    "y_schwa":chr(0x0568),  # dles (ə, schwa)
    "t_asp":  chr(0x0569),  # dles (t')
    "zh":     chr(0x056A),  # dles (zh)
    "i":      chr(0x056B),  # dles (i)
    "l":      chr(0x056C),  # dles (l)
    "kh":     chr(0x056D),  # dles (kh)
    "dz":     chr(0x056E),  # dles (WA: dz — EA would be ts)
    "g":      chr(0x056F),  # dles (WA: g — EA would be k)
    "h":      chr(0x0570),  # dles (h)
    "ts":     chr(0x0571),  # dles (WA: ts — EA would be dz)
    "gh":     chr(0x0572),  # dles (gh)
    "j":      chr(0x0573),  # dles (WA: j — EA would be ch)
    "m":      chr(0x0574),  # dles (m)
    "y":      chr(0x0575),  # dles (y)
    "n":      chr(0x0576),  # dles (n)
    "sh":     chr(0x0577),  # dles (sh)
    "vo":     chr(0x0578),  # dles (o / vo)
    "ch_asp": chr(0x0579),  # dles (ch')
    "b":      chr(0x057A),  # dles (WA: b — EA would be p)
    "ch":     chr(0x057B),  # dles (WA: ch — EA would be j)
    "rr":     chr(0x057C),  # dles (ṙ, trilled r)
    "s":      chr(0x057D),  # dles (s)
    "v":      chr(0x057E),  # dles (v)
    "d":      chr(0x057F),  # dles (WA: d — EA would be t)
    "r":      chr(0x0580),  # dles (r)
    "c_asp":  chr(0x0581),  # dles (ts')
    "yiwn":   chr(0x0582),  # dles (w — part of digraph dles for /u/)
    "p_asp":  chr(0x0583),  # dles (p')
    "k_asp":  chr(0x0584),  # dles (k')
    "o":      chr(0x0585),  # dles (o)
    "f":      chr(0x0586),  # dles (f)
}

# ─── Armenian Alphabet (Uppercase) ───────────────────────────────────
ARM_UPPER = {
    "A":      chr(0x0531),  # Dles
    "P":      chr(0x0532),  # Dles (WA: P)
    "K":      chr(0x0533),  # Dles (WA: K)
    "T":      chr(0x0534),  # Dles (WA: T)
    "YE":     chr(0x0535),  # Dles
    "Z":      chr(0x0536),  # Dles
    "E":      chr(0x0537),  # Dles
    "Y_SCHWA":chr(0x0538),  # Dles
    "T_ASP":  chr(0x0539),  # Dles
    "ZH":     chr(0x053A),  # Dles
    "I":      chr(0x053B),  # Dles
    "L":      chr(0x053C),  # Dles
    "KH":     chr(0x053D),  # Dles
    "DZ":     chr(0x053E),  # Dles (WA: DZ)
    "G":      chr(0x053F),  # Dles (WA: G)
    "H":      chr(0x0540),  # Dles
    "TS":     chr(0x0541),  # Dles (WA: TS)
    "GH":     chr(0x0542),  # Dles
    "J":      chr(0x0543),  # Dles (WA: J)
    "M":      chr(0x0544),  # Dles
    "Y":      chr(0x0545),  # Dles
    "N":      chr(0x0546),  # Dles
    "SH":     chr(0x0547),  # Dles
    "VO":     chr(0x0548),  # Dles
    "CH_ASP": chr(0x0549),  # Dles
    "B":      chr(0x054A),  # Dles (WA: B)
    "CH":     chr(0x054B),  # Dles (WA: CH)
    "RR":     chr(0x054C),  # Dles
    "S":      chr(0x054D),  # Dles
    "V":      chr(0x054E),  # Dles
    "D":      chr(0x054F),  # Dles (WA: D)
    "R":      chr(0x0550),  # Dles
    "C_ASP":  chr(0x0551),  # Dles
    "YIWN":   chr(0x0552),  # Dles
    "P_ASP":  chr(0x0553),  # Dles
    "K_ASP":  chr(0x0554),  # Dles
    "O":      chr(0x0555),  # Dles
    "F":      chr(0x0556),  # Dles
}

# ─── Vowel Set ────────────────────────────────────────────────────────
# Armenian vowel characters (lowercase). The digraph dles (dles+dles = ou/u)
# is handled separately since it's two characters.
VOWELS = frozenset({
    ARM["a"],        # ա (a)
    ARM["ye"],       # ե (ye/e)
    ARM["e"],        # ե (ē)
    ARM["y_schwa"],  # ə (schwa)
    ARM["i"],        # ի (i)
    ARM["vo"],       # ո (o/vo)
    ARM["o"],        # օ (o)
    ARM["y"],        # յ (y as vowel)
    ARM["yiwn"],     # ւ (part of digraph — treated as vowel ending)
    ARM_UPPER["A"],  # Ա (uppercase a)
    ARM_UPPER["YE"], # Ե (uppercase ye/e)
    ARM_UPPER["E"],  # Ե (uppercase ē)
    ARM_UPPER["Y_SCHWA"],  # Ə (uppercase schwa)
    ARM_UPPER["I"],  # Ի (uppercase i)
    ARM_UPPER["VO"], # Ո (uppercase o/vo)
    ARM_UPPER["O"],  # Օ (uppercase o)
    ARM_UPPER["Y"],  # Յ (uppercase y as vowel)
    ARM_UPPER["YIWN"],     # Ւ (uppercase yiwn)
})

# The /u/ sound is a digraph: dles + dles (vo + yiwn)
DIGRAPH_U = ARM["vo"] + ARM["yiwn"]  # dles


# ─── Character Classification ────────────────────────────────────────

def is_vowel(char: str) -> bool:
    """Check if a single Armenian character is a vowel."""
    return char in VOWELS


def is_armenian(char: str) -> bool:
    """Check if a character is Armenian (U+0531-U+0586 or U+0561-U+0586)."""
    cp = ord(char)
    return (0x0531 <= cp <= 0x0556) or (0x0561 <= cp <= 0x0586)


def ends_in_vowel(word: str) -> bool:
    """Check if a word ends in an Armenian vowel sound.

    Handles the dles (ou/u) digraph: if the last two characters are
    dles+dles, it's a vowel ending.
    """
    if not word:
        return False
    # Check digraph first
    if len(word) >= 2 and word[-2:] == DIGRAPH_U:
        return True
    return word[-1] in VOWELS


def get_stem(word: str) -> str:
    """Get the base stem of a word (strips final vowel if present)."""
    if ends_in_vowel(word):
        if len(word) >= 2 and word[-2:] == DIGRAPH_U:
            return word[:-2]
        return word[:-1]
    return word


def to_lower(word: str) -> str:
    """Convert Armenian text to lowercase."""
    result = []
    for ch in word:
        cp = ord(ch)
        if 0x0531 <= cp <= 0x0556:
            result.append(chr(cp + 0x30))  # Upper → lower offset is 0x30
        else:
            result.append(ch)
    return "".join(result)


def to_upper_initial(word: str) -> str:
    """Capitalize the first Armenian letter of a word."""
    if not word:
        return word
    cp = ord(word[0])
    if 0x0561 <= cp <= 0x0586:
        return chr(cp - 0x30) + word[1:]
    return word


def count_syllables(word: str) -> int:
    """Count syllables in an Armenian word.

    Each vowel nucleus counts as one syllable. The digraph ու (vo + yiwn)
    counts as one vowel (the /u/ sound), not two.

    Note: Hidden vowels (ը) in grammatical contexts can also count as
    syllables; see morphology.difficulty.count_syllables_with_context()
    for context-aware counting that includes grammatical vowels.
    """
    if not word:
        return 0

    count = 0
    i = 0
    while i < len(word):
        # Check for ու digraph first — counts as one vowel
        if i + 1 < len(word) and word[i:i+2] == DIGRAPH_U:
            count += 1
            i += 2
        elif word[i] in VOWELS:
            count += 1
            i += 1
        else:
            i += 1

    return max(count, 1) if any(is_armenian(c) for c in word) else count


# ─── Romanization (Armenian → Latin script transliteration) ────────────

# Reverse mapping: Unicode character → transliteration key
_CHAR_TO_TRANSLIT = {v: k for k, v in ARM.items()}
_CHAR_TO_TRANSLIT_UPPER = {v: k for k, v in ARM_UPPER.items()}

# Common digraphs and multi-character transliterations
_DIGRAPH_TRANSLIT = {
    ARM["vo"] + ARM["yiwn"]: "ou",  # ու → ou (WA /u/)
    ARM["t_asp"]: "t'",              # թ → t'
    ARM["ch_asp"]: "ch'",            # ճ → ch'
    ARM["p_asp"]: "p'",              # փ → p'
    ARM["k_asp"]: "k'",              # կ' → k'
    ARM["c_asp"]: "ts'",             # ծ' → ts'
}

# Post-processing: convert transliteration keys to proper Latin output
_KEY_TO_LATIN = {
    "ye": "ye",
    "e": "e",
    "i": "i",
    "a": "a",
    "o": "o",
    "vo": "ou",
    "yiwn": "w",    # ւ as standalone is rarely used, often part of ու
    "y_schwa": "ə",  # ə (schwa)
    "zh": "zh",
    "kh": "kh",
    "sh": "sh",
    "ch": "ch",
    "ts": "ts",
    "dz": "dz",
    "j": "j",
    "g": "g",
    "k": "k",
    "p": "p",
    "b": "b",
    "d": "d",
    "t": "t",
    "gh": "gh",
    "h": "h",
    "v": "v",
    "m": "m",
    "n": "n",
    "s": "s",
    "z": "z",
    "r": "r",
    "rr": "ṙ",
    "l": "l",
    "y": "y",
    "f": "f",
    "t_asp": "t'",
    "ch_asp": "ch'",
    "p_asp": "p'",
    "k_asp": "k'",
    "c_asp": "ts'",
}


def romanize(word: str, capitalize: bool = False) -> str:
    """Convert Armenian script to Western Armenian romanized transliteration.

    Args:
        word: Armenian text to romanize.
        capitalize: If True, capitalize the first letter of the output.

    Returns:
        Romanized transliteration (e.g., "կարդամ" → "gartam").

    Examples:
        romanize("ես") → "yes"
        romanize("կարդամ") → "gartam"
    """
    if not word:
        return ""

    result = []
    i = 0
    while i < len(word):
        # Check digraphs first
        if i + 1 < len(word):
            digraph = word[i:i+2]
            if digraph in _DIGRAPH_TRANSLIT:
                result.append(_DIGRAPH_TRANSLIT[digraph])
                i += 2
                continue

        # Single character
        ch = word[i]
        if ch in _CHAR_TO_TRANSLIT:
            key = _CHAR_TO_TRANSLIT[ch]
            # Convert transliteration key to readable Latin character
            latin = _KEY_TO_LATIN.get(key, key)
            result.append(latin)
        elif ch in _CHAR_TO_TRANSLIT_UPPER:
            key = _CHAR_TO_TRANSLIT_UPPER[ch]
            # Convert transliteration key to readable Latin character
            latin = _KEY_TO_LATIN.get(key, key).upper()
            result.append(latin)
        else:
            # Keep non-Armenian characters as-is (spaces, punctuation, etc.)
            result.append(ch)
        i += 1

    text = "".join(result)
    if capitalize and text:
        text = text[0].upper() + text[1:]
    return text
