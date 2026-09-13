# Dynamic Crawl Frequency Adjustment

This document describes the dynamic crawl frequency adjustment system for the bid crawler.

## Overview

The system automatically adjusts crawl intervals based on success rates per category and priority level. Higher success rates result in shorter intervals (more frequent crawling), while lower success rates result in longer intervals (less frequent crawling) to reduce load on failing sources.

## Components

### 1. CrawlerSchedule Model (`database/models/crawler_schedule.py`)

Stores the crawl schedule configuration for each category/priority combination.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| category_id | Integer | Foreign key to agency_categories |
| priority_level | Integer | Priority level (1-5) |
| base_interval_seconds | Integer | Base crawl interval in seconds |
| current_interval_seconds | Integer | Current adjusted interval in seconds |
| success_rate | Float | Current success rate (0.0-1.0) |
| last_updated | DateTime | Last update timestamp |

### 2. Adjustment Script (`scripts/adjust_crawl_frequency.py`)

Calculates success rates and adjusts intervals accordingly.

**Algorithm:**
```
new_interval = base_interval * (target_success_rate / actual_success_rate)
```

- Target success rate: 95% (0.95)
- Min interval: 300 seconds (5 minutes)
- Max interval: 86400 seconds (24 hours)

**Default base intervals by priority:**
- Priority 1: 1800s (30 min)
- Priority 2: 3600s (1 hour)
- Priority 3: 7200s (2 hours)
- Priority 4: 14400s (4 hours)
- Priority 5: 28800s (8 hours)

**Usage:**
```bash
python scripts/adjust_crawl_frequency.py
```

### 3. Report Script (`scripts/report_crawl_success.py`)

Generates success rate reports.

**Usage:**
```bash
# Console output
python scripts/report_crawl_success.py

# JSON output
python scripts/report_crawl_success.py --json

# File output
python scripts/report_crawl_success.py -o report.txt

# Custom lookback period
python scripts/report_crawl_success.py --hours 48
```

## Scheduling

### Cron Example

Add to crontab for automatic adjustment every hour:

```bash
# Adjust frequencies hourly
0 * * * * cd /path/to/project && PYTHONPATH=. python scripts/adjust_crawl_frequency.py >> /var/log/crawl_adjust.log 2>&1

# Generate daily report
0 6 * * * cd /path/to/project && PYTHONPATH=. python scripts/report_crawl_success.py -o /var/log/crawl_report_$(date +\%Y\%m\%d).txt
```

### Systemd Timer (Alternative)

Create `/etc/systemd/system/crawl-adjust.timer`:
```ini
[Unit]
Description=Run crawl frequency adjustment hourly

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
```

Create `/etc/systemd/system/crawl-adjust.service`:
```ini
[Unit]
Description=Crawl frequency adjustment

[Service]
Type=oneshot
WorkingDirectory=/path/to/project
Environment=PYTHONPATH=.
ExecStart=/usr/bin/python scripts/adjust_crawl_frequency.py
```

Then enable:
```bash
systemctl enable --now crawl-adjust.timer
```

## Algorithm Details

### Success Rate Calculation

Success rate is calculated from:
1. **CrawlLog** table (primary) - recent crawl attempts with status
2. **BackfillJob** table (fallback) - backfill job statuses

Time window: Last 24 hours (configurable)

### Interval Adjustment Formula

```
ratio = target_success_rate / actual_success_rate
new_interval = base_interval * ratio
new_interval = clip(new_interval, MIN_INTERVAL, MAX_INTERVAL)
```

Examples:
- Success rate 100% → ratio = 0.95 → interval = 95% of base
- Success rate 95% → ratio = 1.0 → interval = base
- Success rate 50% → ratio = 1.9 → interval = 190% of base (capped at max)
- Success rate 0% → interval doubles (capped at max)

## Integration

### Using in Crawlers

```python
from database.engine import get_session
from database.models import CrawlerSchedule, Agency

def get_crawl_interval(agency: Agency) -> int:
    """Get the current crawl interval for an agency."""
    with get_session() as session:
        schedule = session.query(CrawlerSchedule).filter(
            CrawlerSchedule.category_id == agency.category_id,
            CrawlerSchedule.priority_level == agency.priority_level
        ).first()
        return schedule.current_interval_seconds if schedule else 3600
```

### Monitoring

The system exposes metrics via the report script. Key metrics to monitor:
- Overall success rate
- Per-category success rates
- Interval changes over time
- Number of schedules at min/max bounds

## Configuration

Environment variables:
- `DATABASE_URL` - Database connection string (default: sqlite:///./bids_system.db)
- `LOOKBACK_HOURS` - Hours to look back for success rate (default: 24)
- `TARGET_SUCCESS_RATE` - Target success rate (default: 0.95)
- `MIN_INTERVAL` - Minimum interval in seconds (default: 300)
- `MAX_INTERVAL` - Maximum interval in seconds (default: 86400)

## Troubleshooting

### No data in tables
If CrawlLog and BackfillJob tables are empty, success rates default to 100% and intervals are set to 95% of base.

### Intervals not changing
Check that:
1. CrawlLog entries have proper status values ("success" or "failed")
2. Agency records have correct category_id and priority_level
3. Adjustment script runs regularly

### Database errors
Check DATABASE_URL and ensure migrations are applied:
```bash
alembic upgrade head
```