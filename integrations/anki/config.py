"""Configuration for the Anki card generation pipeline.

All constants have sensible defaults matching the standard Western Armenian
flashcard setup.  Consumers can import individual names or pass overrides
where applicable.
"""

# ─── AnkiConnect Settings ─────────────────────────────────────────────
ANKI_CONNECT_URL = "http://localhost:8765"
ANKI_CONNECT_VERSION = 6

# ─── Deck Settings ────────────────────────────────────────────────────
SOURCE_DECK = "Armenian Vocabulary"
TARGET_DECK = "Armenian Vocabulary::Morphology"
LETTER_CARDS_DECK = "Armenian Vocabulary::Letters"
VISUAL_LETTER_CARDS_DECK = "Armenian Vocabulary::Letters::Visual Training"

# ─── Note Type (Model) Names ─────────────────────────────────────────
NOUN_DECLENSION_MODEL = "Armenian Noun Declension"
VERB_CONJUGATION_MODEL = "Armenian Verb Conjugation"
VOCAB_SENTENCES_MODEL = "Armenian Vocab Sentences"
LETTER_CARDS_MODEL = "Armenian Letter Cards"
VISUAL_LETTER_CARDS_MODEL = "Armenian Visual Letter Cards"

# ─── Field Names ──────────────────────────────────────────────────────
SOURCE_FIELDS = {
    "word": "Word",
    "pos": "PartOfSpeech",
    "translation": "Translation",
    "pronunciation": "Pronunciation",
}

# ─── Tags ─────────────────────────────────────────────────────────────
TAG_GENERATED = "auto-generated"
TAG_DECLENSION = "declension"
TAG_CONJUGATION = "conjugation"
TAG_SENTENCES = "sentences"
TAG_LETTER = "letter-card"
TAG_VISUAL_LETTER = "letter-visual"

# ─── Morphology Settings ─────────────────────────────────────────────
DEFAULT_NOUN_DECLENSION = "i_class"
DEFAULT_VERB_CLASS = "e_class"
SENTENCES_PER_WORD = 5

# ─── Phrase-Chunking Progression Settings ───────────────────────────
PROGRESSION_VOCAB_BATCH_SIZE = 20
PROGRESSION_BATCHES_PER_LEVEL = 5

PROGRESSION_SYLLABLE_BANDS = {
    5:  1,   # Levels  1–5:  1-syllable words only
    10: 2,   # Levels  6–10: up to 2 syllables
    15: 3,   # Levels 11–15: up to 3 syllables
}            # Levels 16+:   no restriction

PROGRESSION_PHRASE_WORD_ALLOWANCE = {
    5:  1,   # Levels  1–5:  1 vocab word per phrase
    10: 3,   # Levels  6–10: up to 3 vocab words
    15: 4,   # Levels 11–15: up to 4 vocab words
    20: 5,   # Levels 16–20: up to 5 vocab words
}            # Levels 21+:   up to 6 vocab words
