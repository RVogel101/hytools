from __future__ import annotations

import pytest

from hytools.config.settings import ValidationError, load_config


def test_load_config_attaches_meta_and_expanded_defaults(tmp_path):
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
scraping:
  wikipedia:
    enabled: false
ingestion:
  incremental_merge:
    enabled: true
export:
  output_dir: exported
""".strip()
        + "\n",
        encoding="utf-8",
    )

    cfg = load_config(str(config_path))

    assert cfg["_meta"]["config_path"] == str(config_path)
    assert cfg["_meta"]["explicit_scraping_keys"] == ["wikipedia"]
    assert cfg["_meta"]["explicit_ingestion_keys"] == ["incremental_merge"]
    assert cfg["_meta"]["explicit_export_keys"] == ["output_dir"]
    assert cfg["scraping"]["wikipedia"]["enabled"] is False
    assert cfg["scraping"]["web_crawler"]["seed_file"] == "data/retrieval/crawler_seeds.txt"
    assert cfg["ingestion"]["incremental_merge"]["enabled"] is True
    assert cfg["ingestion"]["metadata_tagger"]["review_queue"]["confidence_threshold"] == 0.35
    assert cfg["export"]["release"]["dataset_name"] == "hytools-western-armenian-corpus"
    assert cfg["scheduler"]["interval_seconds"] == 21600
    assert cfg["research"]["exclude_dirs"] == ["augmented", "logs", "__pycache__"]


def test_load_config_rejects_invalid_release_ratio_sum(tmp_path):
    if ValidationError is None:
        pytest.skip("pydantic is not installed in this environment")

    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
export:
  release:
    train_ratio: 0.8
    validation_ratio: 0.15
    test_ratio: 0.15
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_config(str(config_path))