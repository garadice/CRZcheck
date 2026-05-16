# Source Data Documentation — CRZ Risk & Quality Monitor

## 1. Overview

This document describes the source data consumed by the CRZ Risk & Quality Monitor project. Data originates from Slovakia's **Central Register of Contracts** (*Centrálny register zmlúv*, abbreviated **CRZ**), a government-run database of public-sector contracts maintained by the Ministry of Interior of the Slovak Republic.

The CRZ publishes one ZIP archive per calendar day containing every contract reported that day. The monitor downloads, parses, and analyses these daily snapshots to surface procurement risk signals and data-quality metrics.

## 2. What Is the CRZ?

The Central Register of Contracts is a publicly accessible, freely downloadable register operated under **Act No. 546/2010 Coll.** (*zákon č. 546/2010 Z. z.*). Under this law, Slovak public institutions — ministries, municipalities, state-owned enterprises, schools, hospitals, and similar bodies — are required to publish contracts that exceed defined thresholds.

Key characteristics:

- **Operator:** Ministry of Interior of the Slovak Republic (*Ministerstvo vnútra SR*)
- **Public availability:** Yes — free, no authentication required
- **Publication requirement:** Mandatory for covered public institutions
- **Validation:** The CRZ does **not** validate metadata completeness; quality depends entirely on the reporting institution
- **Access URL:** `https://www.crz.gov.sk/`

## 3. Data Format

### 3.1 Download URL Pattern

```
https://www.crz.gov.sk/export/YYYY-MM-DD.zip
```

| Property | Value |
|---|---|
| Example URL | `https://www.crz.gov.sk/export/2024-12-15.zip` |
| HTTP status on success | `200` |
| Response content type | `application/zip` |
| Archive size (typical) | ~3.2 MB per day |
| Contracts per day (typical) | ~2,700 (varies by weekday/holiday) |
| Encoding | UTF-8 |

Each ZIP archive contains exactly one file: `YYYY-MM-DD.xml`. An empty `<zmluvy/>` root element is valid and represents a day with zero reported contracts.

### 3.2 XML Structure

```xml
<?xml version="1.0" encoding="utf-8"?>
<zmluvy>
  <zmluva>
    <id>123456</id>
    <nazov>Contract title</nazov>
    <predmet>Subject description</predmet>
    <zs1>Buyer Name</zs1>
    <zs2>Supplier Name</zs2>
    <ico>12345678</ico>
    <ico1>87654321</ico1>
    <!-- ... 27 more tags ... -->
    <prilohy>
      <priloha>
        <id_suboru>...</id_suboru>
        <nazov>...</nazov>
        <typ>...</typ>
        <velkost>...</velkost>
        <datum>...</datum>
        <url>...</url>
        <hash>...</hash>
      </priloha>
    </prilohy>
  </zmluva>
</zmluvy>
```

- **Root element:** `<zmluvy>`
- **Contract element:** `<zmluva>` — 34 child tags per contract
- **Attachment element:** `<priloha>` — 7 child tags per attachment, nested inside `<prilohy>`

### 3.3 Key Fields

| XML Tag | Description |
|---|---|
| `id` | Unique contract identifier in CRZ |
| `nazov` | Contract title |
| `zs1` | Party 1 name — **~95% buyer**, order is not guaranteed |
| `zs2` | Party 2 name — **~95% supplier**, order is not guaranteed |
| `ico` | IČO (business ID) for party corresponding to `zs1` |
| `ico1` | IČO for party corresponding to `zs2` |
| `cena` | Contract price (European decimal format) |
| `datum` | Contract date |
| `typ` | Contract type code |
| `druh` | Contract kind code |

> **Note on `zs1`/`zs2` ordering:** The buyer/supplier assignment is approximately 95% reliable but CAN vary. The `ico`/`ico1` mapping follows the same ordering, so the pair (`zs1`, `ico`) always refers to the same entity. Heuristic or manual correction may be needed for the remaining ~5%.

## 4. Data Quality Observations

### 4.1 Summary Statistics

| Issue | Approximate Rate |
|---|---|
| Contracts with zero or missing price | ~34.5% |
| Missing supplier IČO | ~23% |
| Missing buyer IČO | ~17.5% |
| Sentinel date `"0000-00-00"` | Frequent — must be parsed as `NULL` |

### 4.2 Known Issues

1. **Sentinel dates.** The string `"0000-00-00"` appears frequently in date fields. This must be parsed as `NULL`, not as a valid date. Failure to handle this will cause date-parsing errors.

2. **Zero-price contracts.** Roughly one-third of contracts report a price of `0` or omit the price element entirely. This may reflect genuinely zero-value contracts, reporting omissions, or price fields left intentionally blank.

3. **Missing IČO values.** Both buyer and supplier IČO fields are frequently absent, with supplier IČO missing more often than buyer IČO. This limits de-duplication and entity-resolution logic.

4. **European number format.** Prices use the European convention: **dot** as thousands separator, **comma** as decimal separator.
   ```
   "1.234,56"  →  1234.56
   "500,00"    →  500.00
   "10.000"    →  10000
   ```
   Parsing code must strip dots, replace the comma with a dot, and convert to float/decimal.

5. **HTML entities in text fields.** Some contracts contain HTML entities (e.g., `&amp;`, `&lt;`) in free-text fields such as titles and subject descriptions. These must be decoded before storage.

6. **IČO formatting inconsistencies.** IČO values may include leading zeros, embedded spaces, or non-digit characters. Normalisation (strip non-digits, zero-pad to 8 digits) is recommended before comparison or lookup.

7. **Buyer/supplier order instability.** As noted above, `zs1`/`zs2` does not always correspond to buyer/supplier respectively. The ~5% misalignment requires heuristic handling — legal-form suffixes in names are one useful signal.

8. **Empty daily snapshots.** A valid ZIP/XML with an empty `<zmluvy/>` root is normal (e.g., holidays, weekends). The ingestion pipeline must handle zero-contract days gracefully.

9. **Legal-form suffixes in supplier names.** Slovak legal entities carry distinguishing suffixes that help classify parties as legal entities vs. natural persons. The 12 recognised suffixes are:

   | Suffix | Legal Form |
   |---|---|
   | `s.r.o.` | Limited liability company (spoločnosť s ručením obmedzeným) |
   | `spol. s r.o.` | Limited liability company (variant) |
   | `a.s.` | Joint-stock company (akciová spoločnosť) |
   | `v.o.s.` | General commercial partnership (verejná obchodná spoločnosť) |
   | `k.s.` | Limited partnership (komanditná spoločnosť) |
   | `š.p.` | Sole proprietor (živnostník-podnikateľ) |
   | `o.z.` | Civic association (občianske združenie) |
   | `príspevková organizácia` | Contributory organization (public budgetary) |
   | `rozpočtová organizácia` | Budgetary organization (public) |
   | `nadácia` | Foundation |
   | `n.o.` | Non-profit organization (nezisková organizácia) |
   | `živnostník` | Self-employed tradesperson |

10. **No upstream validation.** The CRZ does not enforce metadata completeness or correctness. All quality control must happen downstream, in this project's ingestion and analysis layers.

## 5. Legal Context

| Item | Detail |
|---|---|
| Governing law | Act No. 546/2010 Coll. on the Central Register of Contracts |
| Responsible authority | Ministry of Interior of the Slovak Republic |
| Publication obligation | Mandatory for public institutions above defined thresholds |
| Data licensing | Publicly available, free of charge |
| Rate limiting | Approximately 3 requests/second (observed) |

The data is publicly available and its use for analytical purposes is consistent with the register's intended function. This project does not redistribute raw data; it consumes it for derived analysis only.

## 6. Download Methodology

### 6.1 Rate Limiting

The CRZ server tolerates approximately 3 requests per second. The download scheduler uses conservative intervals with a day/night split to balance throughput against server load:

| Period | Interval |
|---|---|
| Daytime (06:00–22:00 local) | 2.0 seconds between requests |
| Nighttime (22:00–06:00 local) | 0.4 seconds between requests |

### 6.2 Retry Logic

On server errors (HTTP 5xx) or transport failures, the downloader performs up to **3 retry attempts** with **exponential backoff**:

```
Attempt 1:  immediate
Attempt 2:  wait  ~4 seconds
Attempt 3:  wait  ~16 seconds
```

A day that fails all 3 attempts is logged and retried in a subsequent batch cycle.

### 6.3 Integrity Verification

Every downloaded artefact is verified with **SHA-256** checksums:

- **ZIP file:** hashed immediately after download; any tampering or truncation is detected before extraction.
- **Extracted XML:** hashed after extraction; verifies the decompression step produced valid output.

Checksums are stored alongside the raw data for future audit.

### 6.4 Schema Fingerprinting

The parser fingerprints the XML schema (root element name, child tag names, nesting structure) on each daily file. If the CRZ operator changes the XML structure — new fields, renamed tags, altered nesting — the fingerprint mismatch triggers an alert and halts ingestion for that day until the parser is updated.

## 7. Field Mapping Table

The table below maps XML tags from a `<zmluva>` element to database columns in the `contracts` table.

| # | XML Tag | Database Column | Notes |
|---|---|---|---|
| 1 | `id` | `crz_contract_id` | Unique CRZ identifier (primary key source) |
| 2 | `nazov` | `title` | Contract title |
| 3 | `predmet` | `subject` | Subject / description |
| 4 | `zs1` | `buyer_name` | Party 1 — buyer ~95% of the time |
| 5 | `ico` | `buyer_ico` | Buyer IČO; normalise non-digits |
| 6 | `adresa1` | `buyer_address` | Buyer registered address |
| 7 | `zs2` | `supplier_name` | Party 2 — supplier ~95% of the time |
| 8 | `ico1` | `supplier_ico` | Supplier IČO; normalise non-digits |
| 9 | `adresa2` | `supplier_address` | Supplier registered address |
| 10 | `rezort` | `department` | Government department / sector |
| 11 | `typ` | `contract_type` | Type code |
| 12 | `druh` | `contract_kind` | Kind code |
| 13 | `datum` | `contract_date` | `"0000-00-00"` → `NULL` |
| 14 | `datum_zverejnenia` | `publication_date` | Date published on CRZ |
| 15 | `datum_ucinnosti` | `effective_date` | Contract effective date; may be empty |
| 16 | `platnost_do` | `valid_until` | Expiry date; may be empty |
| 17 | `cena` | `price_contract` | European format; `0` or empty → `NULL` |
| 18 | `cena_celkom` | `price_total` | Total price incl. VAT; European format |
| 19 | `mena` | `currency` | Currency code (EUR, etc.) |
| 20 | `stav` | `status` | Contract status code |
| 21 | `url` | `crz_detail_url` | Direct link to CRZ detail page |
| 22 | `ulozenie` | `storage_location` | Internal CRZ storage reference |
| 23 | `identifikator` | `identifier` | Additional identifier |
| 24 | `kod_partnera` | `partner_code` | Partner classification code |
| 25 | `kod_partnera1` | `partner1_code` | Second partner classification |
| 26 | `forma` | `legal_form` | Legal form code |
| 27 | `lehots` | `deadline` | Deadline / term |
| 28 | `poznamka` | `note` | Free-text notes |
| 29 | `zmluvny_vztah` | `contract_relationship` | Relationship type |
| 30 | `prilohy` | *(nested — attachments table)* | Contains `<priloha>` children |
| 31 | `modalita` | `modality` | Procurement modality |
| 32 | `cpv` | `cpv_code` | Common Procurement Vocabulary code |
| 33 | `nuts` | `nuts_code` | NUTS regional classification |
| 34 | `zs1_ico` | *(supplementary)* | Alternate buyer IČO field |

> **Note:** The exact mapping is defined in `app/ingestion/crz/parser.py` (`FIELD_MAP` constant). The table above reflects the mapping at the time of writing; always refer to the source code as the authoritative reference.

---

*Last updated: 2026-05*
