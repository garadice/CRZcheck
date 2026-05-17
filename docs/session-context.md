# CRZ Risk & Quality Monitor — Session Context for Compaction

## Current State (2026-05-17)

### Project
- **Repo:** /mnt/data2/projects/CRZcheck
- **GitHub:** https://github.com/garadice/CRZcheck (2 commits pushed, live)
- **Git remote:** origin (PAT stored in local git config — rotate after session)
- **Venv:** .venv (Python 3.12.3, all deps installed)
- **Tests:** 202/202 passing, ruff lint clean
- **No secrets in source code** — verified by security scan
- **Live dashboard E2E tested** in browser (Home, Oznamy, Metodika, Stav dat all render)

### Completed Phases ✅
- **Phase 0:** Project setup (port 5433, 90-day window, all scaffolding)
- **Phase 1:** CRZ XML Parser (streaming lxml.iterparse, schema fingerprinting, 26 tests)
- **Phase 2:** Database & Data Model (13 ORM models, Alembic migration, 15 tests)
- **Phase 3:** Ingestion Pipeline (Slovak price parsing, entity normalization, upsert, 40 tests)
- **Phase 3 Code Review:** 3C+6I+4M fixed, 57 new tests added
- **Phase 4:** Risk Flags + Cleaning (6 flags, compound severity, re-flagging lifecycle, freshness, 62 tests)
- **Phase 4 Code Review:** 4 IMPORTANT fixed (timezone, seed_flags, memory streaming, orphan cleanup)
- **Phase 5:** Streamlit Dashboard (7 pages, Slovak UI, CSV export, CRZ links)
- **Phase 5 Code Review:** 2 CRITICAL fixed (flag_code crash, N+1 queries)
- **Full Codebase Review:** 3C+8I+9M found, ALL CRITICAL + key IMPORTANT fixed
- **Phase 6:** Documentation & Portfolio Polish
  - README.md (English, 228 lines, recruiter-ready)
  - docs/methodology.md (bilingual Slovak + English, 429 lines)
  - docs/limitations.md (English, ~180 lines, honest limitations)
  - docs/architecture.md (English, 356 lines, ASCII diagrams)
  - docs/source-notes.md (English, 237 lines, field mapping)
  - docs/deployment-checklist.md (pre-flight checklist)
  - docs/runbook.md (operational procedures)
  - LICENSE (MIT)
- **Phase 7:** Final Verification + Push to GitHub — DONE
- **Pre-Live Hardening:** 8 actions completed (see below)

### Pre-Live Hardening (Completed)

All 8 pre-live actions completed, committed as `f433dd0`, pushed to GitHub:

1. **Security Review** (security-reviewer agent):
   - FIXED: XXE vulnerability in XML parser (resolve_entities=False, no_network=True)
   - FIXED: Natural person PII masking in CSV export
   - FIXED: PII notices on search and detail pages
   - OWASP Top 10: SQL injection PASS, XSS PASS, SSRF PASS, XXE FIXED

2. **Click-Path Audit** (code-reviewer agent):
   - FIXED: Severity filter logic bug for "high" (override_threshold=3 not 2)
   - FIXED: N+1 queries in Organizations/Suppliers pages (batch loading)
   - FIXED: Result count mismatch (shows "zobrazujem prvých 20")
   - FIXED: Whitespace-only search bypass (.strip() in filters)
   - FIXED: Freshness banner missing on Metodika page
   - FIXED: Missing CRZ links in org/supplier expanders
   - FIXED: Silent absence of contracts for orgs without IČO

3. **Dead Code Cleanup** (refactor-cleaner agent):
   - Removed 5 empty placeholder packages: app/api, app/attachments, app/attachments/metadata, app/enrichment, tests/api

4. **Docker Hardening** (general agent + docker-patterns skill):
   - docker-compose.yml: restart:unless-stopped, mem_limit:512m, logging limits, shm_size:256m, 127.0.0.1:5433 binding
   - docker-compose.prod.yml: production override (created)

5. **PostgreSQL Patterns** (database-reviewer agent):
   - GOOD: Connection pool (pool_pre_ping, pool_recycle=300, pool_size=5)
   - GOOD: All FK columns indexed, migration rollback safe
   - FOUND: Freshness timezone bug (naive vs aware datetimes) — FIXED LIVE during E2E test

6. **Deployment Checklist** (general agent):
   - docs/deployment-checklist.md created
   - docs/runbook.md created

7. **Live Dashboard E2E Test** (browser-qa):
   - Started Docker PG, ran migrations, ingested sample data, started Streamlit
   - FOUND AND FIXED LIVE: TypeError in freshness.py (timezone mismatch)
   - Verified: Home, Oznamy, Metodika, Stav dat pages all render correctly

8. **Test Coverage**: 202 tests, 58% overall coverage (see remaining items below)

### Remaining Items (MUST DO BEFORE PRODUCTION)

These items were identified by the pre-live audits but not yet fixed. They should be addressed in the next session:

#### HIGH Priority (from PostgreSQL reviewer):
1. **Replace ingestion lock with `pg_advisory_xact_lock`** — Current TOCTOU race condition in `acquire_ingestion_lock()` (app/db/repository.py lines 245-277). Two concurrent processes could both pass the check. Fix: use `SELECT pg_try_advisory_xact_lock(hashval)` for true atomicity.
2. **Batch `run_flag_evaluation` with periodic commits** — Currently streams ALL contracts in one transaction. With 100K+ contracts, holds locks on `contract_risk_flags` for the entire duration. Fix: process in explicit batches with `session.commit()` between batches.
3. **Add composite index on `contract_risk_flags(crz_contract_id, source_run_id)`** — The per-contract DELETE during re-flagging does index scan on `crz_contract_id` then filters `source_run_id` in memory. A composite index would make this a direct index lookup.
4. **Add `connect_timeout` to engine `connect_args`** — If DB unreachable, default TCP timeout is 60-120s. Add `connect_args={"connect_timeout": 10}`.

#### MEDIUM Priority (from security + click-path reviews):
5. **Pin dependency versions in pyproject.toml** — All deps use `>=` (httpx>=0.27, lxml>=5.0, etc.). Should pin upper bounds: `httpx>=0.27,<0.28`. Or add requirements.lock.
6. **Separate SQL echo from app_env** — `echo=(settings.app_env == "development")` in session.py logs all queries+params in dev mode. Use dedicated `sql_echo: bool = False` setting.
7. **Add contract CSV export to Detail page** — Page 2 (Detail zmluvy) has no export button. Add `export_dataframe` call.
8. **Move DB session creation inside `if contract_id:` block** — Page 2 creates session unconditionally even when no contract ID entered (wasteful).
9. **Add `DateTime(timezone=True)` to migration** — PostgreSQL reviewer noted `started_at`/`finished_at` use `DateTime` not `DateTime(timezone=True)`. The Python code uses `datetime.now(UTC)` (aware) but PG silently drops timezone info. Fixed at Python level (freshness.py) but should be fixed at schema level too.

#### LOW Priority (from security review):
10. **Add security headers** via reverse proxy (X-Content-Type-Options, X-Frame-Options, CSP, HSTS)
11. **Remove POSTGRES_PASSWORD from docker-compose.yml** — Use `${POSTGRES_PASSWORD}` variable substitution
12. **Add ZIP bomb protection** — Validate ZIP size before extraction in parser
13. **Add redirect domain validation** to httpx client in download.py
14. **Add FK indexes** for `organization_metrics_monthly.organization_id` and `supplier_metrics_monthly.supplier_id`

### Test Coverage Gaps (58% overall)
- Dashboard pages: 0% coverage (all 5 pages untested)
- `ingestion/jobs.py`: 31% (orchestrator logic)
- `ingestion/crz/download.py`: 74% (retry logic)
- `app/db/repository.py`: 88%
- `app/db/session.py`: 53%
- Target: 80%+ for critical paths (ingestion, flags, repository)

### Key Source Files
- `README.md` — Project overview, architecture, quick start, roadmap (English)
- `docs/architecture.md` — System architecture with ASCII diagrams (English, 356 lines)
- `docs/methodology.md` — Flag methodology (bilingual SK+EN, 429 lines)
- `docs/limitations.md` — Honest project limitations (English)
- `docs/source-notes.md` — CRZ data source & field mapping (English)
- `docs/deployment-checklist.md` — Pre-flight deployment checklist
- `docs/runbook.md` — Operational runbook (daily/weekly/monthly)
- `docs/master-plan.md` — THE implementation bible (v2.0, 1,014 lines)
- `app/settings.py` — Pydantic settings (database_url default is empty string)
- `app/db/session.py` — Singleton engine, session factory
- `app/db/models.py` — 13 ORM models (Contract PK=crz_contract_id)
- `app/db/repository.py` — CRUD layer. upsert_contract() → tuple[Contract, bool]
- `app/ingestion/crz/parser.py` — Streaming XML parser with XXE protection
- `app/ingestion/crz/download.py` — HTTP client with 3× retry
- `app/ingestion/jobs.py` — Orchestrator
- `app/transforms/cleaning.py` — parse_slovak_price (European format aware)
- `app/transforms/entities.py` — is_probable_natural_person (12 legal suffixes)
- `app/flags/definitions.py` — 6 MVP flags catalog
- `app/flags/evaluate.py` — Flag checkers, compound_severity
- `app/flags/freshness.py` — check_data_freshness (48h threshold, timezone-safe)
- `app/dashboard/components/connection.py` — @st.cache_resource engine, get_session()
- `app/dashboard/components/queries.py` — 13 DB queries, batch loading, ILIKE escaping
- `app/dashboard/components/filters.py` — Sidebar widgets (.strip() on search)
- `app/dashboard/components/export.py` — CSV export with PII masking
- `app/dashboard/Home.py` — Main entry
- `app/dashboard/pages/` — 6 Streamlit pages

### Important Decisions & Fixes
- Port 5433 (system PG 5432 used by n8n)
- `database_url` default is empty string (no hardcoded credentials)
- `get_session()` calls `_get_session_factory()()` (double parens)
- Stale ingestion runs (>6h) auto-cleaned to "failed"
- `parse_slovak_price` handles European format: "1.234,56" → 1234.56
- CSV export timestamp is dynamic, not frozen at import
- All ILIKE queries escape %, _, \ wildcards via _escape_ilike()
- `datetime.now(UTC)` everywhere, freshness.py handles naive PG datetimes
- Natural person detection: no IČO + no legal form suffix → probable natural person
- Compound severity: 3+ flags = "high", else max individual
- XXE hardened: resolve_entities=False, no_network=True, dtd_validation=False
- Docker: restart:unless-stopped, mem_limit:512m, 127.0.0.1:5433

### Key API Signatures
- `upsert_contract(session, parsed: ParsedContract, export_date: date) → tuple[Contract, bool]`
- `acquire_ingestion_lock(session) → int` uses flush(), caller must commit()
- `download_export(date_str, max_retries=3) → Path`
- `run_flag_evaluation(session, run_id, batch_size=500) → tuple[int, int]`
- `seed_flags(session) → int` dialect-agnostic upsert
- `check_data_freshness(session) → dict` (timezone-safe)
- `process_export(zip_path: Path, export_date: date) → dict`

### Infrastructure Notes
- **eucheck-db-1** Docker container on port 5433 — must stop before starting CRZcheck DB
- Streamlit port: 8501
- Docker compose creates network `crzcheck_default`, volume `crzcheck_pgdata`
- Setsid needed to keep Streamlit alive in background: `setsid .venv/bin/streamlit run ... &`

### Process
- After each phase: PAUSE, report, user quality gate
- Master plan: docs/master-plan.md
- Slovak UI, no accusatory language
- Run `make dashboard` to start Streamlit on port 8501

### Phase 8: Production Deployment — DEFERRED
Hetzner server, *.bacimo.net, not in current scope.
