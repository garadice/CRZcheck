# CRZ Risk & Quality Monitor — Session Context for Compaction

## Current State (2026-05-17)

### Project
- **Repo:** /mnt/data2/projects/CRZcheck
- **GitHub:** https://github.com/garadice/CRZcheck (6 commits pushed, live)
- **Git remote:** origin (PAT stored in local git config — rotate after session)
- **Venv:** .venv (Python 3.12.3, all deps installed)
- **Tests:** 302/302 passing, 84% coverage, ruff lint clean
- **No secrets in source code** — verified by security scan

### Completed Phases ✅
- **Phases 0-7:** MVP complete (parser, DB, ingestion, flags, dashboard, docs, pushed to GitHub)
- **Pre-Live Hardening:** Security, click-path audit, Docker, PostgreSQL patterns
- **Post-Live Hardening:** Advisory lock, batched flags, indexes, pinned deps, etc.
- **Post-Live Code Review:** 1C+2I fixed (deterministic hash, compound_severity, TransportError)
- **Backup Strategy:** scripts/backup.sh + restore.sh, Makefile targets, docs updated
- **Test Coverage:** 56% → 84% (302 tests, queries.py 100%, export 70%, download 83%)
- **Deployment Automation:** Streamlit config, Caddy reverse proxy, deploy script, smoke test

### Git History (6 commits on main)
```
df99b2f feat: production deployment automation — Streamlit config, Caddy, deploy script
a677ff6 feat: database backup strategy + test coverage 56% → 84%
afaf824 fix: code review fixes — deterministic lock hash, compound severity, redirect exception
0466e6a fix: post-live hardening — advisory lock, batched flags, security hardening
f433dd0 fix: pre-live hardening — security, bugs, Docker, docs
5f5ccfa feat: CRZ Risk & Quality Monitor — MVP release (Phases 1-6)
```

### Key Architecture
- **Docker PostgreSQL** on 127.0.0.1:5433 (container: crz_db, user: crz, db: crz_monitor)
- **Streamlit** on 127.0.0.1:8501 (headless, behind Caddy reverse proxy)
- **Caddy** on :80/:443 → automatic HTTPS (Let's Encrypt) + basic auth + security headers
- **Ingestion** runs as systemd timer (02:00 Europe/Bratislava, nighttime rate 0.4s)
- **Backup** via daily cron (03:00, pg_dump -Fc, 30-day retention)

### Deployment Files (all committed, ready for server)
- `.streamlit/config.toml` — production Streamlit config
- `.env.production.example` — env template with CHANGE_ME placeholders
- `deploy/Caddyfile` — Caddy config (crz.bacimo.net, basic auth, security headers)
- `deploy/install-caddy.sh` — install Caddy from Cloudsmith repo
- `deploy/caddy-setup.sh` — validate + deploy Caddyfile
- `scripts/deploy.sh` — idempotent 10-step production deployment
- `scripts/smoke-test.sh` — 6-check post-deploy verification
- `scripts/backup.sh` — pg_dump + validate + retention cleanup
- `scripts/restore.sh` — --test (safe) and --apply (production) modes
- `docker-compose.prod.yml` — production overrides (127.0.0.1:5433, separate password)

### Key Technical Decisions
- Port 5433 (system PG 5432 used by n8n — NO CONFLICT confirmed by user)
- `database_url` default is empty string (no hardcoded credentials)
- Advisory lock uses `hashlib.sha256()` (NOT `hash()` — randomized per session!)
- `DateTime(timezone=True)` via migration 002
- XXE hardened XML parser, 100MB ZIP bomb limit
- Redirect validation: crz.gov.sk domain check, raises TransportError
- Dependencies pinned with upper bounds
- docker-compose.prod.yml keeps 127.0.0.1:5433 port mapping (Streamlit runs outside Docker)
- Deploy script does NOT install [dev] extras in production
- Deploy script wraps alembic in `cd` for correct CWD
- Caddy domain parameterized in smoke test via $CADDY_DOMAIN

### Source Code Structure
- `app/settings.py` — Pydantic settings (database_url="", sql_echo=False)
- `app/db/session.py` — Singleton engine (connect_timeout=10)
- `app/db/models.py` — 13 ORM models (Contract PK=crz_contract_id)
- `app/db/repository.py` — CRUD layer, advisory lock (sha256 hash)
- `app/ingestion/crz/parser.py` — Streaming XML parser (XXE hardened)
- `app/ingestion/crz/download.py` — HTTP client (redirect validation)
- `app/ingestion/jobs.py` — Ingestion orchestrator (33% coverage — hard to test end-to-end)
- `app/flags/evaluate.py` — Flag checkers, compound_severity, batched evaluation
- `app/flags/freshness.py` — check_data_freshness (timezone-safe)
- `app/dashboard/components/` — connection, queries (100%), filters, export (70%)
- `app/dashboard/` — Home.py + 6 pages (Streamlit, excluded from coverage)
- `docs/master-plan.md` — THE implementation bible (v2.0, 1,014 lines)
- `docs/runbook.md` — Operational runbook (daily/weekly/monthly + systemd units)
- `docs/deployment-checklist.md` — Pre-flight deployment checklist

### Coverage Status
| Module | Coverage | Notes |
|--------|----------|-------|
| queries.py | 100% | 77 tests |
| evaluate.py | 100% | 44 tests |
| models.py | 100% | 15 tests |
| flags_catalog.py | 100% | 9 tests |
| entities.py | 100% | 26 tests |
| links.py | 100% | 5 tests |
| parser.py | 96% | 21 tests |
| freshness.py | 95% | 7 tests |
| definitions.py | 94% | — |
| settings.py | 95% | — |
| cleaning.py | 91% | 40 tests |
| export.py | 70% | 9 tests (st.download_button untestable) |
| repository.py | 86% | 23 tests |
| download.py | 83% | 17 tests |
| session.py | 53% | singleton hard to test |
| jobs.py | 33% | end-to-end, needs live DB |
| Dashboard pages | 0% | Streamlit rendering, excluded from coverage |
| **Total** | **84%** | **302 tests** |

### What's Next — Production Deployment
Server setup on Hetzner (*.bacimo.net):
1. Resolve any port issues (user confirmed NO 5433 conflict)
2. Run `sudo bash scripts/deploy.sh` — sets up user, clone, venv, DB, systemd, cron
3. Edit `.env` with strong POSTGRES_PASSWORD
4. `systemctl start crz-dashboard`
5. Install Caddy: `bash deploy/install-caddy.sh`
6. Generate bcrypt hash: `caddy hash-password --plaintext 'password'`
7. Edit Caddyfile, replace `<BCRYPT_HASH>` and domain
8. Deploy Caddyfile: `bash deploy/caddy-setup.sh`
9. First ingestion: `sudo -u crz /opt/crz-monitor/.venv/bin/python -m app.ingestion.jobs`
10. Run flag evaluation after ingestion
11. Smoke test: `bash scripts/smoke-test.sh`
12. Verify dashboard at https://crz.bacimo.net

### Potential Future Enhancements
- FastAPI REST API layer
- PDF attachment OCR + text extraction
- Natural person detection enrichment
- Organization/supplier relationship graph
- Health check alerting (email/Slack on freshness failure)
- Log aggregation (journalctl sufficient for now)

### Instincts Learned (6 global)
1. `deterministic-hash-for-cross-process` — Never use Python hash() for cross-process IDs
2. `dialect-aware-postgresql-features` — Detect dialect for PG-specific features in SQLite tests
3. `raise-specific-httpx-exceptions` — Raise TransportError not base HTTPError
4. `reuse-existing-utility-functions` — Search codebase before writing inline logic
5. `verify-remaining-items-already-done` — Check current file state before fixing "remaining" items
6. `no-secrets-in-session-context` — Never put secrets in docs that get committed
