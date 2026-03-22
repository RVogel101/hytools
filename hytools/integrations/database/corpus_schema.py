"""Corpus ingestion database schema (16 tables).

Migrated from WesternArmenianLLM/src/database/schema.py.
"""

CORPUS_SCHEMA_SQL = """
-- ====================================================================
-- Core metadata table: tracks all ingestion operations
-- ====================================================================
CREATE TABLE IF NOT EXISTS ingestion_operations (
    operation_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    operation_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL,
    description TEXT,
    config_snapshot TEXT,
    error_message TEXT
);

-- ====================================================================
-- Newspaper articles
-- ====================================================================
CREATE TABLE IF NOT EXISTS newspaper_articles (
    article_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    title TEXT,
    content TEXT,
    scraped_timestamp DATETIME,
    published_date_raw TEXT,
    author TEXT,
    source_language TEXT DEFAULT 'western_armenian',
    content_sha1 TEXT,
    content_length_chars INTEGER,
    operation_id TEXT,
    FOREIGN KEY (operation_id) REFERENCES ingestion_operations(operation_id)
);

CREATE INDEX IF NOT EXISTS idx_newspaper_source ON newspaper_articles(source_name);
CREATE INDEX IF NOT EXISTS idx_newspaper_timestamp ON newspaper_articles(scraped_timestamp);
CREATE INDEX IF NOT EXISTS idx_newspaper_sha1 ON newspaper_articles(content_sha1);

-- ====================================================================
-- Nayiri dictionary entries
-- ====================================================================
CREATE TABLE IF NOT EXISTS nayiri_entries (
    entry_id TEXT PRIMARY KEY,
    headword TEXT NOT NULL,
    headword_transliterated TEXT,
    pronunciation TEXT,
    part_of_speech TEXT,
    definition TEXT,
    examples TEXT,
    etymology TEXT,
    content_sha1 TEXT,
    scraped_timestamp DATETIME,
    operation_id TEXT,
    FOREIGN KEY (operation_id) REFERENCES ingestion_operations(operation_id)
);

CREATE INDEX IF NOT EXISTS idx_nayiri_headword ON nayiri_entries(headword);
CREATE INDEX IF NOT EXISTS idx_nayiri_timestamp ON nayiri_entries(scraped_timestamp);
CREATE INDEX IF NOT EXISTS idx_nayiri_sha1 ON nayiri_entries(content_sha1);

-- ====================================================================
-- Archive.org texts
-- ====================================================================
CREATE TABLE IF NOT EXISTS archive_org_texts (
    text_id TEXT PRIMARY KEY,
    archive_id TEXT NOT NULL,
    title TEXT,
    author TEXT,
    publication_date TEXT,
    full_text TEXT,
    extracted_from_format TEXT,
    source_url TEXT,
    content_sha1 TEXT,
    content_length_chars INTEGER,
    language TEXT DEFAULT 'western_armenian',
    scraped_timestamp DATETIME,
    operation_id TEXT,
    FOREIGN KEY (operation_id) REFERENCES ingestion_operations(operation_id)
);

CREATE INDEX IF NOT EXISTS idx_archive_id ON archive_org_texts(archive_id);
CREATE INDEX IF NOT EXISTS idx_archive_timestamp ON archive_org_texts(scraped_timestamp);
CREATE INDEX IF NOT EXISTS idx_archive_sha1 ON archive_org_texts(content_sha1);

-- ====================================================================
-- Wikipedia articles (Western Armenian wiki)
-- ====================================================================
CREATE TABLE IF NOT EXISTS wikipedia_articles (
    article_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    content TEXT,
    revision_id INTEGER,
    scraped_timestamp DATETIME,
    content_sha1 TEXT,
    content_length_chars INTEGER,
    operation_id TEXT,
    FOREIGN KEY (operation_id) REFERENCES ingestion_operations(operation_id)
);

CREATE INDEX IF NOT EXISTS idx_wiki_title ON wikipedia_articles(title);
CREATE INDEX IF NOT EXISTS idx_wiki_timestamp ON wikipedia_articles(scraped_timestamp);
CREATE INDEX IF NOT EXISTS idx_wiki_sha1 ON wikipedia_articles(content_sha1);

-- ====================================================================
-- CulturaX texts
-- ====================================================================
CREATE TABLE IF NOT EXISTS culturax_texts (
    text_id TEXT PRIMARY KEY,
    source_url TEXT,
    source_domain TEXT,
    title TEXT,
    content TEXT,
    language TEXT DEFAULT 'western_armenian',
    scraped_timestamp DATETIME,
    content_sha1 TEXT,
    content_length_chars INTEGER,
    operation_id TEXT,
    FOREIGN KEY (operation_id) REFERENCES ingestion_operations(operation_id)
);

CREATE INDEX IF NOT EXISTS idx_culturax_domain ON culturax_texts(source_domain);
CREATE INDEX IF NOT EXISTS idx_culturax_timestamp ON culturax_texts(scraped_timestamp);
CREATE INDEX IF NOT EXISTS idx_culturax_sha1 ON culturax_texts(content_sha1);

-- ====================================================================
-- HathiTrust texts
-- ====================================================================
CREATE TABLE IF NOT EXISTS hathitrust_texts (
    text_id TEXT PRIMARY KEY,
    hathi_id TEXT NOT NULL,
    title TEXT,
    author TEXT,
    publication_date TEXT,
    language TEXT DEFAULT 'western_armenian',
    full_text TEXT,
    source_url TEXT,
    content_sha1 TEXT,
    content_length_chars INTEGER,
    scraped_timestamp DATETIME,
    operation_id TEXT,
    FOREIGN KEY (operation_id) REFERENCES ingestion_operations(operation_id)
);

CREATE INDEX IF NOT EXISTS idx_hathitrust_id ON hathitrust_texts(hathi_id);
CREATE INDEX IF NOT EXISTS idx_hathitrust_timestamp ON hathitrust_texts(scraped_timestamp);
CREATE INDEX IF NOT EXISTS idx_hathitrust_sha1 ON hathitrust_texts(content_sha1);

-- ====================================================================
-- Library of Congress texts
-- ====================================================================
CREATE TABLE IF NOT EXISTS loc_texts (
    text_id TEXT PRIMARY KEY,
    loc_id TEXT NOT NULL,
    title TEXT,
    author TEXT,
    publication_date TEXT,
    language TEXT DEFAULT 'western_armenian',
    full_text TEXT,
    source_url TEXT,
    content_sha1 TEXT,
    content_length_chars INTEGER,
    scraped_timestamp DATETIME,
    operation_id TEXT,
    FOREIGN KEY (operation_id) REFERENCES ingestion_operations(operation_id)
);

CREATE INDEX IF NOT EXISTS idx_loc_id ON loc_texts(loc_id);
CREATE INDEX IF NOT EXISTS idx_loc_timestamp ON loc_texts(scraped_timestamp);
CREATE INDEX IF NOT EXISTS idx_loc_sha1 ON loc_texts(content_sha1);

-- ====================================================================
-- Wikisource texts
-- ====================================================================
CREATE TABLE IF NOT EXISTS wikisource_texts (
    text_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    author TEXT,
    publication_date TEXT,
    content TEXT,
    revision_id INTEGER,
    scraped_timestamp DATETIME,
    content_sha1 TEXT,
    content_length_chars INTEGER,
    operation_id TEXT,
    FOREIGN KEY (operation_id) REFERENCES ingestion_operations(operation_id)
);

CREATE INDEX IF NOT EXISTS idx_wikisource_title ON wikisource_texts(title);
CREATE INDEX IF NOT EXISTS idx_wikisource_timestamp ON wikisource_texts(scraped_timestamp);
CREATE INDEX IF NOT EXISTS idx_wikisource_sha1 ON wikisource_texts(content_sha1);

-- ====================================================================
-- Deduplication audit trail
-- ====================================================================
CREATE TABLE IF NOT EXISTS dedup_records (
    dedup_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    entry_id TEXT NOT NULL,
    content_sha1 TEXT NOT NULL,
    first_seen_timestamp DATETIME,
    duplicate_count INTEGER DEFAULT 0,
    original_source_name TEXT
);

CREATE INDEX IF NOT EXISTS idx_dedup_sha1 ON dedup_records(content_sha1);
CREATE INDEX IF NOT EXISTS idx_dedup_entry ON dedup_records(entry_id);

-- ====================================================================
-- Migration audit trail
-- ====================================================================
CREATE TABLE IF NOT EXISTS migration_log (
    migration_id TEXT PRIMARY KEY,
    source_file TEXT NOT NULL,
    source_type TEXT NOT NULL,
    target_table TEXT NOT NULL,
    record_count INTEGER,
    migration_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL,
    error_message TEXT,
    file_deleted BOOLEAN DEFAULT FALSE,
    file_delete_timestamp DATETIME
);

CREATE INDEX IF NOT EXISTS idx_migration_source ON migration_log(source_file);
CREATE INDEX IF NOT EXISTS idx_migration_status ON migration_log(status);

-- ====================================================================
-- Process telemetry and metrics
-- ====================================================================
CREATE TABLE IF NOT EXISTS process_telemetry (
    telemetry_id TEXT PRIMARY KEY,
    operation_id TEXT,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    process_phase TEXT,
    event_type TEXT,
    event_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_description TEXT,
    metric_name TEXT,
    metric_value REAL,
    metric_unit TEXT,
    duration_seconds REAL,
    success BOOLEAN,
    error_message TEXT,
    FOREIGN KEY (operation_id) REFERENCES ingestion_operations(operation_id)
);

CREATE INDEX IF NOT EXISTS idx_telemetry_operation ON process_telemetry(operation_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_source ON process_telemetry(source_type, source_name);
CREATE INDEX IF NOT EXISTS idx_telemetry_phase ON process_telemetry(process_phase);
CREATE INDEX IF NOT EXISTS idx_telemetry_type ON process_telemetry(event_type);

-- ====================================================================
-- Process bottlenecks and issues log
-- ====================================================================
CREATE TABLE IF NOT EXISTS process_issues (
    issue_id TEXT PRIMARY KEY,
    operation_id TEXT,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    issue_category TEXT,
    issue_severity TEXT,
    issue_description TEXT,
    affected_records INTEGER,
    affected_items TEXT,
    resolution_attempted TEXT,
    resolution_success BOOLEAN,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (operation_id) REFERENCES ingestion_operations(operation_id)
);

CREATE INDEX IF NOT EXISTS idx_issues_operation ON process_issues(operation_id);
CREATE INDEX IF NOT EXISTS idx_issues_source ON process_issues(source_type, source_name);
CREATE INDEX IF NOT EXISTS idx_issues_category ON process_issues(issue_category);
CREATE INDEX IF NOT EXISTS idx_issues_severity ON process_issues(issue_severity);

-- ====================================================================
-- Process metrics aggregates
-- ====================================================================
CREATE TABLE IF NOT EXISTS process_metrics (
    metrics_id TEXT PRIMARY KEY,
    operation_id TEXT UNIQUE,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    total_records_attempted INTEGER,
    total_records_imported INTEGER,
    total_records_skipped INTEGER,
    total_records_failed INTEGER,
    total_duration_seconds REAL,
    avg_record_time_ms REAL,
    content_deduped INTEGER,
    unique_content_hashes INTEGER,
    earliest_timestamp DATETIME,
    latest_timestamp DATETIME,
    data_size_mb REAL,
    compression_ratio_percent REAL,
    FOREIGN KEY (operation_id) REFERENCES ingestion_operations(operation_id)
);

CREATE INDEX IF NOT EXISTS idx_metrics_operation ON process_metrics(operation_id);
CREATE INDEX IF NOT EXISTS idx_metrics_source ON process_metrics(source_type);

-- ====================================================================
-- Data quality metrics
-- ====================================================================
CREATE TABLE IF NOT EXISTS data_quality (
    quality_id TEXT PRIMARY KEY,
    operation_id TEXT,
    source_type TEXT NOT NULL,
    table_name TEXT NOT NULL,
    metric_name TEXT,
    metric_value REAL,
    check_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    passed BOOLEAN,
    FOREIGN KEY (operation_id) REFERENCES ingestion_operations(operation_id)
);

CREATE INDEX IF NOT EXISTS idx_quality_operation ON data_quality(operation_id);
CREATE INDEX IF NOT EXISTS idx_quality_table ON data_quality(table_name);

-- ====================================================================
-- Training dataset allocation
-- ====================================================================
CREATE TABLE IF NOT EXISTS training_allocations (
    allocation_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    table_name TEXT NOT NULL,
    record_id TEXT NOT NULL,
    dataset_split TEXT,
    allocated_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    allocated_for_model TEXT
);

CREATE INDEX IF NOT EXISTS idx_allocation_source ON training_allocations(source_type);
CREATE INDEX IF NOT EXISTS idx_allocation_split ON training_allocations(dataset_split);
CREATE INDEX IF NOT EXISTS idx_allocation_model ON training_allocations(allocated_for_model);
"""


def get_corpus_schema_sql() -> str:
    """Return the complete corpus schema SQL."""
    return CORPUS_SCHEMA_SQL
