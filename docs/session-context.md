# CRZ Risk & Quality Monitor — Session Context for Compaction

## Current State (2026-05-16)

### Project
- **Repo:** /mnt/data2/projects/CRZcheck
- **GitHub:** https://github.com/garadice/CRZcheck
- **Venv:** .venv (Python 3.12.3, all deps installed)
- **Tests:** 202/202 passing, ruff lint clean
- **No secrets in source code** — verified by security scan

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
  - LICENSE (MIT)
  - Code review: 4C+3I+4M found, ALL CRITICAL + IMPORTANT fixed
  - Legal form suffix tables synchronized with actual code (12 real suffixes)
  - 202 tests still passing

### Key Source Files
- `README.md` — Project overview, architecture, quick start, screenshots, roadmap (English, 228 lines)
- `docs/architecture.md` — System architecture with ASCII diagrams (English, 356 lines)
- `docs/methodology.md` — Flag methodology explanations (bilingual SK+EN, 429 lines)
- `docs/limitations.md` — Honest project limitations (English, ~180 lines)
- `docs/source-notes.md` — CRZ data source & field mapping (English, 237 lines)
- `LICENSE` — MIT license
- `app/settings.py` — Pydantic settings (**database_url default is empty string**, must be set via .env)
- `app/db/session.py` — Singleton engine, session factory
- `app/db/models.py` — 13 ORM models (Contract PK=crz_contract_id, currency default EUR)
- `app/db/repository.py` — CRUD layer. NOTE: `upsert_contract()` returns `tuple[Contract, bool]`. Stale-run cleanup (zombie >6h auto-failed)
- `app/ingestion/crz/parser.py` — Streaming XML parser with field mapping
- `app/ingestion/crz/download.py` — HTTP client with 3× retry + exponential backoff
- `app/ingestion/jobs.py` — Orchestrator, `acquire_ingestion_lock` uses flush() not commit()
- `app/transforms/cleaning.py` — `parse_slovak_price` (handles European dot-thousands), `parse_crz_date`, `normalize_ico`
- `app/transforms/entities.py` — `is_probable_natural_person`, `normalize_entity_name`
- `app/flags/definitions.py` — 6 MVP flags catalog (FlagDefinition dataclass)
- `app/flags/evaluate.py` — Flag checkers, compound_severity, run_flag_evaluation (batch with yield_per, orphan cleanup)
- `app/flags/flags_catalog.py` — seed_flags() dialect-agnostic (select+update/insert)
- `app/flags/freshness.py` — check_data_freshness (48h stale threshold)
- `app/dashboard/components/connection.py` — @st.cache_resource engine+factory, get_session(), disclaimer, freshness banner
- `app/dashboard/components/queries.py` — 13 DB queries with batch loading, ILIKE escaping
- `app/dashboard/components/filters.py` — Sidebar widgets (date, severity, flag type, search)
- `app/dashboard/components/export.py` — CSV export with dynamic timestamp disclaimer
- `app/dashboard/Home.py` — Main entry (search, stats, disclaimer, freshness)
- `app/dashboard/pages/1_Oznamy.py` — Flagged contracts with compound severity
- `app/dashboard/pages/2_Detail_zmluvy.py` — Contract detail (metadata, flags, attachments)
- `app/dashboard/pages/3_Organizacie.py` — Organization profiles
- `app/dashboard/pages/4_Dodavatelia.py` — Suppliers (natural persons hidden by default)
- `app/dashboard/pages/5_Metodika.py` — Flag methodology explanation
- `app/dashboard/pages/6_Stav_dat.py` — Data status, freshness, ingestion history

### What's Next: Phase 7 (Final Verification + Push)

**Phase 7: Final Verification + Push to GitHub** (direct)
- docker compose up, make migrate, make test, make lint, make ingest (1 day), make dashboard
- Push to https://github.com/garadice/CRZcheck

**Phase 8: Production Deployment** — DEFERRED (Hetzner, *.bacimo.net)

### Important Decisions & Fixes
- Port 5433 (system PG 5432 used by n8n)
- `database_url` default is empty string (CRITICAL-3 fix — no hardcoded credentials)
- `get_session()` in dashboard calls `_get_session_factory()()` (CRITICAL-1 fix — double parens)
- Stale ingestion runs (>6h) auto-cleaned to "failed" status (CRITICAL-2 fix)
- `parse_slovak_price` handles European format: "1.234,56" → 1234.56 (IMPORTANT-2 fix)
- CSV export timestamp is dynamic, not frozen at import (IMPORTANT-5 fix)
- All ILIKE queries escape %, _, \ wildcards (IMPORTANT-7 fix)
- `datetime.now(UTC)` everywhere (not `datetime.utcnow()` or `datetime.now()`)
- Natural person detection already in entities.py (12 legal form suffixes)
- Compound severity: 3+ flags = "high", else max individual

### Key API Notes
- `upsert_contract(session, parsed, export_date) → tuple[Contract, bool]`
- `acquire_ingestion_lock(session) → int` uses flush(), caller must commit()
- `download_export(date_str, max_retries=3) → Path` retries on 5xx/transport errors
- `run_flag_evaluation(session, run_id, batch_size=500) → tuple[int, int]`
- `seed_flags(session) → int` dialect-agnostic upsert
- `check_data_freshness(session) → dict` (status, warning, last_success, hours_since)
- Dashboard `get_session()` returns a Session (not sessionmaker)

### Process
- After each phase: PAUSE, report, user quality gate
- Master plan: docs/master-plan.md (Phase 6 starts at line ~845)
- Slovak UI, no accusatory language ("corruption", "fraud", "suspicious")
- Run `make dashboard` to start Streamlit on port 8501
