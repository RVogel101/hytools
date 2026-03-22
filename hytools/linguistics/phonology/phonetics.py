"""
Armenian-to-English phonetic mapping and difficulty scoring.

Maps WESTERN ARMENIAN letters and digraphs to IPA and English approximations,
providing pronunciation guides and English-speaker difficulty scores.

NOTE: This module is specifically for WESTERN ARMENIAN phonetics, not Eastern Armenian.
Western Armenian has different pronunciations for several letters (e.g., ղ, ծ, ռ).
"""

# Mapping of WESTERN ARMENIAN letters to IPA and closest English approximations
ARMENIAN_PHONEMES = {
    # Vowels (WESTERN ARMENIAN)
    'ա': {'ipa': 'ɑ', 'english': 'ah', 'word': 'father', 'difficulty': 1},  # vowel
    'ե': {'ipa': 'ɛ~jɛ', 'english': 'e/ye', 'word': 'bed (or yes at word start)', 'difficulty': 1},  # vowel: e in middle, ye at start
    'է': {'ipa': 'ɛ', 'english': 'eh', 'word': 'bed', 'difficulty': 1},  # vowel
    'ը': {'ipa': 'ə', 'english': 'uh', 'word': 'about (schwa)', 'difficulty': 1},  # vowel: schwa
    'ի': {'ipa': 'i', 'english': 'ee', 'word': 'fleece', 'difficulty': 1},  # vowel
    'ո': {'ipa': 'v~ɔ', 'english': 'v/o', 'word': 'von/lot (v before consonants)', 'difficulty': 2},  # Western: v before consonants (ոչ=voch, որ=vor), o vowel otherwise
    'օ': {'ipa': 'o', 'english': 'o', 'word': 'go', 'difficulty': 1},  # vowel
    
    # Single consonants (WESTERN ARMENIAN)
    'բ': {'ipa': 'p', 'english': 'p', 'word': 'pat (unaspirated)', 'difficulty': 1},  # Western: p (not b)
    'գ': {'ipa': 'k', 'english': 'k', 'word': 'kit', 'difficulty': 1},  # Western: k (not g)
    'դ': {'ipa': 't', 'english': 't', 'word': 'top (unaspirated)', 'difficulty': 1},  # Western: t (not d)
    'զ': {'ipa': 'z', 'english': 'z', 'word': 'zoo', 'difficulty': 1},
    'թ': {'ipa': 't', 'english': 't', 'word': 'top', 'difficulty': 1},  # Western: regular t (not th)
    'ժ': {'ipa': 'ʒ', 'english': 'zh', 'word': 'measure', 'difficulty': 2},
    'լ': {'ipa': 'l', 'english': 'l', 'word': 'lot', 'difficulty': 1},
    'խ': {'ipa': 'x', 'english': 'kh', 'word': 'German Bach (guttural)', 'difficulty': 4},  # Guttural
    'ծ': {'ipa': 'dz', 'english': 'dz', 'word': 'adze', 'difficulty': 2},  # Western: voiced dz
    'կ': {'ipa': 'g', 'english': 'g', 'word': 'go', 'difficulty': 1},  # Western: g (not k)
    'հ': {'ipa': 'h', 'english': 'h', 'word': 'hat', 'difficulty': 1},
    'ձ': {'ipa': 'ts', 'english': 'ts', 'word': 'cats', 'difficulty': 2},  # Western: ts (EA: dz)
    'ղ': {'ipa': 'ɣ', 'english': 'voiced gh', 'word': 'guttural voiced (no English)', 'difficulty': 4},  # Western: voiced velar fricative
    'ճ': {'ipa': 'dʒ', 'english': 'j', 'word': 'job', 'difficulty': 1},  # Western: j (not ch)
    'մ': {'ipa': 'm', 'english': 'm', 'word': 'man', 'difficulty': 1},
    'յ': {'ipa': 'j~h', 'english': 'y/h', 'word': 'yes (middle) / hat (start)', 'difficulty': 1},  # Western: y in middle of words, h at beginning
    'ն': {'ipa': 'n', 'english': 'n', 'word': 'no', 'difficulty': 1},
    'շ': {'ipa': 'ʃ', 'english': 'sh', 'word': 'shop', 'difficulty': 1},
    'չ': {'ipa': 'tʃ', 'english': 'ch', 'word': 'chop', 'difficulty': 1},
    'պ': {'ipa': 'b', 'english': 'b', 'word': 'bat', 'difficulty': 1},  # Western: b (not p)
    'ջ': {'ipa': 'tʃ', 'english': 'ch', 'word': 'chop', 'difficulty': 1},  # Western: ch (not j)
    'ռ': {'ipa': 'r', 'english': 'r (trilled)', 'word': 'Spanish r/Italian r (rolled)', 'difficulty': 3},  # Western: trilled r (not English tap)
    'ս': {'ipa': 's', 'english': 's', 'word': 'sun', 'difficulty': 1},
    'տ': {'ipa': 'd', 'english': 'd', 'word': 'dog (unaspirated)', 'difficulty': 1},  # Western: d (not t)
    'ր': {'ipa': 'ɾ', 'english': 'r', 'word': 'better (flap)', 'difficulty': 2},  # Western: flapped r (closer to English)
    'ց': {'ipa': 'ts', 'english': 'ts', 'word': 'cats', 'difficulty': 2},  # Western: ts (sometimes dz)
    'ւ': {'ipa': 'v~u', 'english': 'v/oo', 'word': 'vet (between vowels) / goose (as diphthong)', 'difficulty': 1},  # Western: v between vowels, oo in diphthongs
    'փ': {'ipa': 'p', 'english': 'p', 'word': 'pat', 'difficulty': 1},
    'ք': {'ipa': 'k', 'english': 'k', 'word': 'kit', 'difficulty': 1},
    'ֆ': {'ipa': 'f', 'english': 'f', 'word': 'fun', 'difficulty': 1},
}

# Diphthongs and multi-letter combinations
# These are two-letter sequences that create single phonetic units
ARMENIAN_DIGRAPHS = {
    # Diphthongs (two-letter vowel combinations)
    'ու': {'ipa': 'u', 'english': 'oo', 'word': 'goose', 'difficulty': 1},  # ո + ւ = long oo sound
    'իւ': {'ipa': 'ju', 'english': 'yoo', 'word': 'you', 'difficulty': 1},  # ի + ւ = yoo sound
}


def is_vowel(letter):
    """Check if Armenian letter is a vowel."""
    vowels = {'ա', 'ե', 'ի', 'ո', 'օ', 'է'}
    return letter in vowels


def get_phoneme_info(letter):
    """Get IPA, English approximation, and difficulty for a single letter."""
    return ARMENIAN_PHONEMES.get(letter, {
        'ipa': '?',
        'english': '?',
        'word': 'unknown',
        'difficulty': 0
    })


def get_phonetic_transcription(armenian_word):
    """
    Convert Armenian word to phonetic transcription.
    Returns dictionary with IPA, English approximation, and difficulty score.
    """
    ipa_chars = []
    english_approx = []
    max_difficulty = 0
    difficult_letters = []
    
    for letter in armenian_word:
        info = get_phoneme_info(letter)
        ipa_chars.append(info.get('ipa', ''))
        english_approx.append(info.get('english', ''))
        
        diff = info.get('difficulty', 0)
        if diff > max_difficulty:
            max_difficulty = diff
        if diff >= 3:
            difficult_letters.append((letter, info.get('english', '?'), diff))
    
    return {
        'word': armenian_word,
        'ipa': ''.join(ipa_chars),
        'english_approx': ' '.join(english_approx),
        'max_phonetic_difficulty': max_difficulty,
        'difficult_phonemes': difficult_letters,  # List of (letter, english, difficulty) tuples
    }


def calculate_phonetic_difficulty(armenian_word):
    """
    Calculate how difficult the pronunciation is for English speakers (1-5 scale).
    Considers: number of difficult phonemes, letter count, digraphs.
    """
    info = get_phonetic_transcription(armenian_word)
    
    # Base difficulty from most difficult phoneme in the word
    base = info['max_phonetic_difficulty']
    
    # Add penalty for multiple difficult phonemes
    num_difficult = len(info['difficult_phonemes'])
    penalty = num_difficult * 0.3
    
    # Normalize to 1-5 scale
    final_difficulty = min(5.0, max(1.0, base + penalty))
    
    return round(final_difficulty, 2)


def get_pronunciation_guide(armenian_word):
    """
    Generate a simple pronunciation guide for English speakers.
    """
    info = get_phonetic_transcription(armenian_word)
    
    guide = {
        'armenian': armenian_word,
        'ipa': info['ipa'],
        'english_approx': info['english_approx'],
        'difficulty_score': calculate_phonetic_difficulty(armenian_word),
        'tips': []
    }
    
    # Generate tips for difficult letters
    if info['difficult_phonemes']:
        tip_list = []
        for letter, english, diff in info['difficult_phonemes']:
            if diff == 4:
                phoneme_info = get_phoneme_info(letter)
                tip_list.append(f"  {letter} [{phoneme_info['english']}] - very difficult, like {phoneme_info['word']}")
            elif diff == 3:
                phoneme_info = get_phoneme_info(letter)
                tip_list.append(f"  {letter} [{phoneme_info['english']}] - tricky, like {phoneme_info['word']}")
        if tip_list:
            guide['tips'] = tip_list
    
    return guide


# ============================================================================
# LETTER NAME & SOUND DATA (merged from ipa_mappings.py for consolidation)
# ============================================================================
# These dictionaries provide alternative representations of Armenian letter
# phonetics used in specific contexts (letter naming, IPA transcription).
# Armenian letter naming and IPA transcription mappings

# Armenian-script spelling of each letter's traditional name
LETTER_NAME_ARMENIAN = {
    "ա": "այբ",      # ayp
    "բ": "բեն",      # pen
    "գ": "գիմ",      # kim
    "դ": "դա",       # ta
    "ե": "եծ",       # yech
    "զ": "զա",       # za
    "է": "է",        # eh
    "ը": "ըթ",       # et
    "թ": "թո",      # to
    "ժ": "ժե",       # zhe
    "ի": "ինի",      # ini
    "լ": "լյուն",    # lyun
    "խ": "խե",      # khe
    "ծ": "ծա",       # dza
    "կ": "կեն",      # gen
    "հ": "հո",       # ho
    "ձ": "ծա",       # tsa
    "ղ": "ղաղ",      # ghat
    "ճ": "ճե",       # je
    "մ": "մեն",      # men
    "յ": "յի",       # yi
    "ն": "նու",      # nu
    "շ": "շա",       # sha
    "ո": "ո",        # vo
    "չ": "չա",       # cha
    "պ": "բե",       # be
    "ջ": "չե",       # che
    "ռ": "ռա",       # rra
    "ս": "սե",       # se
    "վ": "վեւ",      # vev
    "տ": "տյուն",    # dyun
    "ր": "րե",       # re
    "ց": "ցո",       # tso
    "ւ": "հյուն",    # yiwn
    "փ": "փյուր",    # pyur
    "ք": "քե",       # ke
    "օ": "օ",        # o
    "ֆ": "ֆե",       # fe
}

# Spoken names of Armenian letters (grapheme names), in detailed IPA
# Used for pronunciation of individual letter names (e.g., "What letter is this?")
LETTER_NAME_IPA = {
    "ա": "ɑjpʰ",
    "բ": "pʰɛn",
    "գ": "kʰim",
    "դ": "tʰɑ",
    "ե": "jɛtʃʰ",
    "զ": "zɑ",
    "է": "ɛ",
    "ը": "ətʰ",
    "թ": "tʰɔ",
    "ժ": "ʒɛ",
    "ի": "ini",
    "լ": "lʏn",
    "խ": "χɛ",
    "ծ": "dzɑ",
    "կ": "ɡɛn",
    "հ": "ho",
    "ձ": "tsʰɑ",
    "ղ": "ʁɑd",
    "ճ": "dʒɛ",
    "մ": "mɛn",
    "յ": "hi",
    "ն": "nu",
    "շ": "ʃɑ",
    "ո": "ʋɔ",
    "չ": "tʃʰɑ",
    "պ": "bɛ",
    "ջ": "tʃʰɛ",
    "ռ": "ɾɑ",
    "ս": "sɛ",
    "վ": "vɛv",
    "տ": "dʏn",
    "ր": "ɾɛ",
    "ց": "tsʰɔ",
    "ւ": "hʏn",
    "փ": "pʰʏɾ",
    "ք": "kʰɛ",
    "օ": "o",
    "ֆ": "fɛ",
}

# Base letter sounds (phoneme values) in isolated context, in IPA
# Use these for consonant/vowel sounds (not letter names)
# Context-sensitive alternates (word-initial, diphthongs) stored separately below
LETTER_SOUND_IPA = {
    "ա": "ɑ",
    "բ": "pʰ",
    "գ": "kʰ",
    "դ": "tʰ",
    "ե": "ɛ",
    "զ": "z",
    "է": "ɛ",
    "ը": "ə",
    "թ": "tʰ",
    "ժ": "ʒ",
    "ի": "i",
    "լ": "l",
    "խ": "χ",
    "ծ": "dz",
    "կ": "ɡ",
    "հ": "h",
    "ձ": "tsʰ",
    "ղ": "ʁ",
    "ճ": "dʒ",
    "մ": "m",
    "յ": "h",
    "ն": "n",
    "շ": "ʃ",
    "ո": "ɔ",
    "չ": "tʃʰ",
    "պ": "b",
    "ջ": "tʃʰ",
    "ռ": "ɾ",
    "ս": "s",
    "վ": "v",
    "տ": "d",
    "ր": "ɾ",
    "ց": "tsʰ",
    "ւ": "v",
    "փ": "pʰ",
    "ք": "kʰ",
    "օ": "o",
    "ֆ": "f",
}

# Word-initial alternates (letters that sound different at word start)
LETTER_SOUND_IPA_WORD_INITIAL = {
    "ե": "jɛ",      # ե at word start → ye (jɛ)
    "ո": "ʋɔ",      # ո at word start → vo (ʋɔ)
}

# Multi-character diphthong sounds (vowel + vowel combinations)
DIPHTHONG_SOUND_IPA = {
    "ու": "u",      # ո + ւ = long oo (goose)
    "իւ": "ju",     # ի + ւ = yoo (you)
    "եա": "ɛɑ",
    "ոյ": "uj",
    "այ": "aj",
}

# Ligatures (special grapheme combinations)
LIGATURE_SOUND_IPA = {
    "և": "jɛv",
}


if __name__ == '__main__':
    # Test examples
    test_words = ['ուր', 'ղ', 'ռ', 'պետք', 'մեր']
    for word in test_words:
        guide = get_pronunciation_guide(word)
        print(f"\n{guide['armenian']}")
        print(f"  IPA: {guide['ipa']}")
        print(f"  English: {guide['english_approx']}")
        print(f"  Difficulty: {guide['difficulty_score']}/5")
        if guide['tips']:
            print("  Tips:")
            for tip in guide['tips']:
                print(tip)
