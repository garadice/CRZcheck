# CRZ Risk & Quality Monitor — Architecture Documentation

## Overview

CRZcheck is a Python data pipeline that ingests public contract metadata from the Slovak CRZ government API, checks it for quality issues, and shows the results in a Streamlit dashboard. It processes hundreds of thousands of contracts within a 90-day rolling window using six metadata quality checks. The pipeline is designed to be idempotent (safe to re-run), data-integrity-focused (SHA-256 verification, upsert semantics), and simple to operate (single-command Docker setup).

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         External Systems                            │
│                                                                     │
│   ┌──────────────────┐                  ┌───────────────────────┐   │
│   │  CRZ Government   │                  │   User's Browser      │   │
│   │  API (REST/ZIP)   │                  │                       │   │
│   └────────┬──────────┘                  └───────────▲───────────┘   │
│            │                                         │               │
└────────────┼─────────────────────────────────────────┼───────────────┘
             │                                         │
             │ daily ZIP download                      │ HTTP
             │ (rate-limited)                          │
             │                                         │
┌────────────▼─────────────────────────────────────────┼───────────────┐
│                   CRZcheck Application                               │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                    Ingestion Layer                            │    │
│  │                                                              │    │
│  │  CRZDownloader ──► Streaming XML Parser ──► Ingestion Jobs  │    │
│  │  (httpx, ZIP)       (lxml.iterparse)         (orchestrator) │    │
│  └──────────────────────────┬───────────────────────────────────┘    │
│                             │                                        │
│                             ▼                                        │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                   Transform Layer                             │    │
│  │                                                              │    │
│  │  Data Cleaning ──► Entity Normalization                     │    │
│  │  (prices, dates,     (natural person                        │    │
│  │   IČO, names)         detection, dedup)                     │    │
│  └──────────────────────────┬───────────────────────────────────┘    │
│                             │                                        │
│                             ▼                                        │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                PostgreSQL Database                            │    │
│  │              (13 tables, SQLAlchemy ORM)                      │    │
│  │                                                              │    │
│  │  contracts · organizations · suppliers · risk_flags          │    │
│  │  contract_risk_flags · ingestion_runs · raw_crz_exports      │    │
│  │  ... (7 more tables)                                         │    │
│  └──────────────────────────┬───────────────────────────────────┘    │
│                             │                                        │
│                             ▼                                        │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                   Flag Engine                                 │    │
│  │                                                              │    │
│  │  6 flag checkers ──► compound severity ──► re-flag lifecycle │    │
│  └──────────────────────────┬───────────────────────────────────┘    │
│                             │                                        │
│                             ▼                                        │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                 Streamlit Dashboard                           │    │
│  │                                                              │    │
│  │  Home + 6 pages + 4 shared components                       │    │
│  │  (batch loading, ILIKE search, CSV export)                  │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                             │                                        │
└─────────────────────────────┼────────────────────────────────────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │  User's Browser │
                     └─────────────────┘
```

---

## Data Flow

```
[CRZ Government API]
       │
       │ 1. Daily ZIP download (rate-limited via httpx)
       ▼
[CRZDownloader]  app/ingestion/crz/download.py
       │
       │ 2. ZIP extraction → XML, SHA-256 integrity check
       ▼
[Streaming XML Parser]  app/ingestion/crz/parser.py
       │
       │ 3. lxml.iterparse yields ParsedContract dataclasses
       │    (memory-efficient: elements cleared after processing)
       ▼
[Ingestion Orchestrator]  app/ingestion/jobs.py
       │
       │ 4. Clean, normalize, upsert each contract
       ▼
[Data Cleaning]  app/transforms/cleaning.py
   │   parse_slovak_price()   — European format: 1.234,56 → 1234.56
   │   parse_crz_date()       — Slovak date strings → date objects
   │   normalize_ico()        — Strip prefixes, pad to 8 digits
   │   clean_name()           — Whitespace normalization
   │
   ▼
[Entity Normalization]  app/transforms/entities.py
   │   is_probable_natural_person()  — No IČO + no legal form suffix
   │   normalize_entity_name()       — Consistent casing, dedup key
   │
   ▼
[Repository Upsert]  app/db/repository.py
       │
       │ 5. upsert_contract() returns (Contract, was_created: bool)
       │    — INSERT on new, UPDATE on changed payload hash
       │    — Organizations/suppliers deduplicated by IČO
       ▼
[PostgreSQL Database]  13 tables via SQLAlchemy ORM
       │
       │ 6. Flag evaluation runs after successful ingestion
       ▼
[Flag Evaluation Engine]  app/flags/evaluate.py
       │
       │ 7. Six flag checkers compute metadata quality indicators:
       │    • missing_price      — No price information at all (both price_total and price_contract are NULL)
       │    • zero_price         — Contract price is zero
       │    • missing_supplier   — Supplier name is absent
       │    ├── missing_supplier_ico  — Supplier IČO is missing
       │    ├── invalid_ico_format   — IČO present but not 8 digits
       │    └── missing_buyer_ico    — Buyer IČO is missing
       │
       │ 8. Compound severity: 3+ flags on one contract → "high"
       │
       │ 9. Re-flagging lifecycle:
       │    DELETE old flags for source_run_id → compute → INSERT new
       ▼
[ContractRiskFlag + RiskFlag Tables]
       │
       │ 10. Dashboard queries with batch loading
       ▼
[Streamlit Dashboard]  app/dashboard/Home.py + pages/
       │
       │ 11. Rendered to user's browser
       ▼
[User's Browser]
```

---

## Component Descriptions

### Ingestion Layer

**CRZDownloader** (`app/ingestion/crz/download.py`)
Downloads daily ZIP archives from the CRZ government API using `httpx` with configurable rate limiting. Each download is tracked in `raw_crz_exports` with its URL, SHA-256 hash, and HTTP status code. Failed downloads are recorded and can be retried without duplication.

**Streaming XML Parser** (`app/ingestion/crz/parser.py`)
Uses `lxml.iterparse` to process multi-hundred-megabyte XML files without loading them fully into memory. Elements are cleared after processing. Maps 34 XML fields from the CRZ schema onto `ParsedContract` dataclasses. Records the schema fingerprint in `crz_export_files` to detect upstream schema changes.

**Ingestion Orchestrator** (`app/ingestion/jobs.py`)
Coordinates the full ingestion pipeline: download → parse → clean → normalize → upsert. Each run is tracked in `ingestion_runs` with type (full/incremental), status, record counts, and timestamps. Implements an ingestion lock to prevent concurrent runs, with zombie detection that auto-fails stale runs older than 6 hours.

### Transform Layer

**Data Cleaning** (`app/transforms/cleaning.py`)
Handles Slovak-specific data formats:
- **Price parsing**: European number format (`1.234,56` → `1234.56`), handles missing/corrupt values gracefully
- **Date parsing**: Slovak date string conventions into Python `date` objects
- **IČO normalization**: Strips common prefixes (e.g., "SK"), pads to 8 digits
- **Name cleaning**: Collapses whitespace, strips leading/trailing spaces

**Entity Normalization** (`app/transforms/entities.py`)
Separates natural persons from legal entities using a heuristic: entities without an IČO and without a known legal form suffix (s.r.o., a.s., v.o.s., etc.) are classified as natural persons. Entity names are normalized for deduplication — consistent casing, whitespace normalization, and legal form stripping.

### Storage Layer

**Database Session** (`app/db/session.py`)
Manages the SQLAlchemy engine with a singleton pattern for connection pooling. The engine is created once and reused across the application. Session factory uses scoped sessions for thread safety.

**ORM Models** (`app/db/models.py`)
Defines 13 tables with full relational mapping. Uses SQLAlchemy 2.0 declarative style with typed column annotations. Migrations are managed through Alembic.

**Repository** (`app/db/repository.py`)
Implements the data access layer with `upsert_contract()` as the primary write operation. Returns a `(Contract, was_created)` tuple so callers know whether a contract was inserted or updated. Handles deduplication of organizations and suppliers by IČO with partial unique indexes.

### Flag Engine

**Flag Definitions** (`app/flags/definitions.py`)
Contains the `FLAG_CATALOG` — a registry of all six risk flags, each with a machine-readable code, human-readable name, base severity level, and methodology description.

**Evaluation Engine** (`app/flags/evaluate.py`)
Runs all flag checkers against the contract dataset within a given scope. Implements compound severity: contracts with 3 or more active flags are escalated to "high" severity regardless of individual flag severities.

**Re-flagging Lifecycle**
Flag evaluation is deterministic and tied to a `source_run_id`. When re-evaluating, the engine:
1. DELETEs all existing flags for the given `source_run_id`
2. Computes fresh flags from current data
3. INSERTs new flag instances

This ensures flags are always consistent with the underlying data and avoids stale flag accumulation.

### Dashboard

**Streamlit Application** (`app/dashboard/Home.py` + 6 pages + 4 components)
Interactive web dashboard for exploring contracts, risk flags, and entity relationships. Key technical details:
- **Batch loading**: Large result sets are loaded in configurable batches to avoid UI freezing
- **ILIKE escaping**: Search queries escape SQL wildcards (`%`, `_`) to prevent unintended pattern matching
- **CSV export**: Export timestamps are generated dynamically at export time, not frozen at page load
- **Shared components**: Four reusable components (charts, tables, filters, exports) ensure consistency across pages

---

## Database Schema

The database contains 13 tables organized into four functional groups:

### Ingestion Tracking

| Table | Purpose |
|---|---|
| `raw_crz_exports` | Download tracking — URL, SHA-256 hash, HTTP status, timestamps |
| `crz_export_files` | Parsed export metadata — record count, schema fingerprint, parse status |
| `ingestion_runs` | Run tracking — type (full/incremental), status, record counts, start/end times |
| `data_quality_checks` | Quality check results per ingestion run |

### Core Contract Data

| Table | Purpose |
|---|---|
| `contracts` | Core contract records — 34 XML fields mapped to typed columns |
| `contract_versions` | Change tracking — payload hash for change detection, metadata JSON |
| `contract_attachments_metadata` | Attachment file metadata (filename, size, type) |

### Entities

| Table | Purpose |
|---|---|
| `organizations` | Buyer entities — deduplicated by IČO with partial unique index |
| `suppliers` | Supplier entities — includes natural person detection flag |

### Risk Analysis

| Table | Purpose |
|---|---|
| `risk_flags` | Flag definitions — code, name, severity, methodology description |
| `contract_risk_flags` | Flag instances per contract — FK to `risk_flags.id` (not flag code) |
| `organization_metrics_monthly` | Monthly aggregation of organization procurement activity |
| `supplier_metrics_monthly` | Monthly aggregation of supplier award activity |

---

## Key Design Decisions

### 1. PostgreSQL on Port 5433

The system's PostgreSQL instance runs in Docker on port **5433** rather than the default 5432. The host system's port 5432 is already occupied by an n8n automation instance. This avoids port conflicts while keeping both services running simultaneously.

### 2. 90-Day Rolling Window

Ingestion operates on a configurable 90-day rolling window rather than attempting to maintain the full CRZ historical dataset. This keeps storage and processing requirements bounded while still providing a statistically meaningful sample for risk analysis. The window size is controlled via `Pydantic Settings`.

### 3. Singleton Engine Pattern

The SQLAlchemy engine is created once using a module-level singleton. This ensures connection pooling works correctly and avoids the overhead of creating multiple engine instances. All sessions share the same engine and its connection pool.

### 4. Re-flagging Lifecycle (DELETE → Compute → INSERT)

Flag evaluation is not incremental — it is fully deterministic. Each evaluation run is tied to a `source_run_id`. Before computing new flags, all existing flags for that run are deleted. This prevents stale flags from accumulating and guarantees that flags always reflect the current state of the underlying data.

### 5. Ingestion Lock with Zombie Cleanup

Only one ingestion run can be active at a time. A database-level lock prevents concurrent runs. Runs that have been running for more than 6 hours are automatically marked as failed during the next lock acquisition, cleaning up zombie processes from crashed or interrupted runs.

### 6. Streaming XML Parser

The CRZ exports can exceed hundreds of megabytes. Using `lxml.iterparse` with explicit element clearing keeps memory usage constant regardless of file size. The parser processes one contract element at a time and releases it immediately after extraction.

### 7. Slovak Price Format Handling

Slovak price data uses European number formatting (`1.234,56` — dot as thousands separator, comma as decimal). The `parse_slovak_price()` function handles this format explicitly, along with edge cases like missing values, text like "neuvedená" (not specified), and malformed numbers.

### 8. Natural Person Detection Heuristic

Slovak procurement data does not explicitly distinguish natural persons from legal entities. The system uses a heuristic: if an entity has no IČO (business ID) and its name does not contain a recognized legal form suffix (s.r.o., a.s., v.o.s., k.s., etc.), it is classified as a probable natural person. This classification affects how the entity is stored and displayed.

### 9. Compound Severity Escalation

Individual flags have their own severity levels (low, medium, high). However, contracts accumulating 3 or more flags of any severity are automatically escalated to "high" compound severity. This catches contracts that are individually unremarkable but collectively suspicious.

### 10. ILIKE Query Escaping

Dashboard search uses PostgreSQL `ILIKE` for case-insensitive pattern matching. All user input is escaped for SQL wildcards (`%` → `\%`, `_` → `\_`) before interpolation, preventing users from accidentally or intentionally crafting broad pattern matches.

### 11. Dynamic CSV Export Timestamps

When users export dashboard data to CSV, the filename and embedded timestamps are generated at the moment of export, not when the page was loaded. This ensures exported files have accurate timestamps reflecting when the export action occurred.

---

## Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Language | Python 3.12 | Primary implementation language |
| Database | PostgreSQL 16 | Persistent storage (Docker, port 5433) |
| ORM | SQLAlchemy 2.0 | Database models, queries, connection pooling |
| Migrations | Alembic | Schema versioning and migration management |
| HTTP Client | httpx | Rate-limited downloads from CRZ API |
| XML Parsing | lxml | Streaming XML parsing (`iterparse`) |
| Dashboard | Streamlit | Interactive web-based analytics UI |
| Configuration | Pydantic Settings | Type-safe environment-based configuration |
| Data Handling | Pandas | Tabular data manipulation in dashboard |
| Linting | Ruff | Fast Python linting and formatting |
| Testing | pytest | 302 tests (84% coverage) |
| Containerization | Docker Compose | PostgreSQL service definition |

---

## Project Structure

```
CRZcheck/
├── app/
│   ├── settings.py                        # Pydantic Settings configuration
│   ├── db/
│   │   ├── session.py                     # SQLAlchemy engine & session factory
│   │   ├── models.py                      # 13 ORM model definitions
│   │   └── repository.py                  # upsert_contract, ingestion lock
│   ├── transforms/
│   │   ├── cleaning.py                    # Price, date, IČO parsing utilities
│   │   └── entities.py                    # Entity normalization & natural person detection
│   ├── ingestion/
│   │   ├── crz/
│   │   │   ├── models.py                  # ParsedContract dataclass
│   │   │   ├── parser.py                  # Streaming XML parser (lxml.iterparse)
│   │   │   ├── links.py                   # CRZ URL builders
│   │   │   └── download.py                # Rate-limited ZIP downloader
│   │   └── jobs.py                        # Ingestion orchestration
│   ├── flags/
│   │   ├── definitions.py                 # FLAG_CATALOG registry (6 flags)
│   │   ├── evaluate.py                    # Flag evaluation engine
│   │   ├── flags_catalog.py               # Database seed & lookup
│   │   └── freshness.py                   # Flag freshness checks
│   └── dashboard/
│       ├── Home.py                        # Streamlit entry point
│       ├── pages/                         # 6 dashboard pages
│       └── components/                    # 4 shared UI components
├── alembic/                               # Database migration scripts
│   ├── versions/                          # Migration files
│   └── env.py                             # Alembic configuration
├── tests/                                 # 302 test cases (84% coverage)
├── docs/                                  # Project documentation
├── data/                                  # Raw data storage
├── docker-compose.yml                     # PostgreSQL service
├── pyproject.toml                         # Dependencies & tool configuration
└── Makefile                               # Common development commands
```
