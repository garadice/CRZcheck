# CRZ Risk & Quality Monitor — Production Deployment Checklist

Pre-flight checklist before going live. Every item must be resolved or explicitly
accepted before production deployment.

---

## 1. Environment Configuration

### 1.1 Settings via Environment Variables

All settings in `app/settings.py` are loaded via `pydantic-settings` from env vars
(with `.env` file fallback). The following variables **must** be set in production:

| Variable | Default | Production value | Required |
|---|---|---|---|
| `DATABASE_URL` | `""` (empty) | `postgresql://crz:<strong-password>@<host>:5432/crz_monitor` | YES |
| `APP_ENV` | `development` | `production` | YES |
| `LOG_LEVEL` | `INFO` | `INFO` or `WARNING` | recommended |
| `CRZ_EXPORT_BASE_URL` | `https://www.crz.gov.sk/export` | same | no |
| `CRZ_ROLLING_WINDOW_DAYS` | `90` | `90` | no |
| `CRZ_RATE_LIMIT_DAY_SECONDS` | `2.0` | `2.0` | no |
| `CRZ_RATE_LIMIT_NIGHT_SECONDS` | `0.4` | `0.4` | no |
| `RAW_DATA_DIR` | `data/raw` | persistent volume path | no |
| `SAMPLE_DATA_DIR` | `data/sample` | — (dev only) | no |

- [ ] **DATABASE_URL** set to production PostgreSQL with a strong, unique password
- [ ] **APP_ENV** set to `production` (disables SQLAlchemy echo logging)
- [ ] **LOG_LEVEL** set appropriately (INFO for initial launch, WARNING later)
- [ ] `.env` file is **not** committed to version control (confirmed in `.gitignore`)
- [ ] `.env.example` is complete and matches current `app/settings.py` fields

### 1.2 Missing / Unhandled Cases

- [ ] **DATABASE_URL not set**: `database_url` defaults to empty string `""`.
  SQLAlchemy will raise `ArgumentError` on engine creation. This is a hard crash —
  acceptable for production (fail-fast), but add a startup validation check if desired.
- [ ] **CRZ API unreachable**: `CRZDownloader` uses `httpx.Client(timeout=30.0)` with
  3 retries and exponential backoff on 5xx/transport errors. After all retries, the
  individual date is logged as `FAILED` and ingestion continues to the next date.
  The run still completes with status `"completed"`. **Action item**: consider adding
  a "partial failure" status or alerting when any date fails.
- [ ] No `SECRET_KEY` or `ENCRYPTION_KEY` exists — not needed yet since there is no
  authentication. If auth is added later, this must be addressed.

### 1.3 `.env.example` Completeness

Current `.env.example` covers all fields in `settings.py`. No missing variables.

---

## 2. Process Management

### 2.1 Ingestion Pipeline

The ingestion pipeline (`python -m app.ingestion.jobs`) downloads 90 days of CRZ
exports sequentially with rate limiting. Estimated runtime: 4–8 hours for initial
load, ~30 min for daily incremental.

- [ ] **Scheduler configured** — choose one:
  - [ ] Systemd timer (recommended for single-host deployment)
  - [ ] Cron job (simpler, less control over overlap)
  - [ ] Celery / external orchestrator (for distributed setups)
- [ ] **Schedule time** — recommend 02:00–06:00 CET (nighttime rate limit is 0.4s
  vs 2.0s daytime, 5x faster downloads)
- [ ] **Lock mechanism** — `acquire_ingestion_lock()` in `app/db/repository.py:245`
  prevents concurrent runs. Stale runs (>6h) are auto-cleaned. This is sufficient
  for single-process scheduling.
- [ ] **Overlap protection** — scheduler must not start a new run if previous is still
  running. The lock handles this, but the scheduler should also have `ExecStartPre`
  or flock-based guarding.
- [ ] **Timeout** — no global timeout on ingestion. Add a systemd `TimeoutStartSec=4h`
  or similar wrapper.

### 2.2 Dashboard (Streamlit)

- [ ] **Run method** — choose one:
  - [ ] Systemd service running `streamlit run app/dashboard/Home.py --server.port 8501 --server.address 127.0.0.1`
  - [ ] Docker container
  - [ ] Direct invocation (not recommended for production)
- [ ] **Streamlit config** — set via env vars or `.streamlit/config.toml`:
  - [ ] `SERVER_HEADLESS=true`
  - [ ] `SERVER_ENABLE_CORS=false` (if behind reverse proxy)
  - [ ] `SERVER_ENABLE_XSRF_PROTECTION=true`
  - [ ] `BROWSER_GATHER_USAGE_STATS=false`
- [ ] **Auto-restart** — systemd `Restart=on-failure` or Docker `restart: unless-stopped`
- [ ] **Resource limits** — Streamlit can consume significant memory with large datasets.
  Set `MemoryMax=1G` in systemd or `mem_limit` in Docker.

### 2.3 Database

- [ ] **PostgreSQL 16** running (docker-compose provides this for dev)
- [ ] **Port binding** — `docker-compose.yml` binds to `127.0.0.1:5433`. Production
  should use a non-default port or Unix socket, and never expose to 0.0.0.0.
- [ ] **shm_size** set to `256m` in compose — verify this is sufficient for production workload
- [ ] **Connection pool** — SQLAlchemy pool_size=5, max_overflow=10 (set in both
  `app/db/session.py` and `app/dashboard/components/connection.py`). Adequate for
  single-dashboard + ingestion concurrent usage.

### 2.4 Crash Recovery

- [ ] **Ingestion crashes mid-run**: The `acquire_ingestion_lock()` system creates an
  `IngestionRun` row with `status="running"`. If the process dies, the next run's
  stale-run cleanup (runs older than 6h) will mark it as `failed`. Contracts already
  committed per-date are safe (each date commits independently at `jobs.py:91`).
- [ ] **Dashboard crashes**: Streamlit is stateless — restart recovers fully. User
  sessions are lost but no data is at risk.
- [ ] **Database crashes**: PostgreSQL WAL + `restart: unless-stopped` in Docker
  handles recovery. Verify `pgdata` volume is on persistent storage.

---

## 3. Data Management

### 3.1 Rolling Window

- [ ] **90-day window is for ingestion only** — `get_date_range()` in `jobs.py:25`
  generates dates for the last 90 days and re-downloads/updates them. It does NOT
  delete data older than 90 days. Data accumulates indefinitely.
- [ ] **Purge policy needed** — decide whether to:
  - [ ] Keep all historical data (recommended for trend analysis)
  - [ ] Add a periodic cleanup job to purge contracts with `source_export_date`
    older than the rolling window
- [ ] If purging: add a cleanup script and schedule it (monthly cron)

### 3.2 Database Size Estimation

- ~2,700 contracts/day x 90 days = ~243,000 contracts in rolling window
- Each contract: ~2-5 KB metadata + version history + flags
- **Estimated steady-state size**: 2–5 GB (contracts + versions + flags)
- With attachments metadata and organization/supplier tables: add 1–2 GB
- **Total estimate**: 3–7 GB at steady state, growing slowly after initial 90 days
- [ ] **Storage provisioned** — ensure at least 20 GB for database volume
- [ ] **Growth monitoring** — track `pg_database_size('crz_monitor')` weekly

### 3.3 Backups

- [ ] **pg_dump cron** configured:
  ```bash
  # Daily full backup, keep 30 days
  0 3 * * * pg_dump -Fc crz_monitor > /backups/crz_monitor_$(date +\%Y\%m\%d).dump
  0 4 * * * find /backups -name "crz_monitor_*.dump" -mtime +30 -delete
  ```
- [ ] **Backup location** — separate volume or remote storage (S3, rsync to another host)
- [ ] **Restore test** — perform at least one test restore before going live
- [ ] **WAL archiving** — consider enabling if point-in-time recovery is required

---

## 4. Monitoring & Alerting

### 4.1 Health Check

- [ ] **No built-in health endpoint** — Streamlit does not provide a `/healthz`.
  Options:
  - [ ] Add a minimal Streamlit page that returns 200 (e.g., `app/dashboard/pages/0_Health.py`)
  - [ ] Use a TCP check on port 8501
  - [ ] Use `curl -f http://localhost:8501/_stcore/health` (Streamlit 1.35+ has this)
- [ ] **Database health** — `pg_isready -U crz -d crz_monitor` (already in docker-compose
  healthcheck)

### 4.2 Data Freshness Detection

- [ ] Freshness check exists in `app/flags/freshness.py` — `check_data_freshness()`
  compares last successful `IngestionRun.finished_at` against `STALE_THRESHOLD_HOURS = 48`.
- [ ] Dashboard shows freshness banner on every page via `show_freshness_banner()`
- [ ] **External alert needed** — add a cron job or script that calls
  `check_data_freshness()` and sends an alert (email, Slack, etc.) if stale:
  ```python
  from app.db.session import get_session_factory
  from app.flags.freshness import check_data_freshness
  session = get_session_factory()()
  result = check_data_freshness(session)
  if result["status"] != "fresh":
      # send alert
  ```

### 4.3 Log Management

- [ ] **Ingestion logs** — `logging.basicConfig(level=logging.INFO)` in `jobs.py:160`.
  In production, configure proper log output:
  - [ ] Systemd captures stdout → `journalctl -u crz-ingestion`
  - [ ] Or redirect to file with logrotate
- [ ] **Dashboard logs** — Streamlit logs to stderr. Systemd captures these.
- [ ] **PostgreSQL logs** — docker-compose uses `json-file` driver with 10m max, 3 files.
  For production, consider forwarding to a log aggregator.
- [ ] **Log aggregation** — if centralized logging is available (Loki, ELK), configure
  forwarding for all three services.

### 4.4 Ingestion Failure Detection

- [ ] Monitor `ingestion_runs` table for runs with `status = 'failed'`
- [ ] Alert on:
  - [ ] No completed run in last 48 hours
  - [ ] Run with `status = 'running'` for > 6 hours (should be auto-cleaned, but verify)
  - [ ] Consecutive failed runs
- [ ] Monitor individual date failures within a run — currently logged as WARNING
  but not tracked in DB. Consider adding `raw_crz_exports` rows with `status = 'error'`.

---

## 5. Security

### 5.1 Dashboard Authentication

- [ ] **No authentication** — Streamlit has no built-in auth. The dashboard is open
  to anyone who can reach port 8501.
- [ ] **Action required** — choose one:
  - [ ] Reverse proxy with HTTP Basic Auth (nginx/Caddy)
  - [ ] Streamlit-Authenticator package (`streamlit-authenticator`)
  - [ ] OAuth2 proxy (e.g., `oauth2-proxy`) in front of Streamlit
  - [ ] VPN / network-level restriction
- [ ] **Minimum**: bind Streamlit to `127.0.0.1` only and use reverse proxy

### 5.2 Reverse Proxy

- [ ] **nginx or Caddy** configured in front of Streamlit:
  ```
  location / {
      proxy_pass http://127.0.0.1:8501;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_http_version 1.1;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection "upgrade";
  }
  ```
  WebSocket support is required for Streamlit live updates.

### 5.3 HTTPS

- [ ] TLS certificate configured (Let's Encrypt / certbot recommended)
- [ ] HSTS header set if serving publicly
- [ ] HTTP → HTTPS redirect

### 5.4 Network Security

- [ ] PostgreSQL port not exposed to internet (docker-compose already binds to `127.0.0.1`)
- [ ] Dashboard port (8501) not directly exposed — only via reverse proxy
- [ ] Firewall rules reviewed (ufw/iptables)
- [ ] `POSTGRES_PASSWORD` changed from default `crz_local` in production

### 5.5 Application Security

- [ ] SQL injection: SQLAlchemy ORM with parameterized queries — low risk
- [ ] User input sanitization: `_escape_ilike()` in `queries.py:49` escapes LIKE wildcards
- [ ] Rate limiting: no rate limiting on dashboard. Consider nginx `limit_req` if exposed
  publicly.
- [ ] CORS: disabled if behind reverse proxy (`SERVER_ENABLE_CORS=false`)

---

## 6. Backup & Recovery

### 6.1 Database Backup

- [ ] Daily `pg_dump -Fc` (custom format, compressible) scheduled
- [ ] Backups stored on separate disk/volume from database
- [ ] 30-day retention policy defined
- [ ] **Backup script** -- `scripts/backup.sh` automates pg_dump, validation, and cleanup:
  ```bash
  # Run backup manually
  make backup

  # Or schedule via cron:
  0 3 * * * cd /opt/crz-monitor && ./scripts/backup.sh
  ```
- [ ] **Restore script** -- `scripts/restore.sh` provides test and apply modes:
  ```bash
  # Test restore (non-destructive, validates row counts)
  make restore-test DUMP=backups/crz_monitor_20260517.dump

  # Production restore (destructive, requires confirmation)
  make restore DUMP=backups/crz_monitor_20260517.dump
  ```
- [ ] Backup script tested:

```bash
# Backup
docker exec crz_db pg_dump -U crz -Fc crz_monitor > /backups/crz_monitor_$(date +%Y%m%d).dump

# Restore (stop services first)
docker exec -i crz_db pg_restore -U crz -d crz_monitor -c < /backups/crz_monitor_20260517.dump
```

### 6.2 Configuration Backup

- [ ] `.env` file backed up securely (contains credentials)
- [ ] `alembic/versions/` tracked in git (already is)
- [ ] `docker-compose.yml` tracked in git
- [ ] Any reverse proxy configs backed up
- [ ] Any systemd unit files backed up

### 6.3 Recovery Procedure

1. Provision new host / restore VM
2. Clone repository
3. Restore `.env` file
4. Start PostgreSQL: `docker compose up -d db`
5. Run migrations: `alembic upgrade head`
6. Restore latest database backup if needed
7. Start ingestion service
8. Start dashboard service
9. Verify: check dashboard, run `check_data_freshness()`

### 6.4 Disaster Recovery

- [ ] RPO (Recovery Point Objective): 24 hours (daily backups)
- [ ] RTO (Recovery Time Objective): 2 hours (documented procedure)
- [ ] Recovery procedure tested end-to-end before production launch

---

## 7. Pre-Launch Verification

### 7.1 Smoke Tests

- [ ] Database migration runs cleanly: `alembic upgrade head`
- [ ] Initial ingestion completes successfully (test with 1-day window)
- [ ] Dashboard loads and shows data
- [ ] Flag evaluation produces expected results
- [ ] Data freshness banner displays correctly
- [ ] Search functionality works
- [ ] Export/download buttons work (if any)
- [ ] All dashboard pages load without errors

### 7.2 Performance

- [ ] Dashboard page load < 5 seconds with 250K contracts
- [ ] Ingestion completes within scheduled window
- [ ] Database queries use expected indexes (check with `EXPLAIN ANALYZE`)
- [ ] Memory usage within limits during full ingestion run
- [ ] Streamlit handles concurrent users (test with 2-3 simultaneous)

### 7.3 Documentation

- [ ] This checklist completed
- [ ] Operational runbook created (`docs/runbook.md`)
- [ ] Architecture diagram updated if changed
- [ ] Contact information for on-call documented

---

## Quick Reference: Production Checklist Summary

```
Environment
  [ ] DATABASE_URL set (non-empty, strong password)
  [ ] APP_ENV=production
  [ ] .env not in git

Process Management
  [ ] Ingestion scheduled (systemd timer or cron, nighttime)
  [ ] Dashboard running as service
  [ ] Auto-restart configured

Database
  [ ] PostgreSQL port not publicly exposed
  [ ] Password changed from default
  [ ] Daily pg_dump configured
  [ ] Restore tested

Security
  [ ] Dashboard behind reverse proxy
  [ ] HTTPS configured
  [ ] Authentication enabled
  [ ] Firewall rules reviewed

Monitoring
  [ ] Health check endpoint reachable
  [ ] Freshness alerting configured
  [ ] Log forwarding configured
  [ ] Ingestion failure alerting configured
```
