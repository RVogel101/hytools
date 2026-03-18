# Local Scheduler

This document provides cron and systemd timer examples for running the Armenian corpus pipeline locally.

## Prerequisites

- MongoDB running (e.g. `mongod` or Docker)
- Project installed: `pip install -e '.[all]'`
- Config at `config/settings.yaml` with `database.mongodb_uri`

## Cron Jobs

Add to `crontab -e` (adjust paths and times as needed):

```cron
# Scraping pipeline — weekly (Mondays 03:00)
0 3 * * 1 cd /path/to/armenian-corpus-core && python -m scraping.runner run --config config/settings.yaml --only wikipedia_wa,wikipedia_ea,wikisource,archive_org,hathitrust,loc >> data/logs/cron_scraping.log 2>&1

# Scraping pipeline — daily (06:00)
0 6 * * * cd /path/to/armenian-corpus-core && python -m scraping.runner run --config config/settings.yaml --only newspaper,ea_news,culturax,rss_news,english_sources >> data/logs/cron_scraping.log 2>&1

# Cleaning — after scraping (daily 08:00)
0 8 * * * cd /path/to/armenian-corpus-core && python -m scraping.runner run --config config/settings.yaml --only cleaning >> data/logs/cron_cleaning.log 2>&1

# Augmentation — after cleaning (daily 09:00)
0 9 * * * cd /path/to/armenian-corpus-core && python -m augmentation.runner run >> data/logs/cron_augmentation.log 2>&1

# Book catalog — weekly (Sundays 02:00)
0 2 * * 0 cd /path/to/armenian-corpus-core && python -m ingestion.discovery.book_inventory_runner --config config/settings.yaml --worldcat --scan-mongodb >> data/logs/cron_book_inventory.log 2>&1

# Author updates — weekly (Sundays 04:00)
0 4 * * 0 cd /path/to/armenian-corpus-core && python -m ingestion.research_runner --config config/settings.yaml >> data/logs/cron_author_research.log 2>&1
```

## Systemd Timers

### 1. Scraping service

`~/.config/systemd/user/armenian-corpus-scraping.service`:

```ini
[Unit]
Description=Armenian corpus scraping pipeline
After=network.target mongod.service

[Service]
Type=oneshot
WorkingDirectory=/path/to/armenian-corpus-core
ExecStart=/usr/bin/python -m scraping.runner run --config config/settings.yaml
StandardOutput=append:data/logs/scraping.log
StandardError=append:data/logs/scraping.log
```

### 2. Scraping timer (weekly)

`~/.config/systemd/user/armenian-corpus-scraping-weekly.timer`:

```ini
[Unit]
Description=Armenian corpus scraping (weekly)

[Timer]
OnCalendar=Mon *-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

### 3. Scraping timer (daily)

`~/.config/systemd/user/armenian-corpus-scraping-daily.timer`:

```ini
[Unit]
Description=Armenian corpus scraping (daily)

[Timer]
OnCalendar=*-*-* 06:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

### 4. Cleaning service

`~/.config/systemd/user/armenian-corpus-cleaning.service`:

```ini
[Unit]
Description=Armenian corpus cleaning
After=network.target mongod.service

[Service]
Type=oneshot
WorkingDirectory=/path/to/armenian-corpus-core
ExecStart=/usr/bin/python -m scraping.runner run --config config/settings.yaml --only cleaning
StandardOutput=append:data/logs/cleaning.log
StandardError=append:data/logs/cleaning.log
```

### 5. Augmentation service

`~/.config/systemd/user/armenian-corpus-augmentation.service`:

```ini
[Unit]
Description=Armenian corpus augmentation
After=network.target mongod.service

[Service]
Type=oneshot
WorkingDirectory=/path/to/armenian-corpus-core
ExecStart=/usr/bin/python -m augmentation.runner run
StandardOutput=append:data/logs/augmentation.log
StandardError=append:data/logs/augmentation.log
```

### 6. Book catalog service

`~/.config/systemd/user/armenian-corpus-book-catalog.service`:

```ini
[Unit]
Description=Armenian corpus book catalog
After=network.target mongod.service

[Service]
Type=oneshot
WorkingDirectory=/path/to/armenian-corpus-core
ExecStart=/usr/bin/python -m ingestion.discovery.book_inventory_runner --config config/settings.yaml --worldcat --scan-mongodb
StandardOutput=append:data/logs/book_inventory.log
StandardError=append:data/logs/book_inventory.log
```

### 7. Author research service

`~/.config/systemd/user/armenian-corpus-author-research.service`:

```ini
[Unit]
Description=Armenian corpus author research
After=network.target mongod.service

[Service]
Type=oneshot
WorkingDirectory=/path/to/armenian-corpus-core
ExecStart=/usr/bin/python -m ingestion.research_runner --config config/settings.yaml
StandardOutput=append:data/logs/author_research.log
StandardError=append:data/logs/author_research.log
```

### 8. Enable timers

```bash
# Replace /path/to/armenian-corpus-core with actual path
mkdir -p ~/.config/systemd/user
# Copy service and timer files, then:
systemctl --user daemon-reload
systemctl --user enable armenian-corpus-scraping-weekly.timer
systemctl --user enable armenian-corpus-scraping-daily.timer
systemctl --user start armenian-corpus-scraping-weekly.timer
systemctl --user start armenian-corpus-scraping-daily.timer
# Add more timers for cleaning, augmentation, book catalog, author research as needed
```

## Ingestion Before Scraping

If you have cached JSONL in `data/raw/` and want to load it into MongoDB before scraping:

```bash
# (Removed) JSONL ingestion step no longer supported: run_ingestion has been removed.
```

Add to cron or a systemd service if you run ingestion before scraping.
