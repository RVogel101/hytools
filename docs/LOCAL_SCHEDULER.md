# Local Scheduler Setup (Phase 2)

Run the pipeline continuously on your machine with retry logic and alerting.

## Quick Start

```bash
# Foreground — runs every 6 hours
python -m hytools.ingestion.runner schedule

# Custom interval (every 2 hours)
python -m hytools.ingestion.runner schedule --interval 7200

# With JSONL alert file
python -m hytools.ingestion.runner schedule --alert-file data/logs/alerts.jsonl

# Only scraping stages, skip OCR
python -m hytools.ingestion.runner schedule --only wikipedia archive_org news --skip ocr_ingest

# Test with 1 tick
python -m hytools.ingestion.runner schedule --max-ticks 1
```

## Systemd Service (Linux)

```ini
# /etc/systemd/system/hytools-pipeline.service
[Unit]
Description=Western Armenian Corpus Pipeline Scheduler
After=network.target mongod.service

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/hytools
ExecStart=/path/to/conda/envs/hytools/bin/python -m hytools.ingestion.runner schedule \
    --interval 21600 \
    --alert-file data/logs/alerts.jsonl \
    --config config/settings.yaml
Restart=on-failure
RestartSec=60
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable hytools-pipeline
sudo systemctl start hytools-pipeline
sudo journalctl -u hytools-pipeline -f
```

## Cron Alternative (Linux/Mac)

```cron
# Run pipeline every 6 hours
0 */6 * * * cd /path/to/hytools && /path/to/python -m hytools.ingestion.runner run --config config/settings.yaml >> data/logs/cron.log 2>&1
```

## Windows Task Scheduler

```powershell
# Create scheduled task — runs every 6 hours
$action = New-ScheduledTaskAction `
    -Execute "C:\path\to\conda\envs\hytools\python.exe" `
    -Argument "-m hytools.ingestion.runner run --config config\settings.yaml" `
    -WorkingDirectory "C:\path\to\hytools"

$trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 6) -At "00:00" -Once

Register-ScheduledTask -TaskName "HytoolsPipeline" -Action $action -Trigger $trigger
```

## State and Monitoring

### Scheduler State

The scheduler saves state to `data/logs/scheduler_state.json`:

```json
{
  "last_tick_iso": "2026-03-06T12:00:00+00:00",
  "last_success_iso": "2026-03-06T12:00:00+00:00",
  "total_ticks": 42,
  "stages": {
    "wikipedia": {
      "name": "wikipedia",
      "last_status": "ok",
      "consecutive_failures": 0,
      "total_runs": 42,
      "total_failures": 1
    }
  }
}
```

### Check Status

```bash
python -m hytools.ingestion.runner status
```

Shows: PID, scheduler ticks, last success, failing stages.

### Alerts

Alerts are emitted to the log and optionally to a JSONL file:

| Alert | Severity | Trigger |
|-------|----------|---------|
| Stage consecutive failures | warning | Any stage fails 5+ times in a row |
| No ingestion success | critical | No stage succeeds within alert window (default: 24h) |

Alert JSONL format:
```json
{"severity": "critical", "message": "No successful ingestion for 25.3 hours", "timestamp_iso": "...", "context": {...}}
```

## Retry Logic

Each stage gets up to 3 retries with exponential backoff:

| Attempt | Delay |
|---------|-------|
| 1st retry | 30s |
| 2nd retry | 60s |
| 3rd retry | 120s |

Retries handle transient errors (network timeouts, 429/5xx responses).
Permanent failures (missing config, import errors) exhaust retries quickly.

## Configuration

All scheduler settings can be overridden via CLI flags or `config/settings.yaml`:

```yaml
scheduler:
  interval_seconds: 21600     # 6 hours
  alert_window_seconds: 86400 # 24 hours
  max_retries: 3
```
