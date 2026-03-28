from hytools.ingestion._shared.helpers import normalize_internal_language_branch, is_valid_internal_language_branch


def test_normalize_internal_language_branch():
    assert normalize_internal_language_branch("hye-w") == "hye-w"
    assert normalize_internal_language_branch("western_armenian") == "hye-w"
    assert normalize_internal_language_branch("hyw") == "hye-w"
    assert normalize_internal_language_branch("hye-e") == "hye-e"
    assert normalize_internal_language_branch("eastern_armenian") == "hye-e"
    assert normalize_internal_language_branch("hye") == "hye-e"
    assert normalize_internal_language_branch("eng") == "eng"
    assert normalize_internal_language_branch("english") == "eng"
    assert normalize_internal_language_branch(None) is None
    assert normalize_internal_language_branch("unknown") is None


def test_is_valid_internal_language_branch():
    assert is_valid_internal_language_branch("hye-w")
    assert is_valid_internal_language_branch("hye-e")
    assert is_valid_internal_language_branch("eng")
    assert is_valid_internal_language_branch("western_armenian")
    assert is_valid_internal_language_branch("eastern_armenian")
    assert not is_valid_internal_language_branch(None)
