# CRZ Risk & Quality Monitor — Master Execution Plan

> Version: **2.0** (Santa Review v2)  
> Derived from: `docs/crz-risk-quality-monitor-implementation-plan.md`  
> Date: 2026-05-15  
> Status: **READY FOR IMPLEMENTATION**

---

## Santa Review Fixes Applied (v1 → v2)

| # | Issue | Resolution |
|---|-------|-----------|
| 1 | Port 5432→5433 | ✅ DONE — `docker-compose.yml`, `settings.py`, `.env.example` all use 5433 |
| 2 | Re-flagging strategy | `source_run_id` added to `contract_risk_flags`; flag lifecycle = DELETE old → recompute → INSERT |
| 3 | Slovak price parsing | Explicit rules for comma decimals, space thousands, EUR suffix, edge cases; test cases specified |
| 4 | `data_quality_checks` table | Restored to MVP table list in Phase 2 |
| 5 | Natural person detection | Explicit heuristic with legal-form suffix list added to Phase 4 |
| 6 | 60% flag rate mitigation | Compound severity (3+ flags = elevated), dashboard default filter, manual review gate |
| 7 | Rolling window → 90 days | ✅ DONE — `settings.py` and `.env.example` updated to 90 |
| 8 | All 34 XML fields mapped | Two sections: Mapped (with targets) + Unmapped (with justifications) |
| 9 | Phase 8 (Production) | Added as DEFERRED phase with full scope documented |
| 10 | Partial unique index on ico | `WHERE ico IS NOT NULL` indexes specified for organizations and suppliers |

**Additional improvements incorporated:**
- Schema fingerprinting in Phase 1 (hash of XML element names)
- `organization_metrics_monthly` and `supplier_metrics_monthly` tables in Phase 2
- Typo fix: "Metódkia" → "Metodika"
- Explicit FK specifications in all Phase 2 table definitions
- Streamlit connection pooling specified in Phase 5
- Concurrent ingestion guard (check `ingestion_runs` for in-progress status)
- Data freshness warning (flag if last successful ingestion > 48h ago)
- Explicit edge case tests for re-ingestion, changed data, all-fields-empty, encoding, zero-contract XML, Slovak price format
- `currency` column in contracts (default `'EUR'`)

---

## Research Verification Summary

| Item | Status | Detail |
|------|--------|--------|
| CRZ export URL | ✅ Verified | `https://www.crz.gov.sk/export/YYYY-MM-DD.zip` → HTTP 200 |
| XML structure | ✅ Verified | 34 tags per `<zmluva>`, 7 per `<priloha>` |
| Detail link pattern | ✅ Verified | `https://www.crz.gov.sk/index.php?ID={ID}` redirects correctly |
| Attachment link pattern | ✅ Verified | `https://www.crz.gov.sk/data/att/{filename}` |
| Python 3.12 | ✅ Available | All packages installed in .venv |
| Docker | ✅ Available | v29.4.3, Compose v5.1.3 |
| PostgreSQL | ✅ Configured | Docker on **5433** (system PG on 5432 used by n8n) |
| Field mapping zs1/zs2 | ⚠️ ~95% reliable | zs1=buyer usually, but CAN vary; ico/ico1 more stable |

---

## Critical XML Field Mapping

### Section A: Mapped Fields (with target column)

```
CRZ XML Field     → Target Table.Column           → Notes
─────────────────────────────────────────────────────────────────────────
ID                → contracts.crz_contract_id      → Primary key, CRZ detail URL
nazov             → contracts.title                 → Contract title
zs1               → contracts.buyer_name            → Usually buyer (~95%), documented assumption
zs2               → contracts.supplier_name         → Usually supplier
ico               → contracts.supplier_ico          → Supplier IČO (can be empty for persons)
sidlo             → contracts.supplier_address       → Supplier address
ico1              → contracts.buyer_ico              → Buyer/public entity IČO
sidlo1            → contracts.buyer_address          → Buyer address
predmet           → contracts.subject                → Contract subject
datum_ucinnost    → contracts.effective_date         → Can be "0000-00-00" → NULL
datum_platnost_do → contracts.valid_until            → Can be "0000-00-00" → NULL
suma_zmluva       → contracts.price_contract         → Slovak price format (see parsing rules)
suma_spolu        → contracts.price_total            → Total price
datum_zverejnene  → contracts.publication_date       → Full datetime
typ               → contracts.contract_type          → 1 or 2
druh              → contracts.contract_kind           → 0, 1, or 2
rezort            → contracts.department             → Department code
datum             → contracts.contract_date           → Contract date (from XML root)
prilohy/priloha   → (parsed into attachment table)   → Can be empty element
  ID              → contract_attachments_metadata.attachment_id
  nazov           → contract_attachments_metadata.attachment_name
  dokument        → contract_attachments_metadata.scan_filename   → via /data/att/
  dokument1       → contract_attachments_metadata.text_filename   → via /data/att/
  velkost         → contract_attachments_metadata.scan_size_bytes
  velkost1        → contract_attachments_metadata.text_size_bytes
```

### Section B: Intentionally Unmapped Fields (with justification)

| XML Field | Observed Values | Justification for Exclusion |
|-----------|----------------|-----------------------------|
| `id` | 0 or small number | Appears to be an internal counter, no clear analytical use |
| `poznamka` | Free text | Not used for metadata flagging in MVP |
| `stav` | 1 or 2 | Contract status — may be useful later but not MVP-flagged |
| `potv_ziadost` | Integer | Confirmation request type, operational CRZ field |
| `potv_datum` | Date or empty | Confirmation date, operational CRZ field |
| `zdroj` | 1, 3 | Source indicator, operational CRZ field |
| `text_ucinnost` | Mostly empty | Effectiveness text, empty in most records |
| `potvrdenie` | Filename | Confirmation PDF filename, operational CRZ field |
| `popis` | Mostly empty | Description field |
| `ref` | Mostly empty | Reference field |
| `internapozn` | Mostly empty | Internal note field |
| `popis_predmetu` | Mostly empty | Subject description field |
| `poznamka_zmena` | Mostly empty | Change note field |
| `uvo` | URL or empty | UVO link — useful but not MVP-flagged |
| `chan` | Timestamp | Channel/timestamp, operational CRZ field |

**Note:** These fields are still PARSED and stored in `contract_versions.metadata_json` for future use. They are simply not mapped to dedicated columns in the MVP schema.

---

## Data Quality Snapshot (2026-05-14 export)

- Total contracts: 2,671
- Zero price: 922 (34.5%) — most common anomaly
- No supplier IČO: 613 (23%)
- No buyer IČO: 469 (17.5%)
- No attachments: 98 (3.7%)
- Multiple attachments: 94 (3.5%)

**Implication:** ~60% of contracts will have at least one flag. Individual flags are noisy. Compound severity and dashboard filtering are critical (see Phase 4 mitigation strategy).

---

## MVP Decisions (Confirmed)

1. **Slovak UI + English README**
2. **90-day initial rolling window** (configurable via `CRZ_ROLLING_WINDOW_DAYS`)
   - Enables basic trend detection
   - ~90 days × ~2,700 contracts/day = ~243,000 contracts (manageable)
3. **Hide natural-person supplier profiles** (contract-level only, using explicit heuristic)
4. **Streamlit dashboard** (FastAPI later)
5. **Defer RPO enrichment** until core works
6. **Show all severities** with user filter; default filter: "medium+ severity OR 2+ flags"
7. **Disclaimer on CSV exports**
8. **Docker PostgreSQL on port 5433** (avoids n8n conflict on 5432)
9. **`currency` column** in contracts (default `'EUR'`, future-proofed for multi-currency)

---

## Execution Phases

### Phase 0: Project Setup ✅ COMPLETE

**Status:** DONE  
**What was done:**
- [x] Git repo initialized
- [x] GitHub repo created: `garadice/CRZcheck`
- [x] Project directory structure
- [x] `pyproject.toml` with all dependencies
- [x] Docker Compose — port **5433** (mapping 5433:5432)
- [x] `.env.example` — port 5433, 90-day window
- [x] `.gitignore`
- [x] `Makefile`
- [x] `app/settings.py` — port 5433, 90-day window
- [x] Virtual environment with all packages installed
- [x] Smoke tests passing (2/2)

**Port 5433 fix:** ✅ Applied to `docker-compose.yml`, `settings.py`, `.env.example`  
**Rolling window 90 days:** ✅ Applied to `settings.py`, `.env.example`

---

### Phase 1: CRZ XML Parser & Link Prototype

**Goal:** Prove that CRZ XML can be downloaded, parsed, and links derived correctly. Establish schema fingerprinting for drift detection.

**Prerequisite:** Phase 0 complete

**Files to create/modify:**
```
app/ingestion/crz/download.py    — HTTP client with rate limiting
app/ingestion/crz/parser.py      — XML parser using lxml.iterparse
app/ingestion/crz/models.py      — Pydantic models for parsed records
app/ingestion/crz/links.py       — CRZ detail + attachment URL generation
tests/fixtures/xml/sample.xml    — Small real XML fixture (~5 contracts)
tests/ingestion/test_parser.py   — Parser tests
tests/ingestion/test_links.py    — Link generation tests
```

**Key decisions:**
- Use `lxml.etree.iterparse` for streaming (memory efficient)
- Pydantic models for type-safe parsed records
- Rate limiting: 2s between requests during day (06-20), 0.35s at night
- Store raw ZIP/XML to `data/raw/` (gitignored)
- **Schema fingerprinting:** compute SHA-256 hash of sorted XML element names per `<zmluva>` and store in `crz_export_files.schema_fingerprint`. If fingerprint changes between runs, log a warning and record the new fingerprint. This enables early detection of CRZ schema drift without failing the pipeline.

**Schema fingerprint implementation:**
```python
def compute_schema_fingerprint(element_names: list[str]) -> str:
    canonical = ",".join(sorted(element_names))
    return hashlib.sha256(canonical.encode()).hexdigest()
```

**Tests:**
- [ ] Parser handles real XML with all 34 field types
- [ ] Parser handles empty/missing fields gracefully
- [ ] Detail link generation: `index.php?ID={ID}`
- [ ] Attachment link generation: `/data/att/{filename}`
- [ ] Parser handles contracts with no attachments
- [ ] Parser handles contracts with multiple attachments
- [ ] Schema fingerprint computed and stable for same structure
- [ ] Schema fingerprint differs when elements change
- [ ] Parser handles zero-contract XML (`<zmluvy></zmluvy>`)
- [ ] Parser handles encoding edge cases (UTF-8 BOM, Latin-1 fallback)

**Definition of done:** At least 2 real export days parse correctly with all fields, links, attachments, and schema fingerprints extracted.

**Estimated complexity:** 4/10  
**Recommended agent:** subagent (straightforward but many files)

---

### Phase 2: Database & Data Model

**Goal:** PostgreSQL running, SQLAlchemy models, Alembic migrations working. All MVP tables with explicit FK constraints and partial unique indexes.

**Prerequisite:** Phase 1 complete

**Files to create/modify:**
```
app/db/session.py                 — SQLAlchemy session factory
app/db/models.py                  — All MVP SQLAlchemy models
alembic.ini                       — Alembic config
alembic/env.py                    — Alembic environment
alembic/versions/001_initial.py   — Initial migration
tests/db/test_models.py           — Model tests
```

**MVP tables (13 tables):**

#### 1. `raw_crz_exports`
```
id                  SERIAL PRIMARY KEY
export_date         DATE NOT NULL
source_url          VARCHAR(512)
downloaded_at       TIMESTAMP
http_status         INTEGER
zip_sha256          VARCHAR(64)
zip_size_bytes      BIGINT
xml_filename        VARCHAR(255)
xml_sha256          VARCHAR(64)
xml_size_bytes      BIGINT
storage_path        VARCHAR(512)
status              VARCHAR(20) DEFAULT 'pending'
error_message       TEXT

UNIQUE (export_date)
INDEX (status)
```

#### 2. `crz_export_files`
```
id                  SERIAL PRIMARY KEY
raw_export_id       INTEGER NOT NULL → raw_crz_exports.id
parser_version      VARCHAR(20)
record_count        INTEGER
attachment_count    INTEGER
parsed_at           TIMESTAMP
parse_status        VARCHAR(20)
schema_fingerprint  VARCHAR(64)

FK: raw_export_id → raw_crz_exports.id ON DELETE CASCADE
```

#### 3. `contracts`
```
crz_contract_id     VARCHAR(50) PRIMARY KEY
title                TEXT
subject              TEXT
buyer_name           TEXT
buyer_ico            VARCHAR(20)
buyer_address        TEXT
supplier_name        TEXT
supplier_ico         VARCHAR(20)
supplier_address     TEXT
department           VARCHAR(20)
contract_type        SMALLINT
contract_kind         SMALLINT
contract_date        DATE
publication_date     TIMESTAMP
effective_date       DATE
valid_until          DATE
price_contract       NUMERIC(18,2)
price_total          NUMERIC(18,2)
currency             VARCHAR(3) DEFAULT 'EUR'
status               VARCHAR(20)
source_export_date   DATE
crz_detail_url       VARCHAR(512)
created_at           TIMESTAMP DEFAULT NOW()
updated_at           TIMESTAMP DEFAULT NOW()

INDEX (publication_date)
INDEX (buyer_ico)
INDEX (supplier_ico)
INDEX (price_total)
FULLTEXT INDEX on (title, subject)
```

#### 4. `contract_versions`
```
id                  SERIAL PRIMARY KEY
crz_contract_id     VARCHAR(50) NOT NULL → contracts.crz_contract_id
export_date         DATE NOT NULL
raw_export_id       INTEGER → raw_crz_exports.id
payload_hash        VARCHAR(64)
metadata_json       JSONB
change_note         TEXT
seen_at             TIMESTAMP DEFAULT NOW()

FK: crz_contract_id → contracts.crz_contract_id ON DELETE CASCADE
FK: raw_export_id → raw_crz_exports.id ON DELETE SET NULL
UNIQUE (crz_contract_id, export_date, payload_hash)
INDEX (crz_contract_id, export_date)
```

#### 5. `contract_attachments_metadata`
```
id                  SERIAL PRIMARY KEY
crz_contract_id     VARCHAR(50) NOT NULL → contracts.crz_contract_id
attachment_id       VARCHAR(50)
attachment_name     TEXT
scan_filename       VARCHAR(255)
scan_size_bytes     BIGINT
scan_source_url     VARCHAR(512)
text_filename       VARCHAR(255)
text_size_bytes     BIGINT
text_source_url     VARCHAR(512)
channel             VARCHAR(50)
source_export_date  DATE

FK: crz_contract_id → contracts.crz_contract_id ON DELETE CASCADE
INDEX (crz_contract_id)
INDEX (attachment_id)
INDEX (scan_filename)
INDEX (text_filename)
```

#### 6. `organizations`
```
id                  SERIAL PRIMARY KEY
ico                 VARCHAR(20)
normalized_name     TEXT
display_name        TEXT
address             TEXT
entity_type         VARCHAR(50)
rpo_entity_id       INTEGER
first_seen_at       TIMESTAMP DEFAULT NOW()
last_seen_at        TIMESTAMP DEFAULT NOW()

PARTIAL UNIQUE INDEX idx_organizations_ico ON organizations (ico) WHERE ico IS NOT NULL
INDEX (normalized_name)
```

#### 7. `suppliers`
```
id                  SERIAL PRIMARY KEY
ico                 VARCHAR(20)
normalized_name     TEXT
display_name        TEXT
address             TEXT
entity_type         VARCHAR(50)
is_probable_natural_person BOOLEAN DEFAULT FALSE
rpo_entity_id       INTEGER
first_seen_at       TIMESTAMP DEFAULT NOW()
last_seen_at        TIMESTAMP DEFAULT NOW()

PARTIAL UNIQUE INDEX idx_suppliers_ico ON suppliers (ico) WHERE ico IS NOT NULL
INDEX (normalized_name)
INDEX (is_probable_natural_person)
```

#### 8. `risk_flags`
```
id                  SERIAL PRIMARY KEY
flag_code           VARCHAR(50) NOT NULL
name                VARCHAR(200) NOT NULL
description         TEXT
severity_default    VARCHAR(20) NOT NULL
methodology         TEXT
is_active           BOOLEAN DEFAULT TRUE
phase               VARCHAR(20) DEFAULT 'mvp'

UNIQUE (flag_code)
```

#### 9. `contract_risk_flags`
```
id                  SERIAL PRIMARY KEY
crz_contract_id     VARCHAR(50) NOT NULL → contracts.crz_contract_id
flag_id             INTEGER NOT NULL → risk_flags.id
source_run_id       INTEGER → ingestion_runs.id
severity            VARCHAR(20) NOT NULL
reason              TEXT
evidence_json       JSONB
created_at          TIMESTAMP DEFAULT NOW()

FK: crz_contract_id → contracts.crz_contract_id ON DELETE CASCADE
FK: flag_id → risk_flags.id ON DELETE RESTRICT
FK: source_run_id → ingestion_runs.id ON DELETE SET NULL
INDEX (crz_contract_id)
INDEX (flag_id)
INDEX (severity)
INDEX (created_at)
INDEX (source_run_id)
```

**Re-flagging lifecycle:**
```sql
BEGIN;
  DELETE FROM contract_risk_flags
    WHERE crz_contract_id = :contract_id
      AND source_run_id = :old_run_id;
  INSERT INTO contract_risk_flags (crz_contract_id, flag_id, source_run_id, severity, reason, evidence_json)
    VALUES (...);
COMMIT;
```
All flags for a contract are recomputed as a batch tied to the current ingestion run. Old flags from the previous run are deleted before inserting new ones. This ensures flags always reflect the current data state and are traceable to a specific ingestion run.

#### 10. `ingestion_runs`
```
id                  SERIAL PRIMARY KEY
run_type            VARCHAR(20) DEFAULT 'daily'
started_at          TIMESTAMP DEFAULT NOW()
finished_at         TIMESTAMP
status              VARCHAR(20) DEFAULT 'running'
records_seen        INTEGER DEFAULT 0
records_inserted    INTEGER DEFAULT 0
records_updated     INTEGER DEFAULT 0
error_message       TEXT

INDEX (status)
INDEX (started_at)
```

**Concurrent ingestion guard:**
```python
def acquire_ingestion_lock(session: Session, run_type: str) -> int:
    in_progress = session.query(IngestionRun).filter(
        IngestionRun.status == 'running',
        IngestionRun.run_type == run_type
    ).first()
    if in_progress:
        raise RuntimeError(
            f"Ingestion already in progress (run_id={in_progress.id}, "
            f"started_at={in_progress.started_at})"
        )
    run = IngestionRun(run_type=run_type, status='running')
    session.add(run)
    session.commit()
    return run.id
```

#### 11. `data_quality_checks`
```
id                  SERIAL PRIMARY KEY
run_id              INTEGER NOT NULL → ingestion_runs.id
check_name          VARCHAR(100) NOT NULL
status              VARCHAR(20)
observed_value      TEXT
threshold           TEXT
details_json        JSONB

FK: run_id → ingestion_runs.id ON DELETE CASCADE
INDEX (run_id)
INDEX (check_name)
```

Records parser validation checks: expected vs actual record counts, schema drift detection (fingerprint change), required field presence rates, etc.

#### 12. `organization_metrics_monthly`
```
id                  SERIAL PRIMARY KEY
organization_id     INTEGER NOT NULL → organizations.id
month               DATE NOT NULL
contract_count      INTEGER DEFAULT 0
total_value         NUMERIC(18,2) DEFAULT 0
flagged_contract_count INTEGER DEFAULT 0
top_supplier_share  NUMERIC(5,4)

FK: organization_id → organizations.id ON DELETE CASCADE
UNIQUE (organization_id, month)
```

Created in Phase 2, populated later when enough data exists. Initially empty.

#### 13. `supplier_metrics_monthly`
```
id                  SERIAL PRIMARY KEY
supplier_id         INTEGER NOT NULL → suppliers.id
month               DATE NOT NULL
contract_count      INTEGER DEFAULT 0
total_value         NUMERIC(18,2) DEFAULT 0
buyer_count         INTEGER DEFAULT 0
growth_ratio        NUMERIC(10,4)

FK: supplier_id → suppliers.id ON DELETE CASCADE
UNIQUE (supplier_id, month)
```

Created in Phase 2, populated later when enough data exists. Initially empty.

---

**Tests:**
- [ ] Docker PostgreSQL starts and accepts connections on 5433
- [ ] Alembic migration runs successfully
- [ ] Can insert and query all 13 model types
- [ ] Upsert on contracts works (`ON CONFLICT UPDATE`)
- [ ] Partial unique index on `organizations.ico` rejects duplicate non-null IČOs
- [ ] Partial unique index on `suppliers.ico` rejects duplicate non-null IČOs
- [ ] Partial unique index allows multiple NULL IČOs
- [ ] FK constraints enforced (cannot insert contract_risk_flag with invalid crz_contract_id)
- [ ] Concurrent ingestion guard prevents duplicate running ingestion

**Definition of done:** All 13 MVP tables created with correct FK constraints, indexes, and partial unique indexes. Can insert/query via SQLAlchemy.

**Estimated complexity:** 5/10  
**Recommended agent:** subagent (well-defined schema)

---

### Phase 3: Data Ingestion Pipeline

**Goal:** End-to-end pipeline from CRZ export download to database with cleaning, entity normalization, and ingestion guards.

**Prerequisite:** Phase 1 + Phase 2

**Files to create/modify:**
```
app/ingestion/jobs.py             — Main ingestion orchestrator
app/ingestion/crz/client.py       — Rate-limited HTTP client
app/transforms/cleaning.py        — Price/date/ICO/name cleaning
app/transforms/entities.py        — Organization/supplier normalization
app/db/repository.py              — Database CRUD operations
tests/ingestion/test_client.py    — HTTP client mock tests
tests/ingestion/test_jobs.py      — Ingestion orchestrator tests
tests/transforms/test_cleaning.py — Cleaning unit tests
```

**Key logic:**
1. Check concurrent ingestion guard — fail if another run is in progress
2. Create `ingestion_runs` record with status='running'
3. Determine date range (configurable rolling window, default 90 days)
4. For each date: download ZIP → checksum → parse XML → schema fingerprint → clean → upsert to DB
5. Create/update organization and supplier records
6. Log `data_quality_checks` (record counts, schema fingerprint matches)
7. Update `ingestion_runs` record with final stats and status='completed'/'failed'

**Slovak price parsing rules (CRZ-specific):**

CRZ prices appear in formats specific to Slovak conventions. The parser must handle all of these:

| Input Format | Example | Parsed Value | Rule |
|---|---|---|---|
| Comma decimal | `"1 200,50"` | `1200.50` | Replace space thousands-separator, replace comma with dot |
| Space thousands | `"50 000"` | `50000.0` | Remove space |
| EUR suffix | `"1 200,50 EUR"` | `1200.50` | Strip `EUR` suffix (and variants `€`, `eur`) |
| Integer string | `"5000"` | `5000.0` | Direct conversion |
| Zero | `"0"` | `0.0` | Valid, not NULL |
| Negative | `"-500"` | `-500.0` | Preserve sign |
| Empty string | `""` | `NULL` | No price information |
| Whitespace only | `"  "` | `NULL` | No price information |
| Dot decimal | `"1200.50"` | `1200.50` | Standard decimal notation |
| Mixed | `"1 200,50€"` | `1200.50` | Strip suffix, handle comma+space |

**Parsing algorithm:**
```python
def parse_slovak_price(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    stripped = stripped.rstrip().rstrip('€').rstrip('EUR').rstrip('eur').strip()
    stripped = stripped.replace('\xa0', ' ').replace(' ', '')
    stripped = stripped.replace(',', '.')
    try:
        return Decimal(stripped)
    except InvalidOperation:
        return None
```

**Test cases for Slovak price parsing:**
```python
@pytest.mark.parametrize("input,expected", [
    ("1 200,50",       Decimal("1200.50")),
    ("50 000",          Decimal("50000")),
    ("1 200,50 EUR",   Decimal("1200.50")),
    ("5000",            Decimal("5000")),
    ("0",               Decimal("0")),
    ("-500",            Decimal("-500")),
    ("",                None),
    ("   ",             None),
    ("1\xa0200,50€",   Decimal("1200.50")),
    ("1200.50",         Decimal("1200.50")),
    (None,              None),
])
```

**Other cleaning rules:**
- Date: `"0000-00-00"` → `None`, standard dates → `date` object
- IČO: strip non-digits, validate 8-digit format
- Names: strip whitespace, normalize multiple spaces

**Tests:**
- [ ] Download with mocked HTTP (success, 404, timeout)
- [ ] Checksum verification
- [ ] Idempotent re-ingestion (same data twice = no duplicates)
- [ ] Re-ingestion with changed data (contract updated = upsert, new version in contract_versions)
- [ ] All-fields-empty contract handled gracefully
- [ ] Encoding edge cases (UTF-8 BOM, Latin-1 characters)
- [ ] Zero-contract XML handled (empty `<zmluvy>`)
- [ ] Slovak price parsing: all parametrized test cases pass
- [ ] Date parsing edge cases (`"0000-00-00"`, various formats)
- [ ] IČO normalization (with/without spaces, invalid lengths)
- [ ] Concurrent ingestion guard rejects second simultaneous run
- [ ] Data quality checks recorded (record count, schema fingerprint)

**Definition of done:** Running `make ingest` downloads 90 days of CRZ data into PostgreSQL with concurrent ingestion protection.

**Estimated complexity:** 6/10  
**Recommended agent:** subagent (complex but well-defined)

---

### Phase 4: MVP Risk Flags + Data Cleaning

**Goal:** Compute 6 explainable metadata-only flags for each contract. Implement natural person detection. Address 60% flag rate with compound severity. Implement data freshness warning.

**Prerequisite:** Phase 3 (cleaned contracts in DB)

**Files to create/modify:**
```
app/flags/definitions.py          — Flag catalog (code, name, severity, description)
app/flags/evaluate.py             — Flag evaluation engine with re-flagging lifecycle
app/flags/flags_catalog.py        — Seed flag definitions into DB
app/flags/freshness.py            — Data freshness warning check
app/transforms/natural_person.py  — Natural person detection heuristic
tests/flags/test_evaluate.py      — Flag evaluation tests
tests/flags/test_freshness.py     — Freshness warning tests
tests/transforms/test_natural_person.py — Natural person detection tests
```

**6 MVP flags:**

| Flag Code | Name | Severity | Logic | False-Positive Note |
|-----------|------|----------|-------|---------------------|
| `MISSING_PRICE` | Chýba cena | medium | `price_total IS NULL AND price_contract IS NULL` | Some contracts legitimately do not state a simple price |
| `ZERO_PRICE` | Nulová cena | low | `COALESCE(price_total, price_contract) = 0` | Framework agreements, non-monetary contracts, corrections, or metadata conventions |
| `MISSING_SUPPLIER` | Chýba dodávateľ | medium | `supplier_name IS NULL OR empty` | Some records may encode supplier elsewhere or be special contract types |
| `MISSING_SUPPLIER_ICO` | Chýba IČO dodávateľa | medium | `supplier_ico IS NULL OR empty` | Foreign suppliers, natural persons, or special cases may not have Slovak IČO |
| `INVALID_ICO_FORMAT` | Neplatný formát IČO | low | IČO present but not 8 digits after normalization | Foreign identifiers and formatting quirks |
| `MISSING_BUYER_ICO` | Chýba IČO obstarávateľa | medium | `buyer_ico IS NULL OR empty` | Legacy records or unusual public entities |

**Natural person detection heuristic:**

```python
LEGAL_FORM_SUFFIXES = [
    "s.r.o.", "spol. s r.o.", "a.s.", "v.o.s.", "k.s.",
    "š.p.", "o.z.", "príspevková organizácia", "rozpočtová organizácia",
    "nadácia", "n.o.", "živnostník",
]

def is_probable_natural_person(name: str | None, ico: str | None) -> bool:
    if not name or not name.strip():
        return False
    has_ico = ico and ico.strip() and ico.strip() != "0"
    if has_ico:
        return False
    name_lower = name.strip().lower()
    for suffix in LEGAL_FORM_SUFFIXES:
        if suffix in name_lower:
            return False
    return True
```

Applied during entity normalization in `app/transforms/entities.py`. Suppliers flagged as `is_probable_natural_person = TRUE` have their profiles hidden in the dashboard by default.

**60% flag rate mitigation strategy:**

Individual flags are noisy (60% of contracts flagged). The following measures reduce noise for users:

1. **Compound severity:** Contracts with 3+ flags get elevated visibility (`compound_severity = 'high'` regardless of individual flag severities). This is computed at query time, not stored.

```python
def compound_severity(flags: list[dict]) -> str:
    if len(flags) >= 3:
        return "high"
    severities = {f["severity"] for f in flags}
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    return "low"
```

2. **Dashboard default filter:** `"medium+ severity OR 2+ flags"` — this is the default view, reducing noise from single low-severity flags. Users can toggle to see all flags.

3. **Manual review gate before Phase 5:** Before building the dashboard, manually review a sample of flagged contracts (at least 50 from each severity tier) to validate flag accuracy and adjust thresholds if needed.

**Data freshness warning:**

```python
def check_data_freshness(session: Session) -> dict:
    last_success = session.query(IngestionRun).filter(
        IngestionRun.status == 'completed'
    ).order_by(IngestionRun.finished_at.desc()).first()

    if not last_success:
        return {"status": "no_data", "warning": "No successful ingestion recorded"}

    hours_since = (datetime.utcnow() - last_success.finished_at).total_seconds() / 3600

    if hours_since > 48:
        return {
            "status": "stale",
            "warning": f"Last successful ingestion was {hours_since:.0f} hours ago (>48h)",
            "last_success": last_success.finished_at,
        }
    return {"status": "fresh", "last_success": last_success.finished_at}
```

This is displayed on the "Stav dát" page and as a banner on the home page when data is stale.

**Re-flagging lifecycle (detailed):**

When flag evaluation runs after a new ingestion:
1. Get the current `run_id` from the ingestion run
2. For each contract:
   a. Evaluate all active flags against current contract data
   b. `DELETE FROM contract_risk_flags WHERE crz_contract_id = :id AND source_run_id != :current_run_id`
   c. `INSERT INTO contract_risk_flags (...) VALUES (...)` for each triggered flag
3. After all contracts processed, any flags with `source_run_id` pointing to old runs that weren't refreshed are orphaned and should be cleaned up

This ensures:
- Flags always reflect the latest data
- Flags are traceable to a specific ingestion run
- Re-ingestion doesn't accumulate stale flags

**Tests:**
- [ ] Each flag fires for correct conditions
- [ ] Each flag does NOT fire for valid data
- [ ] Edge cases (zero vs null, whitespace-only names)
- [ ] Flag catalog seeding is idempotent
- [ ] Re-flagging lifecycle: old flags deleted, new flags inserted with current run_id
- [ ] Natural person detection: empty IČO + no legal suffix → True
- [ ] Natural person detection: has IČO → False
- [ ] Natural person detection: empty IČO + "s.r.o." → False
- [ ] Natural person detection: empty name → False
- [ ] Compound severity: 3+ flags → "high"
- [ ] Compound severity: 1-2 flags → max individual severity
- [ ] Data freshness: no successful run → warning
- [ ] Data freshness: run > 48h ago → stale warning
- [ ] Data freshness: recent run → fresh

**Definition of done:** Running flag evaluation marks ~60% of contracts with at least one flag. Compound severity works. Data freshness warning displays when stale. Manual review of sample flagged contracts completed before proceeding to Phase 5.

**Estimated complexity:** 5/10  
**Recommended agent:** subagent (well-defined rules, but manual review gate required)

**Quality gate:** ⚠️ Manual review of at least 50 flagged contracts required before proceeding to Phase 5.

---

### Phase 5: Streamlit Dashboard

**Goal:** Searchable, filterable dashboard with CRZ links, CSV export, natural person hiding, and connection pooling.

**Prerequisite:** Phase 3 + Phase 4 (including manual review gate)

**Files to create/modify:**
```
app/dashboard/Home.py                   — Main entry + search
app/dashboard/pages/1_Oznamy.py         — Flagged contracts table
app/dashboard/pages/2_Detail_zmluvy.py  — Contract detail
app/dashboard/pages/3_Organizacie.py    — Organization profile
app/dashboard/pages/4_Dodavatelia.py    — Supplier profile
app/dashboard/pages/5_Metodika.py       — Methodology explanation
app/dashboard/pages/6_Stav_dat.py       — Data status + freshness warning
app/dashboard/components/filters.py     — Shared filter components
app/dashboard/components/queries.py     — Shared DB queries
app/dashboard/components/export.py      — CSV export helper
app/dashboard/components/connection.py  — Connection pooling setup
```

**Dashboard pages (Slovak UI):**

1. **Domov (Home):** Search box, date filter, overview stats, disclaimer banner, data freshness warning
2. **Oznamy (Flags):** Filterable table of flagged contracts with CRZ links. Default filter: "medium+ severity OR 2+ flags". Compound severity indicator for 3+ flag contracts.
3. **Detail zmluvy:** Full contract metadata + flags + CRZ link + attachment links
4. **Organizácie:** Organization list → profile with metrics
5. **Dodávatelia:** Supplier list → profile (hidden for natural persons, shown only at contract level)
6. **Metodika:** Flag explanations, methodology, disclaimers
7. **Stav dát:** Last ingestion, failed runs, record counts, data freshness warning banner

**Streamlit connection pooling:**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_engine = None
_SessionFactory = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
        )
    return _engine

def get_session():
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine())
    return _SessionFactory()
```

Use `@st.cache_resource` for the engine to avoid creating multiple pools per Streamlit rerun.

**Key UI requirements:**
- Slovak language throughout
- Disclaimer banner on every page
- Data freshness warning banner when last ingestion > 48h ago
- "Otvoriť v CRZ" link button (opens in new tab)
- "Príloha" link button where available
- CSV export with embedded disclaimer header
- Filter by severity, flag type, date range, organization, supplier
- Default filter: "medium+ severity OR 2+ flags" (compound severity)
- Natural person supplier profiles hidden by default
- Pagination for large result sets

**Definition of done:** User can search contracts, view details, open CRZ links, filter by flags with compound severity default, see data freshness warning, export CSV.

**Estimated complexity:** 6/10  
**Recommended agent:** subagent (many files but pattern is repetitive)

---

### Phase 6: Documentation & Portfolio Polish

**Goal:** Make the project presentable to hiring managers.

**Prerequisite:** Phase 5

**Files to create/modify:**
```
README.md                         — Full project documentation (English)
docs/methodology.md               — Flag methodology (Slovak + English)
docs/limitations.md               — Known limitations
docs/architecture.md              — Architecture diagram (text)
docs/source-notes.md              — Source data notes
```

**README sections (English):**
1. Problem statement
2. What it does / doesn't do
3. Architecture overview
4. Data sources
5. Methodology (flags explained)
6. Quick start (local setup)
7. Screenshots
8. Known limitations
9. Roadmap

**Definition of done:** A recruiter can understand the project in 5 minutes from README alone.

**Estimated complexity:** 3/10  
**Recommended agent:** subagent (writing task)

---

### Phase 7: Final Verification & Push

**Goal:** Everything works end-to-end locally, code pushed to GitHub.

**Checklist:**
- [ ] `docker compose up -d` starts PostgreSQL on port 5433
- [ ] `make migrate` runs migrations
- [ ] `make ingest` downloads and ingests 90 days of CRZ data
- [ ] `make dashboard` starts Streamlit
- [ ] All dashboard pages work
- [ ] Data freshness warning displays correctly
- [ ] CRZ links open correctly
- [ ] CSV export includes disclaimer
- [ ] Natural person profiles hidden by default
- [ ] Compound severity filter works correctly
- [ ] `make test` passes all tests
- [ ] `make lint` passes
- [ ] Code pushed to GitHub

---

### Phase 8: Production Deployment [DEFERRED]

**Status:** ⚠️ DEFERRED — Not in current implementation scope. Documented here for planning purposes only.

**Goal:** Deploy to Hetzner server with GitHub pull/autodeploy.

**Original scope (preserved for future reference):**
```
docker-compose.prod.yml    — Production Docker Compose (resource limits, restart policies)
deploy/                    — Deployment scripts
docs/deployment.md         — Deployment documentation
```

**Tasks (when activated):**
- [ ] Production Docker Compose with resource limits and restart policies
- [ ] Environment variable management for production
- [ ] Database volume and automated backups (daily PG dump, 7 daily + 4 weekly retention)
- [ ] Cron/systemd timer for daily ingestion
- [ ] Health check endpoints
- [ ] Deployment documentation
- [ ] HTTPS setup (reverse proxy or Streamlit native TLS)
- [ ] Monitoring and alerting

**Prerequisites for activation:**
- Phase 7 complete (MVP stable locally)
- Hetzner VPS provisioned
- DNS/domain configured
- Security review completed

**Estimated complexity:** 6/10  
**Estimated time:** 1 week (when activated)

---

## Dependency Graph

```
Phase 0 (Setup) ✅
    ↓
Phase 1 (Parser) ← independent, can test standalone
    ↓
Phase 2 (Database) ← independent of Phase 1, but needs Phase 1 for data
    ↓
Phase 3 (Ingestion) ← depends on Phase 1 + Phase 2
    ↓
Phase 4 (Flags + Cleaning) ← depends on Phase 3
    ↓  ⚠️ Manual review gate (50+ flagged contracts)
Phase 5 (Dashboard) ← depends on Phase 3 + Phase 4
    ↓
Phase 6 (Docs) ← depends on Phase 5
    ↓
Phase 7 (Final) ← depends on all
    ↓
Phase 8 (Production) ← DEFERRED, depends on Phase 7 + server
```

**Parallelization opportunity:** Phase 1 and Phase 2 can be done in parallel by different subagents.

---

## Quality Gates

After each phase:
1. **Agent reports** what was done, files created, tests status
2. **User reviews** code quality, correctness, architecture
3. **User decides** to proceed or request changes
4. Only then do we move to the next phase

**Special quality gates:**
- **Phase 4 → Phase 5:** Manual review of at least 50 flagged contracts required before building the dashboard UI. Verify that flags are reasonable and adjust thresholds if needed.
- **Phase 7 → Phase 8:** Full end-to-end verification on local machine before considering production deployment.

---

## Estimated Timeline

| Phase | Time | Agent | Notes |
|-------|------|-------|-------|
| Phase 0 | ✅ Done | Direct | Port 5433, 90-day window |
| Phase 1 | ~30 min | Subagent | Includes schema fingerprinting |
| Phase 2 | ~35 min | Subagent | 13 tables with FK + partial indexes |
| Phase 3 | ~45 min | Subagent | Slovak price parsing, ingestion guard |
| Phase 4 | ~30 min | Subagent | Flags + natural person + compound severity |
| Phase 5 | ~50 min | Subagent | Connection pooling, freshness warning |
| Phase 6 | ~20 min | Subagent | Writing task |
| Phase 7 | ~15 min | Direct | Verification checklist |
| Phase 8 | DEFERRED | — | Not in current scope |
| **Total (0-7)** | **~3.5 hours** | | |

---

## Edge Case Test Matrix

These tests span multiple phases and must all pass before Phase 7:

| Category | Test | Phase |
|----------|------|-------|
| Re-ingestion | Same export ingested twice → no duplicate contracts | 3 |
| Re-ingestion | Contract data changed → contract updated + new version | 3 |
| Re-flagging | Old flags deleted, new flags with current run_id | 4 |
| All-fields-empty | Contract with all fields empty → parsed without crash | 1, 3 |
| Encoding | UTF-8 BOM in XML → parsed correctly | 1 |
| Encoding | Latin-1 characters in names → stored correctly | 3 |
| Zero-contract XML | Empty `<zmluvy>` → parsed, 0 records logged | 1 |
| Slovak price | `"1 200,50 EUR"` → `1200.50` | 3 |
| Slovak price | `""` → `NULL` | 3 |
| Slovak price | `"0"` → `0.0` (not NULL) | 3 |
| Slovak price | `"-500"` → `-500.0` | 3 |
| Natural person | No IČO + no legal suffix → probable natural person | 4 |
| Natural person | Has IČO → not natural person | 4 |
| Natural person | No IČO + "s.r.o." → not natural person | 4 |
| Data freshness | No successful ingestion → warning displayed | 5 |
| Data freshness | Ingestion > 48h ago → stale warning | 5 |
| Compound severity | 3+ flags → elevated to high | 4 |
| Concurrent guard | Two simultaneous ingestion attempts → second rejected | 3 |
| Schema drift | Different XML element set → new fingerprint logged | 1 |
