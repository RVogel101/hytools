import tempfile
from pathlib import Path

from hytools.cleaning.dedup import deduplicate_files
from hytools.cleaning.dedup_ann import deduplicate_vectors, deduplicate_directory


def test_exact_sha_prefilter_removes_duplicates(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    f1 = input_dir / "a.txt"
    f2 = input_dir / "b.txt"
    f3 = input_dir / "c.txt"

    f1.write_text("hello world", encoding="utf-8")
    f2.write_text("hello world", encoding="utf-8")
    f3.write_text("different text", encoding="utf-8")

    total, kept = deduplicate_files(input_dir, output_dir, threshold=0.85, num_perm=64)

    assert total == 3
    assert kept == 2

    out_files = sorted([p.name for p in output_dir.rglob("*.txt")])
    assert out_files == ["a.txt", "c.txt"] or out_files == ["b.txt", "c.txt"]


from hytools.cleaning.dedup_ann import deduplicate_vectors


def test_ann_hash_dedup_annoy_or_bruteforce():
    # deterministic synthetic vectors, two duplicate groups
    vectors = [
        [0.0, 0.0],
        [0.05, -0.02],
        [10.0, 10.0],
        [10.1, 10.1],
        [50.0, 50.0],
    ]

    result = deduplicate_vectors(vectors, distance_threshold=0.25, backend="annoy", n_trees=10)
    assert result == [0, 2, 4] or result == [0, 2, 4]


def test_ann_faiss_or_bruteforce():
    vectors = [
        [0.0, 0.0],
        [0.2, 0.0],
        [5.0, 5.0],
        [5.2, 5.0],
    ]
    result = deduplicate_vectors(vectors, distance_threshold=0.3, backend="brute")
    assert result == [0, 2]


def test_dedup_ann_directory_persistence(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    (input_dir / "a.txt").write_text("alpha data", encoding="utf-8")
    (input_dir / "b.txt").write_text("alpha data", encoding="utf-8")
    (input_dir / "c.txt").write_text("beta data", encoding="utf-8")

    vectors_path = tmp_path / "ann_vectors.npz"
    index_path = tmp_path / "ann_index.ann"

    total, kept = deduplicate_directory(
        input_dir=input_dir,
        output_dir=output_dir,
        distance_threshold=0.5,
        backend="brute",
        vectors_path=vectors_path,
        index_path=None,
        force_rebuild=True,
    )

    assert total == 3
    assert kept == 2
    assert vectors_path.exists()

    # Re-run using cache should not fail
    total, kept = deduplicate_directory(
        input_dir=input_dir,
        output_dir=output_dir,
        distance_threshold=0.5,
        backend="brute",
        vectors_path=vectors_path,
        index_path=None,
        force_rebuild=False,
    )

    assert total == 3
    assert kept == 2

