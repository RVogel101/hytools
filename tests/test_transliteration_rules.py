import pytest


def test_western_rejects_eastern_markers():
    from hytools.linguistics.tools.transliteration import to_latin

    # Eastern/reform token 'խոսել' should be detected and rejected for Western dialect
    with pytest.raises(ValueError):
        to_latin('Նա խոսել հայերեն', dialect='western')


def test_western_accepts_western_text():
    from hytools.linguistics.tools.transliteration import to_latin

    # Canonical Western Armenian phrase should transliterate without error
    out = to_latin('Ան կը խօսի հայերէն', dialect='western')
    assert isinstance(out, str) and len(out) > 0
