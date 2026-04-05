"""Configuration loader with Pydantic validation for hytools settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Union

import yaml

try:
    from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

    _PYDANTIC_AVAILABLE = True
except ImportError:
    _PYDANTIC_AVAILABLE = False
    BaseModel = None  # type: ignore[assignment,misc]
    ConfigDict = None  # type: ignore[assignment,misc]
    Field = None  # type: ignore[assignment,misc]
    ValidationError = None  # type: ignore[assignment,misc]
    model_validator = None  # type: ignore[assignment,misc]


def _collect_explicit_keys(raw: dict[str, Any], section: str) -> list[str]:
    section_data = raw.get(section)
    if not isinstance(section_data, dict):
        return []
    return sorted(str(key) for key in section_data.keys() if not str(key).startswith("_"))


def _attach_config_meta(config: dict[str, Any], raw: dict[str, Any], config_path: Path) -> dict[str, Any]:
    data = dict(config)
    data["_meta"] = {
        "config_path": str(config_path),
        "validation_mode": "pydantic" if _PYDANTIC_AVAILABLE else "yaml",
        "explicit_scraping_keys": _collect_explicit_keys(raw, "scraping"),
        "explicit_ingestion_keys": _collect_explicit_keys(raw, "ingestion"),
        "explicit_export_keys": _collect_explicit_keys(raw, "export"),
        "explicit_scheduler_keys": _collect_explicit_keys(raw, "scheduler"),
    }
    return data


if _PYDANTIC_AVAILABLE:

    class HytoolsBaseModel(BaseModel):
        model_config = ConfigDict(extra="allow")


    class StageToggleConfig(HytoolsBaseModel):
        enabled: bool = True


    class PathsConfig(HytoolsBaseModel):
        data_root: str = "data"
        raw_dir: str = "data/raw"
        cleaned_dir: str = "data/cleaned"
        filtered_dir: str = "data/filtered"
        log_dir: str = "data/logs"
        metadata_dir: str = "data/metadata"
        cache_dir: str = "cache"
        delete_after_ingest: bool = False


    class DatabaseConfig(HytoolsBaseModel):
        use_mongodb: bool = True
        mongodb_uri: str = "mongodb://localhost:27017/"
        mongodb_database: str = "western_armenian_corpus"
        compute_metrics_on_ingest: bool = True


    class OcrConfig(HytoolsBaseModel):
        dpi: int = Field(default=300, ge=72, le=1200)
        tesseract_lang: str = "hye+eng"
        per_page_lang: str = "auto"
        tesseract_lang_armenian: str = "hye"
        tesseract_lang_mixed: str = "hye+eng"
        tesseract_lang_english: str = "eng"
        script_armenian_threshold: float = Field(default=0.9, ge=0.0, le=1.0)
        script_english_threshold: float = Field(default=0.9, ge=0.0, le=1.0)
        binarization: str = "sauvola"
        confidence_threshold: int = Field(default=60, ge=0, le=100)
        psm: int = Field(default=6, ge=0, le=13)
        use_text_layer: Union[bool, Literal["auto"]] = "auto"
        overwrite: bool = False
        adaptive_dpi: bool = True
        font_hint: str = "normal"
        probe_dpi: int = Field(default=200, ge=72, le=1200)
        detect_cursive: bool = True
        cursive_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
        use_surya: Union[bool, Literal["auto"]] = "auto"
        zone_ocr: Union[bool, Literal["auto"]] = "auto"
        classify_pages: Union[bool, Literal["auto"]] = "auto"
        stroke_thicken: Union[bool, Literal["auto"]] = False
        stroke_thin_threshold: float = Field(default=2.5, ge=0.0)
        stroke_thicken_iterations: int = Field(default=1, ge=1, le=10)
        stroke_thicken_kernel: int = Field(default=2, ge=1, le=10)
        classical_ocr: Union[bool, Literal["auto"]] = "auto"
        classical_lang: str = "hye_old"
        classical_threshold: float = Field(default=15.0, ge=0.0)
        monitor_alert_threshold: float = Field(default=0.10, ge=0.0, le=1.0)
        monitor_min_pages: int = Field(default=3, ge=1)
        use_ocrmypdf: Union[bool, Literal["auto"]] = "auto"
        use_kraken: Union[bool, Literal["auto"]] = "auto"
        kraken_model: str = ""
        ml_corrector: Union[bool, Literal["auto"]] = "auto"
        ml_corrector_model: str = ""
        ml_corrector_max_length: int = Field(default=512, ge=1)
        armcor_correction: Union[bool, Literal["auto"]] = "auto"
        armcor_freq_path: str = ""
        armcor_freq_path_wa: str = ""
        armcor_freq_path_ea: str = ""
        armcor_min_freq: int = Field(default=3, ge=1)
        armcor_max_edit_distance: int = Field(default=1, ge=1, le=3)


    class AugmentationConfig(HytoolsBaseModel):
        use_safe_wrapper: bool = True
        output_backend: str = "mongodb"
        source_backend: str = "mongodb"


    class CleaningConfig(HytoolsBaseModel):
        minhash_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
        minhash_num_perm: int = Field(default=128, ge=1)
        target_language: str = "hyw"
        min_chars_per_doc: int = Field(default=100, ge=0)


    class AnnDedupConfig(HytoolsBaseModel):
        enabled: bool = True
        backend: str = "annoy"
        metric: str = "euclidean"
        distance_threshold: float = Field(default=0.90, ge=0.0)
        n_trees: int = Field(default=20, ge=1)
        n_neighbors: int = Field(default=32, ge=1)
        vectors_path: str = "data/ann_vectors.npz"
        index_path: str = "data/ann_index.ann"
        force_rebuild: bool = False


    class WikimediaStageConfig(StageToggleConfig):
        language: str = "hyw"
        dump_date: str = "latest"
        categories: list[str] = Field(default_factory=list)


    class CulturaXStageConfig(StageToggleConfig):
        dataset_name: str = "uonlp/CulturaX"
        language: str = "hy"
        streaming: bool = True
        min_chars: int = Field(default=1, ge=1)
        max_docs: int = Field(default=0, ge=0)


    class OpusStageConfig(StageToggleConfig):
        corpora: list[str] | None = None


    class JwStageConfig(StageToggleConfig):
        include_eastern: bool = True


    class DplaStageConfig(StageToggleConfig):
        api_key: str = ""


    class NewspapersStageConfig(StageToggleConfig):
        sources: list[str] = Field(default_factory=list)
        max_pages: int = Field(default=0, ge=0)
        max_articles_per_source: int = Field(default=0, ge=0)


    class WebCrawlerSearchSeedingConfig(HytoolsBaseModel):
        enabled: bool = False
        max_results_per_query: int = Field(default=10, ge=1)
        include_existing_corpus_urls: bool = True
        existing_corpus_seed_limit: int = Field(default=250, ge=0)


    class WebCrawlerIncrementalConfig(HytoolsBaseModel):
        enabled: bool = True
        recrawl_after_hours: float = Field(default=168.0, ge=0.0)
        resume_frontier: bool = True
        state_sync_every: int = Field(default=25, ge=1)


    class WebCrawlerPlaywrightConfig(HytoolsBaseModel):
        enabled: bool = False
        timeout_ms: int = Field(default=15000, ge=1)


    class WebCrawlerReviewQueueConfig(HytoolsBaseModel):
        enabled: bool = True
        confidence_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
        score_margin_threshold: float = Field(default=2.0, ge=0.0)
        min_armenian_ratio: float = Field(default=0.05, ge=0.0, le=1.0)


    class WebCrawlerStageConfig(StageToggleConfig):
        seed_file: str = "data/retrieval/crawler_seeds.txt"
        discovery_report: str = "data/retrieval/crawler_found.csv"
        audit_report_csv: str = "data/retrieval/wa_crawler_audit.csv"
        audit_report_json: str = "data/retrieval/wa_crawler_audit.json"
        max_depth: int = Field(default=2, ge=0)
        max_pages_per_domain: int = Field(default=50, ge=1)
        max_total_pages: int = Field(default=500, ge=1)
        request_delay_seconds: float = Field(default=2.0, ge=0.0)
        wa_threshold: float = Field(default=5.0, ge=0.0)
        min_armenian_ratio: float = Field(default=0.10, ge=0.0, le=1.0)
        min_text_chars: int = Field(default=200, ge=0)
        user_agent: str = "HytoolsCorpusCrawler/1.0 (+https://github.com/RVogel101/hytools)"
        allow_http: bool = False
        allow_external_domains: bool = False
        search_seeding: WebCrawlerSearchSeedingConfig = Field(default_factory=WebCrawlerSearchSeedingConfig)
        incremental: WebCrawlerIncrementalConfig = Field(default_factory=WebCrawlerIncrementalConfig)
        playwright_fallback: WebCrawlerPlaywrightConfig = Field(default_factory=WebCrawlerPlaywrightConfig)
        review_queue: WebCrawlerReviewQueueConfig = Field(default_factory=WebCrawlerReviewQueueConfig)


    class NayiriStageConfig(StageToggleConfig):
        lexicon_url: str = ""
        corpus_url: str = ""
        lexicon_path: str = ""
        corpus_path: str = ""
        lexicon_keep_zip: bool = False
        corpus_keep_zip: bool = False


    class MetadataTaggerStageConfig(StageToggleConfig):
        class ReviewQueueConfig(HytoolsBaseModel):
            enabled: bool = False
            confidence_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
            score_margin_threshold: float = Field(default=2.0, ge=0.0)

        output_csv: str | bool | None = None
        review_queue: ReviewQueueConfig = Field(default_factory=ReviewQueueConfig)


    class FrequencyAggregatorStageConfig(StageToggleConfig):
        internal_language_branch: str = "hye-w"
        hybrid_profile: bool = False
        wa_score_weight: float = Field(default=0.5, ge=0.0)
        incremental: bool = True


    class ExportReleaseConfig(HytoolsBaseModel):
        output_dir: str = "data/releases/latest"
        dataset_name: str = "hytools-western-armenian-corpus"
        dataset_version: str = "0.1.0"
        split_seed: str = "hytools-release-v1"
        train_ratio: float = Field(default=0.90, ge=0.0, le=1.0)
        validation_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
        test_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
        include_huggingface: bool = True
        include_full_parquet: bool = True
        include_dataset_card: bool = True
        include_checksums: bool = True

        @model_validator(mode="after")
        def _validate_split_total(self) -> "ExportReleaseConfig":
            total = self.train_ratio + self.validation_ratio + self.test_ratio
            if abs(total - 1.0) > 1e-6:
                raise ValueError("export.release train/validation/test ratios must sum to 1.0")
            return self


    class ExportConfig(HytoolsBaseModel):
        output_dir: str = "data/export"
        dialect_filter: str | None = None
        formats: list[str] = Field(default_factory=lambda: ["parquet", "huggingface"])
        release: ExportReleaseConfig = Field(default_factory=ExportReleaseConfig)


    class SchedulerConfig(HytoolsBaseModel):
        interval_seconds: int = Field(default=21600, ge=1)
        alert_window_seconds: int = Field(default=86400, ge=1)
        max_retries: int = Field(default=3, ge=0)
        alert_file: str = ""
        state_dir: str = ""


    class ResearchConfig(HytoolsBaseModel):
        exclude_dirs: list[str] = Field(default_factory=lambda: ["augmented", "logs", "__pycache__"])
        exclude_sources: list[str] = Field(default_factory=lambda: ["augmented"])
        error_threshold_pct: float = Field(default=10.0, ge=0.0)
        metadata_patterns: list[str] = Field(default_factory=lambda: ["*.json", "*.jsonl"])


    class IngestionConfig(HytoolsBaseModel):
        cleaning: StageToggleConfig = Field(default_factory=StageToggleConfig)
        metadata_tagger: MetadataTaggerStageConfig = Field(default_factory=MetadataTaggerStageConfig)
        frequency_aggregator: FrequencyAggregatorStageConfig = Field(default_factory=FrequencyAggregatorStageConfig)
        incremental_merge: StageToggleConfig = Field(default_factory=StageToggleConfig)
        word_frequency_facets: StageToggleConfig = Field(default_factory=StageToggleConfig)
        drift_detection: StageToggleConfig = Field(default_factory=StageToggleConfig)
        export_corpus_overlap_fingerprints: StageToggleConfig = Field(default_factory=StageToggleConfig)
        corpus_export: StageToggleConfig = Field(default_factory=StageToggleConfig)
        extraction: StageToggleConfig = Field(default_factory=StageToggleConfig)


    class ScrapingConfig(HytoolsBaseModel):
        compute_metrics_on_ingest: bool = True
        wikipedia: WikimediaStageConfig = Field(default_factory=WikimediaStageConfig)
        wikisource: WikimediaStageConfig = Field(default_factory=WikimediaStageConfig)
        archive_org: StageToggleConfig = Field(default_factory=StageToggleConfig)
        hathitrust: StageToggleConfig = Field(default_factory=StageToggleConfig)
        gallica: StageToggleConfig = Field(default_factory=StageToggleConfig)
        loc: StageToggleConfig = Field(default_factory=StageToggleConfig)
        dpla: DplaStageConfig = Field(default_factory=DplaStageConfig)
        newspapers: NewspapersStageConfig = Field(default_factory=NewspapersStageConfig)
        web_crawler: WebCrawlerStageConfig = Field(default_factory=WebCrawlerStageConfig)
        culturax: CulturaXStageConfig = Field(default_factory=CulturaXStageConfig)
        opus: OpusStageConfig = Field(default_factory=OpusStageConfig)
        jw: JwStageConfig = Field(default_factory=JwStageConfig)
        english_sources: StageToggleConfig = Field(default_factory=StageToggleConfig)
        nayiri: NayiriStageConfig = Field(default_factory=NayiriStageConfig)
        gomidas: StageToggleConfig = Field(default_factory=StageToggleConfig)
        mechitarist: StageToggleConfig = Field(default_factory=StageToggleConfig)
        agbu: StageToggleConfig = Field(default_factory=StageToggleConfig)
        hamazkayin: StageToggleConfig = Field(default_factory=StageToggleConfig)
        agos: StageToggleConfig = Field(default_factory=StageToggleConfig)
        ocr_ingest: StageToggleConfig = Field(default_factory=StageToggleConfig)
        mss_nkr: StageToggleConfig = Field(default_factory=StageToggleConfig)
        worldcat: StageToggleConfig = Field(default_factory=StageToggleConfig)
        eastern_armenian: StageToggleConfig = Field(default_factory=StageToggleConfig)
        rss_news: StageToggleConfig = Field(default_factory=StageToggleConfig)
        cleaning: StageToggleConfig = Field(default_factory=StageToggleConfig)
        metadata_tagger: MetadataTaggerStageConfig = Field(default_factory=MetadataTaggerStageConfig)
        frequency_aggregator: FrequencyAggregatorStageConfig = Field(default_factory=FrequencyAggregatorStageConfig)
        incremental_merge: StageToggleConfig = Field(default_factory=StageToggleConfig)
        word_frequency_facets: StageToggleConfig = Field(default_factory=StageToggleConfig)
        drift_detection: StageToggleConfig = Field(default_factory=StageToggleConfig)
        export_corpus_overlap_fingerprints: StageToggleConfig = Field(default_factory=StageToggleConfig)
        corpus_export: StageToggleConfig = Field(default_factory=StageToggleConfig)
        extraction: StageToggleConfig = Field(default_factory=StageToggleConfig)


    class HytoolsConfig(HytoolsBaseModel):
        paths: PathsConfig = Field(default_factory=PathsConfig)
        database: DatabaseConfig = Field(default_factory=DatabaseConfig)
        ocr: OcrConfig = Field(default_factory=OcrConfig)
        augmentation: AugmentationConfig = Field(default_factory=AugmentationConfig)
        cleaning: CleaningConfig = Field(default_factory=CleaningConfig)
        ann_dedup: AnnDedupConfig = Field(default_factory=AnnDedupConfig)
        scraping: ScrapingConfig = Field(default_factory=ScrapingConfig)
        ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
        export: ExportConfig = Field(default_factory=ExportConfig)
        scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
        research: ResearchConfig = Field(default_factory=ResearchConfig)


def load_config(config_path: str) -> dict[str, Any]:
    """Load configuration from a YAML file with optional Pydantic validation.

    When Pydantic is installed, the YAML is validated against the schema
    and missing keys receive defaults. When Pydantic is unavailable,
    raw ``yaml.safe_load`` output is returned for backwards compatibility.

    The returned config also includes a lightweight ``_meta`` section so
    callers can distinguish explicitly declared stage keys from injected
    runtime defaults.
    """

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with config_file.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    if _PYDANTIC_AVAILABLE:
        validated = HytoolsConfig(**raw)
        return _attach_config_meta(validated.model_dump(), raw, config_file)

    return _attach_config_meta(raw, raw, config_file)