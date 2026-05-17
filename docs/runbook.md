# CRZ Risk & Quality Monitor — Operational Runbook

Daily and weekly operational procedures for maintaining the CRZ Monitor
in production.

---

## Service Overview

| Service | Command | Port | Purpose |
|---|---|---|---|
| PostgreSQL 16 | `docker compose up -d db` | 5433 (localhost) | Data storage |
| CRZ Ingestion | `python -m app.ingestion.jobs` | — | Download & process CRZ data |
| Streamlit Dashboard | `streamlit run app/dashboard/Home.py` | 8501 (localhost) | Web UI |

### Key Files

| Path | Description |
|---|---|
| `app/settings.py` | All configuration (env vars) |
| `app/ingestion/jobs.py` | Ingestion pipeline entry point |
| `app/flags/freshness.py` | Data freshness check (48h threshold) |
| `app/flags/evaluate.py` | Risk flag evaluation engine |
| `app/db/repository.py` | Ingestion lock & stale-run cleanup |
| `alembic/versions/` | Database migration history |

### Database Tables (key ones)

| Table | Purpose |
|---|---|
| `contracts` | Core contract data (~250K rows at steady state) |
| `contract_versions` | Version history per contract per export date |
| `ingestion_runs` | Ingestion run log (status, timing, counts) |
| `contract_risk_flags` | Flag evaluation results per contract |
| `risk_flags` | Flag definitions (seeded, ~6 entries) |
| `organizations` | Deduplicated buyer entities |
| `suppliers` | Deduplicated supplier entities |
| `raw_crz_exports` | Download tracking per date |

---

## Data Recovery

All data in this project comes from the public CRZ API. There are no user
accounts, no user-generated content, and no irreplaceable data. If the database
is corrupted or lost, it can be rebuilt from scratch:

```bash
# Full rebuild — re-ingest 90 days from CRZ API (~4–8 hours)
docker compose down -v          # remove old data
docker compose up -d db         # start fresh PostgreSQL
alembic upgrade head            # create schema
python -m app.ingestion.jobs    # re-ingest everything
```

Manual backups are available if you want a faster recovery (saves the re-ingestion time):

```bash
# Create a backup manually
make backup

# Restore from backup
make restore DUMP=backups/crz_monitor_20260517.dump
```

But automated daily backups are not configured — the CRZ API is the backup.

---

## Daily Operations

### 1. Check Ingestion Health (5 min)

**When**: Morning, before 09:00

```bash
# Check if ingestion ran last night
sudo journalctl -u crz-ingestion --since "today 02:00" --until "today 07:00" | tail -50
```

Or query the database directly:

```sql
SELECT id, status, started_at, finished_at,
       records_seen, records_inserted, records_updated,
       error_message
FROM ingestion_runs
ORDER BY started_at DESC
LIMIT 5;
```

**Expected result**: One completed run with `status = 'completed'`, `finished_at`
within the last 24 hours.

**If no run completed**:
1. Check if the service/timer fired: `systemctl status crz-ingestion.timer`
2. Check for errors in logs
3. Run ingestion manually: `make ingest` or `python -m app.ingestion.jobs`
4. Investigate root cause (see Incident Response below)

**If run has `status = 'failed'`**:
1. Read `error_message` from `ingestion_runs`
2. Check if it's a transient error (network, CRZ API down)
3. Re-run ingestion manually if transient
4. Escalate if persistent (see Incident Response)

### 2. Check Data Freshness (2 min)

**When**: Morning, after checking ingestion

Open the dashboard → **Stav dat** page, or run:

```python
python -c "
from app.db.session import get_session_factory
from app.flags.freshness import check_data_freshness
session = get_session_factory()()
result = check_data_freshness(session)
print(result)
session.close()
"
```

**Expected**: `status: "fresh"`, `hours_since` < 24

**If `status: "stale"` (hours_since > 48)**:
1. Check ingestion history for failures
2. Run manual ingestion
3. Verify CRZ API is accessible: `curl -I https://www.crz.gov.sk/export/today.zip`

### 3. Quick Dashboard Smoke Test (2 min)

**When**: Morning

1. Open `https://<dashboard-url>/` in browser
2. Verify overview stats are displayed (non-zero contract counts)
3. Verify freshness banner shows green (not stale warning)
4. Click through each page: Oznamy, Detail zmluvy, Organizacie, Dodavatelia, Stav dat
5. Each page should load within 5 seconds

---

## Weekly Operations

### 1. Database Size Check (5 min)

**When**: Monday

```sql
SELECT pg_size_pretty(pg_database_size('crz_monitor')) AS db_size;
```

Also check individual table sizes:

```sql
SELECT relname AS table,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;
```

**Expected**: 3–7 GB at steady state. If growing rapidly (>1 GB/week after initial load),
investigate whether `contract_versions` or `raw_crz_exports` are accumulating excessively.

### 2. Ingestion Run History Review (5 min)

**When**: Monday

```sql
SELECT
    date(started_at) AS run_date,
    status,
    records_seen,
    records_inserted,
    records_updated,
    EXTRACT(EPOCH FROM (finished_at - started_at)) / 60 AS duration_minutes
FROM ingestion_runs
WHERE started_at > NOW() - INTERVAL '7 days'
ORDER BY started_at;
```

**Look for**:
- All daily runs showing `completed` status
- Reasonable duration (30 min – 4 hours)
- Non-zero `records_seen` (CRZ adds new contracts daily)
- Consistent `records_inserted` (spikes may indicate re-processing)

### 3. Log Review (10 min)

**When**: Monday

```bash
# Check for errors in ingestion logs
sudo journalctl -u crz-ingestion --since "7 days ago" | grep -i "FAILED\|error\|traceback" | tail -20

# Check dashboard errors
sudo journalctl -u crz-dashboard --since "7 days ago" | grep -i "error\|traceback" | tail -20

# Check PostgreSQL logs
docker logs crz_db --since "168h" 2>&1 | grep -i "error\|fatal\|panic" | tail -20
```

### 4. Stale Data Cleanup Check (5 min)

**When**: Monday

Verify that no stale ingestion runs remain:

```sql
SELECT id, status, started_at, finished_at, error_message
FROM ingestion_runs
WHERE status = 'running'
ORDER BY started_at;
```

**Expected**: Empty result. If not, the stale-run cleanup (6h threshold in
`acquire_ingestion_lock()`) should have caught these. If it hasn't, manually
mark them as failed:

```sql
UPDATE ingestion_runs
SET status = 'failed',
    finished_at = NOW(),
    error_message = 'Manual cleanup: stale run'
WHERE status = 'running'
  AND started_at < NOW() - INTERVAL '6 hours';
```

---

## Monthly Operations

### 1. Database Maintenance (15 min)

**When**: First weekend of the month

```sql
-- Update table statistics
ANALYZE;

-- Reclaim space from updates/deletes
VACUUM;

-- Check for index bloat
SELECT schemaname, relname, pg_size_pretty(pg_relation_size(relid)) AS size,
       n_dead_tup
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 10;
```

If `n_dead_tup` is high (>100K) on any table, run `VACUUM FULL <table>` during
a maintenance window (requires exclusive lock, table is unavailable during operation).

### 2. Security Review (15 min)

**When**: Monthly

- [ ] Check PostgreSQL password still strong (not leaked)
- [ ] Review access logs for unauthorized dashboard access attempts
- [ ] Verify TLS certificate not expiring soon (`certbot certificates`)
- [ ] Check for package updates: `pip audit` or review `pyproject.toml` deps
- [ ] Review docker image updates: `docker compose pull`
- [ ] Verify firewall rules unchanged

### 3. Disk Space Check (5 min)

**When**: Monthly

```bash
# Overall disk usage
df -h /var/lib/docker/volumes/  # Docker volumes

# Docker volume sizes
docker system df -v
```

**If disk usage > 80%**:
1. Clean old raw data files in `data/raw/`
2. Consider `VACUUM FULL` on bloated tables
3. Provision additional storage

### 4. Raw Data Cleanup (5 min)

**When**: Monthly

Downloaded ZIP files accumulate in `data/raw/`. These are re-downloaded on each
ingestion run, so old files can be safely deleted:

```bash
# Show size of raw data
du -sh data/raw/
ls -lh data/raw/*.zip | wc -l

# Delete files older than 30 days (already re-downloaded during ingestion)
find data/raw/ -name "*.zip" -mtime +30 -delete
```

---

## Incident Response

### Incident: Ingestion Fails Consecutively

**Symptoms**: Multiple `ingestion_runs` with `status = 'failed'`, stale data banner
on dashboard.

**Steps**:
1. Check the error message:
   ```sql
   SELECT id, started_at, error_message FROM ingestion_runs
   WHERE status = 'failed' ORDER BY started_at DESC LIMIT 3;
   ```
2. **CRZ API unreachable**: Verify `curl -I https://www.crz.gov.sk/export/`. If CRZ
   is down, wait and retry. No action needed on our side.
3. **Database connection error**: Check PostgreSQL is running (`docker ps`), check
   `DATABASE_URL` in `.env`, check connection: `psql $DATABASE_URL -c "SELECT 1"`.
4. **Schema change in CRZ export**: If XML parsing fails, check `app/ingestion/crz/parser.py`
   against a sample download. May need code update.
5. **Disk full**: Check `df -h`. Free space by cleaning raw data.
6. After fixing, run manual ingestion: `make ingest`
7. Verify dashboard shows fresh data.

### Incident: Dashboard Unreachable

**Symptoms**: Browser shows connection refused or 502.

**Steps**:
1. Check Streamlit process:
   ```bash
   sudo systemctl status crz-dashboard
   ```
2. If process is dead, restart:
   ```bash
   sudo systemctl restart crz-dashboard
   ```
3. Check logs for crash cause:
   ```bash
   sudo journalctl -u crz-dashboard --since "1 hour ago"
   ```
4. Check database connectivity from dashboard host:
   ```bash
   psql $DATABASE_URL -c "SELECT 1"
   ```
5. Check reverse proxy (Caddy) is running:
   ```bash
   sudo systemctl status caddy
   ```

### Incident: Database Corruption / Data Loss

**Symptoms**: Queries return unexpected results, missing data, or errors.

**Steps**:
1. **Stop all services immediately**:
   ```bash
   sudo systemctl stop crz-ingestion
   sudo systemctl stop crz-dashboard
   ```
2. Assess extent of damage:
   ```sql
   SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY relname;
   ```
3. **If you have a manual backup**, restore it:
   ```bash
   make restore DUMP=backups/crz_monitor_YYYYMMDD.dump
   ```
4. **If no backup** (or backup is also corrupt), rebuild from scratch:
   ```bash
   docker compose down -v
   docker compose up -d db
   alembic upgrade head
   python -m app.ingestion.jobs    # re-ingest from CRZ (~4-8 hours)
   ```
5. Start services:
   ```bash
   sudo systemctl start crz-dashboard
   sudo systemctl start crz-ingestion  # or wait for timer
   ```
6. Verify dashboard shows expected data.

### Incident: Disk Space Exhaustion

**Symptoms**: Services crash, "no space left on device" errors.

**Steps**:
1. Identify what's consuming space:
   ```bash
   du -sh /var/lib/docker/volumes/*
   du -sh data/raw/
   ```
2. **Immediate relief**:
   ```bash
   # Clean old raw ZIP files
   find data/raw/ -name "*.zip" -mtime +7 -delete

   # Docker cleanup
   docker system prune -f
   ```
3. **Long-term**: Increase disk size or set up raw data cleanup cron.

### Incident: Stale Ingestion Run (Running > 6h)

**Symptoms**: Dashboard shows stale data, ingestion_runs has a `running` entry
older than 6 hours.

**Steps**:
1. The stale-run cleanup in `acquire_ingestion_lock()` handles this automatically
   on the next ingestion start. If no new ingestion is scheduled:
   ```sql
   SELECT id, started_at FROM ingestion_runs WHERE status = 'running';
   ```
2. Manually mark as failed:
   ```sql
   UPDATE ingestion_runs
   SET status = 'failed',
       finished_at = NOW(),
       error_message = 'Manual cleanup: stale run killed by operator'
   WHERE status = 'running' AND id = <run_id>;
   ```
3. Start a new ingestion run: `make ingest`

---

## Appendix: Useful Commands

### Ingestion

```bash
# Run full ingestion (90-day window)
make ingest

# Run with custom end date (for testing)
python -c "from app.ingestion.jobs import run_ingestion; from datetime import date; run_ingestion(date(2026, 5, 15))"
```

### Database

```bash
# Connect to database
psql $DATABASE_URL

# Run migrations
make migrate

# Check migration status
alembic current

# Database size
psql $DATABASE_URL -c "SELECT pg_size_pretty(pg_database_size('crz_monitor'));"

# Active connections
psql $DATABASE_URL -c "SELECT pid, state, query_start, query FROM pg_stat_activity WHERE datname='crz_monitor';"
```

### Docker

```bash
# Start/stop database
make db-up
make db-down

# View PostgreSQL logs
docker logs crz_db --tail 100 -f

# Check container status
docker compose ps
```

### Flag Evaluation

```python
# Run flag evaluation manually
python -c "
from app.db.session import get_session_factory
from app.flags.evaluate import run_flag_evaluation
from app.flags.flags_catalog import seed_flags

session = get_session_factory()()
seed_flags(session)
session.commit()
# Note: run_flag_evaluation requires a run_id from ingestion_runs
# Run ingestion first, then evaluate
session.close()
"
```

### Data Freshness

```python
python -c "
from app.db.session import get_session_factory
from app.flags.freshness import check_data_freshness
s = get_session_factory()()
print(check_data_freshness(s))
s.close()
"
```

### Cleanup Raw Data

```bash
# Show size of raw data
du -sh data/raw/

# Remove ZIP files older than 30 days
find data/raw/ -name "*.zip" -mtime +30 -ls
find data/raw/ -name "*.zip" -mtime +30 -delete
```

---

## Appendix: Recommended Systemd Units

### `/etc/systemd/system/crz-ingestion.service`

```ini
[Unit]
Description=CRZ Data Ingestion
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
User=crz
Group=crz
WorkingDirectory=/opt/crz-monitor
ExecStart=/opt/crz-monitor/.venv/bin/python -m app.ingestion.jobs
TimeoutStartSec=4h
Environment=APP_ENV=production
Environment=LOG_LEVEL=INFO
EnvironmentFile=/opt/crz-monitor/.env
```

### `/etc/systemd/system/crz-ingestion.timer`

```ini
[Unit]
Description=CRZ Daily Ingestion Timer

[Timer]
OnCalendar=*-*-* 02:00:00 Europe/Bratislava
RandomizedDelaySec=300
Persistent=true

[Install]
WantedBy=timers.target
```

### `/etc/systemd/system/crz-dashboard.service`

```ini
[Unit]
Description=CRZ Monitor Dashboard (Streamlit)
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=crz
Group=crz
WorkingDirectory=/opt/crz-monitor
ExecStart=/opt/crz-monitor/.venv/bin/streamlit run app/dashboard/Home.py \
    --server.port 8501 \
    --server.address 127.0.0.1 \
    --server.headless true \
    --browser.gatherUsageStats false
Restart=on-failure
RestartSec=10
MemoryMax=1G
Environment=APP_ENV=production
EnvironmentFile=/opt/crz-monitor/.env

[Install]
WantedBy=multi-user.target
```

### Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable crz-dashboard crz-ingestion.timer
sudo systemctl start crz-dashboard
sudo systemctl start crz-ingestion.timer
```
