import pytest

from hytool.linguistics.morphology import difficulty


def test_phonetic_score_range():
    assert difficulty._score_phonetic_difficulty('') == 0.0
    s1 = difficulty._score_phonetic_difficulty('աբգ')
    assert 0.0 <= s1 <= 5.0
    s2 = difficulty._score_phonetic_difficulty('ֆխղժ')
    assert s2 >= s1


def test_orthographic_score_basic():
    assert difficulty._score_orthographic_mapping('') == 0.0
    s = difficulty._score_orthographic_mapping('աբգդ')
    assert 0.0 <= s <= 3.0


def compute_composite(rank, difficulty_score, max_rank=1000, alpha=0.85, beta=0.15):
    if max_rank <= 1:
        f_norm = 1.0
    else:
        f_norm = 1.0 - (rank - 1) / float(max_rank - 1)
    d_norm = 1.0 - min(max(difficulty_score / 10.0, 0.0), 1.0)
    return alpha * f_norm + beta * d_norm


def test_composite_calculation_monotonic():
    # Better rank should yield higher composite when difficulty equal
    c1 = compute_composite(rank=1, difficulty_score=5.0, max_rank=100)
    c2 = compute_composite(rank=50, difficulty_score=5.0, max_rank=100)
    assert c1 > c2

    # Lower difficulty (harder) reduces composite
    c_easy = compute_composite(rank=10, difficulty_score=1.0, max_rank=100)
    c_hard = compute_composite(rank=10, difficulty_score=9.0, max_rank=100)
    assert c_easy > c_hard
*** End Patch
