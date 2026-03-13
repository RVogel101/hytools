"""
Western Armenian Alphabet - Complete Letter Information for Card Generation.

Provides comprehensive data for each Armenian letter including:
- Letter names (traditional Armenian alphabet names)
- Uppercase and lowercase forms
- IPA transcription (Western Armenian)
- English approximations
- Difficulty ratings
- Example words
- Vowel/consonant classification
- Diphthong information

This module integrates with phonetics.py for pronunciation data.
"""

from typing import Dict, List, Optional
from .phonetics import ARMENIAN_PHONEMES, ARMENIAN_DIGRAPHS


# ─── Armenian Letter Names ───────────────────────────────────────────
# Traditional names of Armenian letters (in Western Armenian pronunciation)

LETTER_NAMES = {
    'ա': 'ayp',
    'բ': 'pen',        # Western: p sound
    'գ': 'kim',        # Western: k sound
    'դ': 'ta',         # Western: t sound
    'ե': 'yech',
    'զ': 'za',
    'է': 'eh',
    'ը': 'ət',         # schwa
    'թ': 'tʰo',        # aspirated t
    'ժ': 'zheh',
    'ի': 'ini',
    'լ': 'lyun',
    'խ': 'kheh',
    'ծ': 'dza',        # Western: dz sound
    'կ': 'gen',        # Western: g sound
    'հ': 'ho',
    'ձ': 'dza',
    'ղ': 'ghat',
    'ճ': 'cheh',       # Western: j sound  
    'մ': 'men',
    'յ': 'yi',
    'ն': 'nu',
    'շ': 'sha',
    'ո': 'vo',
    'չ': 'chʰa',       # aspirated ch
    'պ': 'peh',        # Western: b sound
    'ջ': 'jheh',       # Western: ch sound
    'ռ': 'rra',        # trilled r
    'ս': 'seh',
    'վ': 'vev',
    'տ': 'tyun',       # Western: d sound
    'ր': 'reh',        # flapped r
    'ց': 'tsʰo',
    'ւ': 'yiwn',       # part of ու diphthong
    'փ': 'pʰyur',
    'ք': 'kʰeh',
    'օ': 'o',
    'ֆ': 'feh',
}


# ─── Complete Letter Information ─────────────────────────────────────

ARMENIAN_LETTERS: Dict[str, Dict] = {
    'ա': {
        'name': 'ayp',
        'uppercase': 'Ա',
        'lowercase': 'ա',
        'position': 1,
        'type': 'vowel',
        'ipa': 'ɑ',
        'english': 'ah',
        'difficulty': 1,
        'example_words': ['ալրկենական (garden)', 'առաւոտ (morning)', 'ասել (to say)'],
        'pronunciation_tip': 'Like "ah" in father',
        'audio_file_name': '01_ա_name.wav',
        'audio_file_sound': '01_ա_sound.wav',
    },
    'բ': {
        'name': 'pen',
        'uppercase': 'Բ',
        'lowercase': 'բ',
        'position': 2,
        'type': 'consonant',
        'ipa': 'p',
        'english': 'p',
        'difficulty': 1,
        'example_words': ['բարի (good)', 'բաժակ (cup)', 'բան (thing)'],
        'pronunciation_tip': 'Unaspirated "p" like in "spat", NOT "pat"',
        'western_note': 'WESTERN: sounds like P, not B (reversed from Eastern)',
    },
    'գ': {
        'name': 'kim',
        'uppercase': 'Գ',
        'lowercase': 'գ',
        'position': 3,
        'type': 'consonant',
        'ipa': 'k',
        'english': 'k',
        'difficulty': 1,
        'example_words': ['գիրք (book)', 'գարուն (spring)', 'գինի (wine)'],
        'pronunciation_tip': 'Unaspirated "k" like in "skin", NOT "kin"',
        'western_note': 'WESTERN: sounds like K, not G (reversed from Eastern)',
    },
    'դ': {
        'name': 'ta',
        'uppercase': 'Դ',
        'lowercase': 'դ',
        'position': 4,
        'type': 'consonant',
        'ipa': 't',
        'english': 't',
        'difficulty': 1,
        'example_words': ['դաս (lesson)', 'դուռ (door)', 'դպրոց (school)'],
        'pronunciation_tip': 'Unaspirated "t" like in "stop", NOT "top"',
        'western_note': 'WESTERN: sounds like T, not D (reversed from Eastern)',
    },
    'ե': {
        'name': 'yech',
        'uppercase': 'Ե',
        'lowercase': 'ե',
        'position': 5,
        'type': 'vowel',
        'ipa': 'ɛ~jɛ',
        'english': 'e/ye',
        'difficulty': 1,
        'example_words': ['երգ (song)', 'երեք (three)', 'ես (I)'],
        'pronunciation_tip': '"e" like "bed" in middle of words, "ye" like "yes" at word start',
    },
    'զ': {
        'name': 'za',
        'uppercase': 'Զ',
        'lowercase': 'զ',
        'position': 6,
        'type': 'consonant',
        'ipa': 'z',
        'english': 'z',
        'difficulty': 1,
        'example_words': ['զանգ (bell)', 'զարմանալ (to wonder)', 'զինուոր (soldier)'],
        'pronunciation_tip': 'Like "z" in "zoo"',
    },
    'է': {
        'name': 'eh',
        'uppercase': 'Է',
        'lowercase': 'է',
        'position': 7,
        'type': 'vowel',
        'ipa': 'ɛ',
        'english': 'eh',
        'difficulty': 1,
        'example_words': ['է (is)', 'էջ (page)', 'էն (that)'],
        'pronunciation_tip': 'Like "e" in "bed", always a vowel (no y-glide)',
    },
    'ը': {
        'name': 'ət',
        'uppercase': 'Ը',
        'lowercase': 'ը',
        'position': 8,
        'type': 'vowel',
        'ipa': 'ə',
        'english': 'uh',
        'difficulty': 2,
        'example_words': ['ընկեր (friend)', 'ընտանիք (family)', 'ըլլալ (to be)'],
        'pronunciation_tip': 'Schwa sound like "a" in "about" or "u" in "but"',
    },
    'թ': {
        'name': 'tʰo',
        'uppercase': 'Թ',
        'lowercase': 'թ',
        'position': 9,
        'type': 'consonant',
        'ipa': 't',
        'english': 't',
        'difficulty': 1,
        'example_words': ['թուղթ (paper)', 'թագաւոր (king)', 'թեյ (tea)'],
        'pronunciation_tip': 'Regular aspirated "t" like in "top"',
    },
    'ժ': {
        'name': 'zheh',
        'uppercase': 'Ժ',
        'lowercase': 'ժ',
        'position': 10,
        'type': 'consonant',
        'ipa': 'ʒ',
        'english': 'zh',
        'difficulty': 2,
        'example_words': ['ժամ (hour)', 'ժողովուրդ (people)', 'ժամանակ (time)'],
        'pronunciation_tip': 'Like "s" in "measure" or "z" in "azure"',
    },
    'ի': {
        'name': 'ini',
        'uppercase': 'Ի',
        'lowercase': 'ի',
        'position': 11,
        'type': 'vowel',
        'ipa': 'i',
        'english': 'ee',
        'difficulty': 1,
        'example_words': ['ինը (nine)', 'ի (in/at)', 'իմ (my)'],
        'pronunciation_tip': 'Like "ee" in "fleece" or "see"',
    },
    'լ': {
        'name': 'lyun',
        'uppercase': 'Լ',
        'lowercase': 'լ',
        'position': 12,
        'type': 'consonant',
        'ipa': 'l',
        'english': 'l',
        'difficulty': 1,
        'example_words': ['լաւ (good)', 'լեզու (language)', 'լիճ (lake)'],
        'pronunciation_tip': 'Like "l" in "lot"',
    },
    'խ': {
        'name': 'kheh',
        'uppercase': 'Խ',
        'lowercase': 'խ',
        'position': 13,
        'type': 'consonant',
        'ipa': 'x',
        'english': 'kh',
        'difficulty': 4,
        'example_words': ['խնձոր (apple)', 'խաղ (game)', 'խորն (deep)'],
        'pronunciation_tip': 'Guttural sound like German "ch" in "Bach" or Scottish "loch"',
    },
    'ծ': {
        'name': 'dza',
        'uppercase': 'Ծ',
        'lowercase': 'ծ',
        'position': 14,
        'type': 'consonant',
        'ipa': 'dz',
        'english': 'dz',
        'difficulty': 2,
        'example_words': ['ծառ (tree)', 'ծով (sea)', 'ծնող (parent)'],
        'pronunciation_tip': 'Like "dz" in "adze" or the end of "odds"',
        'western_note': 'WESTERN: voiced dz (Eastern has unvoiced ts here)',
    },
    'կ': {
        'name': 'gen',
        'uppercase': 'Կ',
        'lowercase': 'կ',
        'position': 15,
        'type': 'consonant',
        'ipa': 'g',
        'english': 'g',
        'difficulty': 1,
        'example_words': ['կին (woman)', 'կարմիր (red)', 'կեանք (life)'],
        'pronunciation_tip': 'Like "g" in "go"',
        'western_note': 'WESTERN: sounds like G, not K (reversed from Eastern)',
    },
    'հ': {
        'name': 'ho',
        'uppercase': 'Հ',
        'lowercase': 'հ',
        'position': 16,
        'type': 'consonant',
        'ipa': 'h',
        'english': 'h',
        'difficulty': 1,
        'example_words': ['հայ (Armenian)', 'հին (old)', 'հաց (bread)'],
        'pronunciation_tip': 'Like "h" in "hat"',
    },
    'ձ': {
        'name': 'dza',
        'uppercase': 'Ձ',
        'lowercase': 'ձ',
        'position': 17,
        'type': 'consonant',
        'ipa': 'dz',
        'english': 'dz',
        'difficulty': 2,
        'example_words': ['ձեռք (hand)', 'ձուկ (fish)', 'ձայն (voice)'],
        'pronunciation_tip': 'Like "dz" in "adze"',
    },
    'ղ': {
        'name': 'ghat',
        'uppercase': 'Ղ',
        'lowercase': 'ղ',
        'position': 18,
        'type': 'consonant',
        'ipa': 'ɣ',
        'english': 'gh',
        'difficulty': 4,
        'example_words': ['ղեկ (helm)', 'աղջիկ (girl)', 'ծաղիկ (flower)'],
        'pronunciation_tip': 'Voiced guttural, like gargling (no direct English equivalent)',
        'western_note': 'WESTERN: voiced velar fricative (very different from Eastern)',
    },
    'ճ': {
        'name': 'cheh',
        'uppercase': 'Ճ',
        'lowercase': 'ճ',
        'position': 19,
        'type': 'consonant',
        'ipa': 'dʒ',
        'english': 'j',
        'difficulty': 1,
        'example_words': ['ճանապարհ (road)', 'ճաշ (lunch)', 'ճիշդ (correct)'],
        'pronunciation_tip': 'Like "j" in "job" or "g" in "gem"',
        'western_note': 'WESTERN: sounds like J, not CH (reversed from Eastern)',
    },
    'մ': {
        'name': 'men',
        'uppercase': 'Մ',
        'lowercase': 'մ',
        'position': 20,
        'type': 'consonant',
        'ipa': 'm',
        'english': 'm',
        'difficulty': 1,
        'example_words': ['մայր (mother)', 'մարդ (person)', 'մեծ (big)'],
        'pronunciation_tip': 'Like "m" in "man"',
    },
    'յ': {
        'name': 'yi',
        'uppercase': 'Յ',
        'lowercase': 'յ',
        'position': 21,
        'type': 'consonant',
        'ipa': 'j~h',
        'english': 'y/h',
        'difficulty': 1,
        'example_words': ['յոյս (hope)', 'յետոյ (after)', 'յանկարծ (suddenly)'],
        'pronunciation_tip': 'Like "y" in "yes" in middle of words, "h" at word start',
        'western_note': 'WESTERN: h sound at word start (հ also has h sound)',
    },
    'ն': {
        'name': 'nu',
        'uppercase': 'Ն',
        'lowercase': 'ն',
        'position': 22,
        'type': 'consonant',
        'ipa': 'n',
        'english': 'n',
        'difficulty': 1,
        'example_words': ['նոր (new)', 'նամակ (letter)', 'նկար (picture)'],
        'pronunciation_tip': 'Like "n" in "no"',
    },
    'շ': {
        'name': 'sha',
        'uppercase': 'Շ',
        'lowercase': 'շ',
        'position': 23,
        'type': 'consonant',
        'ipa': 'ʃ',
        'english': 'sh',
        'difficulty': 1,
        'example_words': ['շուն (dog)', 'շատ (much/many)', 'շուկայ (market)'],
        'pronunciation_tip': 'Like "sh" in "shop"',
    },
    'ո': {
        'name': 'vo',
        'uppercase': 'Ո',
        'lowercase': 'ո',
        'position': 24,
        'type': 'mixed',  # Can be vowel or consonant depending on context
        'ipa': 'v~ɔ',
        'english': 'v/o',
        'difficulty': 2,
        'example_words': ['ոչ (no)', 'որ (which)', 'ով (who)'],
        'pronunciation_tip': '"v" before consonants (ոչ=voch), "o" as vowel otherwise',
        'western_note': 'Context-dependent: v before consonants, o vowel in other positions',
    },
    'չ': {
        'name': 'chʰa',
        'uppercase': 'Չ',
        'lowercase': 'չ',
        'position': 25,
        'type': 'consonant',
        'ipa': 'tʃ',
        'english': 'ch',
        'difficulty': 1,
        'example_words': ['չորս (four)', 'չէ (isn\'t)', 'չորեք (Wednesday)'],
        'pronunciation_tip': 'Like "ch" in "chop"',
    },
    'պ': {
        'name': 'peh',
        'uppercase': 'Պ',
        'lowercase': 'պ',
        'position': 26,
        'type': 'consonant',
        'ipa': 'b',
        'english': 'b',
        'difficulty': 1,
        'example_words': ['պապ (grandfather)', 'պատուհան (window)', 'պարտէզ (garden)'],
        'pronunciation_tip': 'Like "b" in "bat"',
        'western_note': 'WESTERN: sounds like B, not P (reversed from Eastern)',
    },
    'ջ': {
        'name': 'jheh',
        'uppercase': 'Ջ',
        'lowercase': 'ջ',
        'position': 27,
        'type': 'consonant',
        'ipa': 'tʃ',
        'english': 'ch',
        'difficulty': 1,
        'example_words': ['ջուր (water)', 'ջերմ (warm)', 'ջան (dear)'],
        'pronunciation_tip': 'Like "ch" in "chop"',
        'western_note': 'WESTERN: sounds like CH, not J (reversed from Eastern)',
    },
    'ռ': {
        'name': 'rra',
        'uppercase': 'Ռ',
        'lowercase': 'ռ',
        'position': 28,
        'type': 'consonant',
        'ipa': 'r',
        'english': 'r (trilled)',
        'difficulty': 3,
        'example_words': ['ռուսական (Russian)', 'առու (male)', 'առնել (to take)'],
        'pronunciation_tip': 'Trilled "r" like Spanish or Italian rolled "r"',
        'western_note': 'WESTERN: trilled/rolled r (different from Eastern tap)',
    },
    'ս': {
        'name': 'seh',
        'uppercase': 'Ս',
        'lowercase': 'ս',
        'position': 29,
        'type': 'consonant',
        'ipa': 's',
        'english': 's',
        'difficulty': 1,
        'example_words': ['սեր (love)', 'սար (mountain)', 'սպիտակ (white)'],
        'pronunciation_tip': 'Like "s" in "sun"',
    },
    'վ': {
        'name': 'vev',
        'uppercase': 'Վ',
        'lowercase': 'վ',
        'position': 30,
        'type': 'consonant',
        'ipa': 'v',
        'english': 'v',
        'difficulty': 1,
        'example_words': ['վաղը (tomorrow)', 'վեց (six)', 'վարժոիթիւն (practice)'],
        'pronunciation_tip': 'Like "v" in "vet"',
    },
    'տ': {
        'name': 'tyun',
        'uppercase': 'Տ',
        'lowercase': 'տ',
        'position': 31,
        'type': 'consonant',
        'ipa': 'd',
        'english': 'd',
        'difficulty': 1,
        'example_words': ['տուն (house)', 'տարի (year)', 'տեղ (place)'],
        'pronunciation_tip': 'Unaspirated "d" like in "dog"',
        'western_note': 'WESTERN: sounds like D, not T (reversed from Eastern)',
    },
    'ր': {
        'name': 'reh',
        'uppercase': 'Ր',
        'lowercase': 'ր',
        'position': 32,
        'type': 'consonant',
        'ipa': 'ɾ',
        'english': 'r',
        'difficulty': 2,
        'example_words': ['աշխարհ (world)', 'հարց (question)', 'որս (hunt)'],
        'pronunciation_tip': 'Flapped "r" like the "tt" in American "better"',
        'western_note': 'WESTERN: flapped r (closer to English than ռ)',
    },
    'ց': {
        'name': 'tsʰo',
        'uppercase': 'Ց',
        'lowercase': 'ց',
        'position': 33,
        'type': 'consonant',
        'ipa': 'ts',
        'english': 'ts',
        'difficulty': 2,
        'example_words': ['ցաւ (pain)', 'ցերեկ (day)', 'ցանց (fence)'],
        'pronunciation_tip': 'Like "ts" in "cats"',
    },
    'ւ': {
        'name': 'yiwn',
        'uppercase': 'Ւ',
        'lowercase': 'ւ',
        'position': 34,
        'type': 'semivowel',  # Not a vowel on its own, forms diphthongs
        'ipa': 'v~u',
        'english': 'v/oo',
        'difficulty': 1,
        'example_words': ['ու (and)', 'իւր (his/her own)', 'արու (male)'],
        'pronunciation_tip': '"v" between vowels, "oo" in diphthongs ու and իւ',
        'western_note': 'NOT a vowel alone - only in diphthongs ու (oo) and իւ (yoo)',
    },
    'փ': {
        'name': 'pʰyur',
        'uppercase': 'Փ',
        'lowercase': 'փ',
        'position': 35,
        'type': 'consonant',
        'ipa': 'p',
        'english': 'p',
        'difficulty': 1,
        'example_words': ['փող (money)', 'փոքր (small)', 'փորձ (attempt)'],
        'pronunciation_tip': 'Aspirated "p" like in "pat"',
    },
    'ք': {
        'name': 'kʰeh',
        'uppercase': 'Ք',
        'lowercase': 'ք',
        'position': 36,
        'type': 'consonant',
        'ipa': 'k',
        'english': 'k',
        'difficulty': 1,
        'example_words': ['քաղաք (city)', 'քոյր (sister)', 'քառասուն (forty)'],
        'pronunciation_tip': 'Aspirated "k" like in "kit"',
    },
    'օ': {
        'name': 'o',
        'uppercase': 'Օ',
        'lowercase': 'օ',
        'position': 37,
        'type': 'vowel',
        'ipa': 'o',
        'english': 'o',
        'difficulty': 1,
        'example_words': ['օր (day)', 'օդ (air)', 'օտար (foreign)'],
        'pronunciation_tip': 'Like "o" in "go"',
    },
    'ֆ': {
        'name': 'feh',
        'uppercase': 'Ֆ',
        'lowercase': 'ֆ',
        'position': 38,
        'type': 'consonant',
        'ipa': 'f',
        'english': 'f',
        'difficulty': 1,
        'example_words': ['ֆինանս (finance)', 'ֆիլմ (film)', 'ֆարմար (farmer)'],
        'pronunciation_tip': 'Like "f" in "fun"',
        'note': 'Mainly used in loanwords',
    },
}


# ─── Diphthongs and Multi-Letter Combinations ────────────────────────

ARMENIAN_DIPHTHONGS = {
    'ու': {
        'letters': ['ո', 'ւ'],
        'name': 'oo-ligature',
        'ipa': 'u',
        'english': 'oo',
        'difficulty': 1,
        'example_words': ['ընկեր (friend)', 'օղոր (soup)', 'ուզել (to want)'],
        'pronunciation_tip': 'Long "oo" sound like in "goose"',
        'note': 'Most common diphthong - ո + ւ creates single "oo" sound',
    },
    'իւ': {
        'letters': ['ի', 'ւ'],
        'name': 'yoo-ligature',
        'ipa': 'ju',
        'english': 'yoo',
        'difficulty': 1,
        'example_words': ['իւր (his/her own)', 'յիւղ (oil)'],
        'pronunciation_tip': 'Like "you" or "yew"',
        'note': 'Classical spelling - ի + ւ creates "yoo" sound',
    },
}


# ─── Add Audio File References ───────────────────────────────────────
# Automatically add audio file references to each letter if not already present

_AUDIO_FILE_MAP = {
    'ա': ('01_ա_name.wav', '01_ա_sound.wav'),
    'բ': ('02_բ_name.wav', '02_բ_sound.wav'),
    'գ': ('03_գ_name.wav', '03_գ_sound.wav'),
    'դ': ('04_դ_name.wav', '04_դ_sound.wav'),
    'ե': ('05_ե_name.wav', '05_ե_sound.wav'),
    'զ': ('06_զ_name.wav', '06_զ_sound.wav'),
    'է': ('07_է_name.wav', '07_է_sound.wav'),
    'ը': ('08_ը_name.wav', '08_ը_sound.wav'),
    'թ': ('09_թ_name.wav', '09_թ_sound.wav'),
    'ժ': ('10_ժ_name.wav', '10_ժ_sound.wav'),
    'ի': ('11_ի_name.wav', '11_ի_sound.wav'),
    'լ': ('12_լ_name.wav', '12_լ_sound.wav'),
    'խ': ('13_խ_name.wav', '13_խ_sound.wav'),
    'ծ': ('14_ծ_name.wav', '14_ծ_sound.wav'),
    'կ': ('15_կ_name.wav', '15_կ_sound.wav'),
    'հ': ('16_հ_name.wav', '16_հ_sound.wav'),
    'ձ': ('17_ձ_name.wav', '17_ձ_sound.wav'),
    'ղ': ('18_ղ_name.wav', '18_ղ_sound.wav'),
    'ճ': ('19_ճ_name.wav', '19_ճ_sound.wav'),
    'մ': ('20_մ_name.wav', '20_մ_sound.wav'),
    'յ': ('21_յ_name.wav', '21_յ_sound.wav'),
    'ն': ('22_ն_name.wav', '22_ն_sound.wav'),
    'շ': ('23_շ_name.wav', '23_շ_sound.wav'),
    'ո': ('24_ո_name.wav', '24_ո_sound.wav'),
    'չ': ('25_չ_name.wav', '25_չ_sound.wav'),
    'պ': ('26_պ_name.wav', '26_պ_sound.wav'),
    'ջ': ('27_ջ_name.wav', '27_ջ_sound.wav'),
    'ռ': ('28_ռ_name.wav', '28_ռ_sound.wav'),
    'ս': ('29_ս_name.wav', '29_ս_sound.wav'),
    'վ': ('30_վ_name.wav', '30_վ_sound.wav'),
    'տ': ('31_տ_name.wav', '31_տ_sound.wav'),
    'ր': ('32_ր_name.wav', '32_ր_sound.wav'),
    'ց': ('33_ց_name.wav', '33_ց_sound.wav'),
    'ւ': ('34_ւ_name.wav', '34_ւ_sound.wav'),
    'փ': ('35_փ_name.wav', '35_փ_sound.wav'),
    'ք': ('36_ք_name.wav', '36_ք_sound.wav'),
    'օ': ('37_օ_name.wav', '37_օ_sound.wav'),
    'ֆ': ('38_ֆ_name.wav', '38_ֆ_sound.wav'),
}

# Add audio files to each letter (if not already present)
for letter, (name_file, sound_file) in _AUDIO_FILE_MAP.items():
    if letter in ARMENIAN_LETTERS:
        if 'audio_file_name' not in ARMENIAN_LETTERS[letter]:
            ARMENIAN_LETTERS[letter]['audio_file_name'] = name_file
        if 'audio_file_sound' not in ARMENIAN_LETTERS[letter]:
            ARMENIAN_LETTERS[letter]['audio_file_sound'] = sound_file

# ─── Helper Functions ────────────────────────────────────────────────

def get_letter_info(letter: str) -> Optional[Dict]:
    """Get complete information for a single Armenian letter."""
    return ARMENIAN_LETTERS.get(letter)


def get_all_vowels() -> List[str]:
    """Return list of all Armenian vowel letters."""
    return [letter for letter, info in ARMENIAN_LETTERS.items() 
            if info['type'] == 'vowel']


def get_all_consonants() -> List[str]:
    """Return list of all Armenian consonant letters."""
    return [letter for letter, info in ARMENIAN_LETTERS.items() 
            if info['type'] == 'consonant']


def get_difficult_letters(min_difficulty: int = 3) -> List[str]:
    """Return letters with difficulty >= min_difficulty (default: 3+)."""
    return [letter for letter, info in ARMENIAN_LETTERS.items() 
            if info['difficulty'] >= min_difficulty]


def get_letters_by_type(letter_type: str) -> List[str]:
    """Get letters by type: 'vowel', 'consonant', 'semivowel', or 'mixed'."""
    return [letter for letter, info in ARMENIAN_LETTERS.items() 
            if info['type'] == letter_type]


def get_diphthong_info(diphthong: str) -> Optional[Dict]:
    """Get information about an Armenian diphthong."""
    return ARMENIAN_DIPHTHONGS.get(diphthong)


def get_all_letters_ordered() -> List[str]:
    """Return all Armenian letters in alphabet order."""
    return sorted(ARMENIAN_LETTERS.keys(), 
                  key=lambda x: ARMENIAN_LETTERS[x]['position'])


def is_western_reversed(letter: str) -> bool:
    """Check if letter has reversed voicing in Western Armenian."""
    info = ARMENIAN_LETTERS.get(letter, {})
    return 'western_note' in info and 'reversed' in info.get('western_note', '').lower()
