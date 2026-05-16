# CRZ Risk & Quality Monitor — Implementation Plan

Project: **Verejné peniaze bez hmly**  
Working product name: **CRZ Risk & Quality Monitor**  
Plan date: 2026-05-15  
Primary positioning: civic portfolio product and useful public-interest review tool.

## 1. Executive Summary

CRZ Risk & Quality Monitor is a small, maintainable data product for Slovakia that ingests metadata from the Central Register of Contracts (CRZ), cleans and models that metadata, links it to public organization/company reference data where feasible, and surfaces explainable metadata-quality and anomaly signals.

Core value proposition:

> Help users quickly find public contracts and organizations worth checking based on transparent data-quality and anomaly signals.

The product is designed for journalists, local councillors, watchdogs, analysts, and engaged citizens. It reduces manual review time by putting CRZ contracts, organizations, suppliers, metadata signals, and links to original records into a searchable interface.

What it does:

- Ingest CRZ XML metadata.
- Store raw XML and parsed relational metadata.
- Store CRZ contract IDs and stable CRZ detail links.
- Store attachment metadata and source attachment/PDF links where available.
- Compute transparent metadata-only data-quality and risk signals.
- Provide organization, supplier, contract, dashboard, CSV export, and eventually API views.

What it does not do:

- It does not detect corruption.
- It does not accuse people, companies, municipalities, ministries, schools, hospitals, or other organizations.
- It does not make legal conclusions.
- The MVP does not process PDF contents.
- The MVP does not download all PDFs.
- The MVP does not run OCR.
- It does not rank natural persons.

MVP boundary:

- MVP uses metadata only.
- MVP stores and displays CRZ detail links and attachment/PDF links.
- MVP does not process PDF contents.
- Later versions may selectively process PDFs only for contracts already flagged by metadata rules.

## 2. Go / No-Go Assessment

Final recommendation: **Go, with a strict metadata-only MVP and national rolling-window scope.**

Reasons to proceed:

- CRZ provides machine-readable daily ZIP/XML export files.
- Live CRZ export files were verified with date-based URLs such as `https://www.crz.gov.sk/export/2026-05-12.zip`.
- Export XML contains contract metadata, contract IDs, and attachment metadata fields.
- CRZ detail links can be generated reliably using the redirect-style URL `https://www.crz.gov.sk/index.php?ID={contract_id}`.
- Attachment/PDF source URLs are derivable from XML attachment filenames using `https://www.crz.gov.sk/data/att/{filename}`.
- Metadata-only signals are useful enough for a first civic review workflow.
- Not downloading PDFs in MVP sharply reduces cost, legal risk, storage risk, bandwidth risk, and operational complexity.

Reasons not to proceed, unless scope remains disciplined:

- Full historical backfill may be large and time-consuming.
- CRZ XML export schema is not fully represented by the public import XSD; the parser must be based on real export samples and tested for drift.
- RPO enrichment is useful but rate-limited and must be cached.
- Slovensko.Digital APIs are useful but should not be a hard dependency for MVP.
- PDF/OCR processing is complex and can easily dominate the project.
- Risk wording can be misinterpreted if the interface is not careful.

Stop or pause the project if:

- CRZ blocks export access or changes terms in a way that prohibits the intended use.
- Stable CRZ detail/attachment links stop being derivable.
- The project cannot maintain safe terminology and disclaimers.
- Most signals prove too noisy to be useful after manual review.
- Maintenance time exceeds the available 8-10 hours/week for multiple weeks.
- The project drifts into mass PDF mirroring, OCR, or accusatory scoring.

Biggest known unknowns:

- Long-term CRZ export schema stability.
- Completeness and consistency of attachment metadata across older records.
- Accuracy of organization/supplier normalization from CRZ metadata alone.
- Practical RPO/RPVS enrichment throughput under rate limits.
- User adoption outside a portfolio context.

Metadata-only MVP assessment:

- Useful enough for MVP: **yes**.
- PDF processing necessary for initial value: **no**.
- PDF processing is a later enhancement for selected flagged contracts only.
- OCR is last and optional.

## 3. Research Findings

Research basis: official sources and live checks performed in May 2026.

### CRZ Export / Download Page

Official URL: `https://www.crz.gov.sk/stahovanie-udajov-z-crz/`

Data available:

- Daily differential ZIP/XML export files.
- Date-based export URLs, verified with live files.
- Contract metadata and attachment metadata.
- Historical date-based ZIPs appear available for older dates, although many archives may be empty or tiny.

Format:

- ZIP containing one XML file.
- Example: `https://www.crz.gov.sk/export/2026-05-12.zip` contained `2026-05-12.xml`.

Access method:

- Direct HTTPS download.
- URL pattern: `https://www.crz.gov.sk/export/YYYY-MM-DD.zip`.

Rate limits:

- Official page documents machine-access limits:
  - 06:00-20:00: approximately one request per 2 seconds.
  - 20:00-06:00: fewer than 3 requests per second.
- Treat these as applying to all CRZ machine access: exports, detail pages, and attachments.

Observed XML structure:

- Root element: `zmluvy`.
- Repeated contract element: `zmluva`.
- Contract fields observed:
  - `nazov`
  - `ID`
  - `zs1`
  - `zs2`
  - `predmet`
  - `datum_ucinnost`
  - `datum_platnost_do`
  - `suma_zmluva`
  - `suma_spolu`
  - `id`
  - `poznamka`
  - `rezort`
  - `datum_zverejnene`
  - `ico`
  - `stav`
  - `potv_ziadost`
  - `potv_datum`
  - `zdroj`
  - `text_ucinnost`
  - `sidlo`
  - `ico1`
  - `sidlo1`
  - `potvrdenie`
  - `typ`
  - `datum`
  - `popis`
  - `druh`
  - `ref`
  - `internapozn`
  - `popis_predmetu`
  - `poznamka_zmena`
  - `uvo`
  - `chan`
  - `prilohy`

Attachment metadata fields observed inside `prilohy`:

- `ID`
- `nazov`
- `dokument`
- `velkost`
- `dokument1`
- `velkost1`
- `chan`

Observed attachment behavior:

- `dokument` maps to scanned version filename in observed records.
- `dokument1` maps to text version filename in observed records.
- Attachment filenames such as `6732340.pdf` are accessible as `https://www.crz.gov.sk/data/att/6732340.pdf`.

Live sample observations:

- `2026-05-12.xml`: 2,953 contracts, 3,128 attachment records, 75 contracts without attachments.
- `2026-05-01.xml`: 92 contracts, 67 attachment records, 28 contracts without attachments.

Suitability for MVP:

- Strong. CRZ export is the primary MVP source.

Suitability for later full feature scope:

- Strong, with schema drift handling, source monitoring, and backfill throttling.

Stability risk:

- Medium. The export exists and is official, but parser tests must be based on real XML samples because the import XSD is not the same as public export XML.

### CRZ FAQ

Official URL: `https://www.crz.gov.sk/casto-kladene-otazky/`

Data/use:

- User-facing explanation of CRZ behavior and contract access.
- Useful for validating public link patterns and authoritative-source wording.

Important link finding:

- Recent CRZ detail pages may redirect to `/zmluva/{ID}/`.
- Older detail pages may use `/{ID}/`.
- The most robust generated link is `https://www.crz.gov.sk/index.php?ID={contract_id}` because CRZ redirects to the correct current detail page.

Suitability for MVP:

- Use for detail-link generation policy and user-facing source attribution.

### CRZ Technical Zone / User Manual / Methodology

Relevant URLs:

- `https://www.crz.gov.sk/technicka-zona/`
- `https://www.crz.gov.sk/data/files/39_user-manual_3.pdf`
- `https://www.crz.gov.sk/schema/crz.xsd`
- `https://www.crz.gov.sk/data/files/44_zmluva.xml`

Findings:

- CRZ documentation distinguishes scanned and text versions of attachments.
- The import XSD and sample import XML include fields and base64 attachment content intended for submitting contracts into CRZ, not the same structure as the public export XML.
- The public export parser must be validated against actual export XML files, not only the XSD.

Suitability for MVP:

- Use for terminology, attachment version semantics, and background.
- Do not base the MVP export parser solely on the import XSD.

### RPO - Register právnických osôb

Official URLs:

- `https://rpo.statistics.sk/docs/oznam.html`
- `https://susrrpo.docs.apiary.io/`
- `https://api.statistics.sk/rpo/v1/search?identifier={ico}`

Data available:

- Official organization/legal entity reference data.
- Search by identifier/IČO.
- JSON API responses include names, addresses, legal form, activity, and related metadata where available.

Format:

- JSON API.

Access method:

- HTTPS API.

Licensing/terms:

- Live API response included CC BY 4.0 license text and references to the legal basis for RPO open data.

Rate limits:

- Live checks hit HTTP 429 after a small number of quick calls.
- Treat as rate-limited and cache aggressively.

Suitability for MVP:

- Optional. Good for cached enrichment, but MVP should work without real-time RPO calls.

Suitability for later full feature scope:

- Strong, if enrichment is batched, cached, and rate-limited.

Stability risk:

- Medium. Official source, but practical throttling and docs availability require robust backoff.

### Slovensko.Digital Open APIs / Open Data

Official URLs:

- `https://ekosystem.slovensko.digital/otvorene-api`
- `https://ekosystem.slovensko.digital/otvorene-data`
- `https://ekosystem.slovensko.digital/podmienky`

Data available:

- APIs and datasets for CRZ, RPO/RPO2, RUZ, and other Slovak public datasets.

Format:

- JSON APIs and datahub-style endpoints.

Access method:

- Public unauthenticated API access for some endpoints.

Rate limits:

- Public unauthenticated API limit documented as 60 requests/minute/IP.

Terms:

- Terms allow reuse with attribution and no warranty.
- Data is informational.

Live reliability note:

- Some datahub endpoint checks timed out during research.

Suitability for MVP:

- Do not make it a hard MVP dependency.
- Useful as optional comparison, fallback, or enrichment source.

Suitability for later full feature scope:

- Useful, with timeout handling and dependency isolation.

Stability risk:

- Medium. Strong ecosystem value, but external API dependency adds operational risk.

### RPVS - Register partnerov verejného sektora

Official URL:

- `https://www.justice.gov.sk/sluzby/register-partnerov-verejneho-sektora/open-data/`

Swagger/OpenAPI:

- `https://rpvs.gov.sk/opendatav2/swagger/index.html`
- `https://rpvs.gov.sk/opendatav2/swagger/v2/swagger.json`

Data available:

- Public-sector partners.
- Beneficial owners.
- Authorized persons.
- Related partner records.

Format:

- OpenAPI 3 JSON API.

Access method:

- HTTPS API.

Suitability for MVP:

- Not needed for MVP.

Suitability for later full feature scope:

- Useful for supplier enrichment, but must be handled carefully because beneficial-owner data can involve natural persons.

Stability risk:

- Medium. Official API exists, but legal/ethical treatment and schema changes need monitoring.

### Transparex

Official URLs:

- `https://www.transparex.sk/`
- `https://www.transparex.sk/privacy`
- `https://www.transparex.sk/imports-report`

What it is:

- Broad commercial/analytical transparency platform using many public registers.
- Covers procurement, companies, public-sector relationships, people/connections, subscriptions, and risk-style business intelligence.

Suitability for integration:

- Do not compete directly.
- Do not attempt to reproduce its broad intelligence platform.

Competitive implication:

- Our defensible niche is smaller: metadata-quality and anomaly radar over CRZ, optimized for fast human review, transparent logic, and portfolio-grade reproducibility.

### Aliancia Fair-play Historical Projects

Official URL:

- `https://www.fair-play.sk/projects.html`

Relevant projects:

- OtvorenéZmluvy.
- Z našich daní.

Finding:

- Important civic-tech precedent, but historical projects appear ended or not active as current CRZ monitoring products.

Suitability for MVP:

- Use as design inspiration and positioning context, not as dependency.

### VOKO

URL:

- `https://voko.sk/en/`

Finding:

- Covers public procurement and CRZ since 2016.

Competitive implication:

- Another reason to stay narrow and transparent. Avoid trying to become a complete procurement intelligence or relationship-analysis platform.

### OpenTender Slovakia

URL:

- `https://data.open-contracting.org/en/publication/88`

Finding:

- Procurement/OCDS-oriented dataset context, not a direct CRZ metadata-quality radar.

Suitability:

- Not MVP dependency.
- Later background for procurement lifecycle integration only if scope is expanded.

### ORSF

URLs:

- `https://orsf.sk/pravne`
- `https://orsf.sk/pricing`

Finding:

- Aggregated company registry and API, unofficial/beta-style service.
- May include extra person/connection data and paid/gated features.

Suitability:

- Not MVP dependency.
- Consider only later, and only if official RPO/RPVS/Slovensko.Digital sources are insufficient.

### Existing CRZ Scraper Reference

URL:

- `https://github.com/slovak-egov/CRZ-scraper`

Finding:

- Existing Python scraper downloads CRZ XML, creates CSVs, filters by IČO, downloads contracts, and extracts text/tables.

Use:

- Useful implementation reference.
- Do not copy mass PDF behavior into MVP.

## 4. Competitor and Alternative Tool Analysis

### CRZ.gov.sk

What it does well:

- Authoritative source.
- Provides official contract detail pages and attachments.
- Provides XML export for machine processing.

What it does not solve:

- Limited analytical workflow.
- No focused metadata-quality radar.
- No user-friendly anomaly dashboard for repeated monitoring.

Strategy:

- Integrate via links and source attribution.
- Always treat CRZ as authoritative.

### Transparex

What it does well:

- Broad public-register intelligence.
- Commercial-grade aggregation and analysis.
- Company/person/relationship-oriented tooling.

What it does not solve for this project:

- Not a small, transparent, reproducible civic portfolio project.
- May not foreground explainable CRZ metadata-quality signals.

Strategy:

- Avoid direct competition.
- Position as narrow, transparent, open-methodology CRZ metadata radar.

### Slovensko.Digital APIs/Datahub

What it does well:

- Developer-friendly access to many Slovak public datasets.
- Can reduce integration effort.

What it does not solve:

- API dependency and timeout risk.
- May not expose every field needed exactly as CRZ export does.

Strategy:

- Optional enrichment/fallback.
- CRZ official export remains primary.

### OtvorenéZmluvy / Z našich daní

What they did well:

- Civic-tech framing.
- Public spending transparency.
- Public-interest discovery.

What they do not solve now:

- Historical projects, not active modern CRZ metadata-quality monitoring.

Strategy:

- Learn from them.
- Do not depend on them.

### VOKO and Other Active Tools

What they do well:

- Broader procurement/CRZ analysis and long-term datasets.

What they do not solve:

- The niche of a small, explainable, maintainable metadata-quality monitor with careful non-accusatory wording.

Strategy:

- Avoid broad procurement intelligence.
- Build a focused review workflow.

Defined niche:

> Metadata-quality and anomaly radar over CRZ, optimized for fast human review, not a full procurement intelligence platform.

## 5. Target Users and Use Cases

### Local Journalist

Job to be done:

- Quickly find contracts in a municipality, public organization, or supplier history that deserve manual checking.

Example question:

- "Which recent contracts for this organization have missing price, missing supplier IČO, or unusual supplier growth?"

Expected output:

- Searchable flagged-contract table with reason, severity, CRZ link, and attachment link.

Why existing tools may not be enough:

- CRZ is authoritative but not optimized for anomaly triage.

Example:

- A journalist searches for a municipality and sees contracts with zero price, missing IČO, or sudden supplier growth, then opens the CRZ/PDF link manually.

### Local Councillor

Job to be done:

- Prepare for council oversight and budget meetings.

Example question:

- "Which contracts over a threshold were published in the last 30 days and have metadata signals?"

Expected output:

- CSV export of contracts with contract ID, title, supplier, buyer, price, date, flag, reason, CRZ link, and attachment link.

Example:

- A councillor checks all contracts over a threshold in the last 30 days and exports flagged contracts to CSV before a council meeting.

### Watchdog Organization

Job to be done:

- Monitor many organizations repeatedly.

Example question:

- "Did any watched organization publish a new high-value contract with incomplete supplier metadata?"

Expected output:

- Dashboard and later email/Telegram alert.

Example:

- A watchdog monitors 50 organizations and receives an alert when a new high-value contract has incomplete supplier metadata.

### Analyst

Job to be done:

- Investigate metadata quality patterns, supplier concentration, and changes over time.

Expected output:

- Aggregated organization/supplier metrics, CSV exports, and documented flag logic.

### Engaged Citizen

Job to be done:

- Understand what contracts are worth opening in official CRZ.

Expected output:

- Simple search and detail pages with cautious wording and direct CRZ links.

## 6. Product Positioning

What to say:

- "This tool highlights metadata-quality and anomaly signals in CRZ records."
- "Signals are designed to help manual review."
- "The original CRZ record is authoritative."
- "A signal does not imply wrongdoing."
- "PDF/text checks, if added later, identify possible mismatches that require manual review."

What not to say:

- "Corruption detector."
- "Fraud detector."
- "Illegal contract."
- "Suspicious person."
- "Blacklist."
- "Guilty."
- "Proved corruption."
- "Dishonest supplier."

Preferred terminology:

- data-quality monitor
- data-quality signal
- risk signal
- anomaly
- requires manual review
- contract worth checking
- possible metadata issue
- possible XML/PDF mismatch

Public disclaimer text:

> CRZ Risk & Quality Monitor does not determine whether any contract, organization, supplier, or person acted unlawfully or improperly. It highlights metadata-quality and anomaly signals that may help users decide what to check manually. The original CRZ record and source documents are authoritative. A signal can be caused by normal administrative practice, missing metadata, source-data limitations, amendments, or parsing errors. Users must verify every finding against official sources before publication or further action.

## 7. MVP Scope

Smallest useful version:

- National CRZ rolling-window metadata monitor.
- Start with recent daily exports and a limited recent backfill, such as 90-180 days.
- Full historical backfill is later.

MVP includes:

- Ingest CRZ daily differential XML or limited historical sample.
- Store raw ZIP/XML metadata and checksums.
- Parse and store core contract metadata.
- Store CRZ contract ID.
- Generate/store CRZ detail URL as `https://www.crz.gov.sk/index.php?ID={contract_id}`.
- Parse/store attachment metadata if available.
- Store direct attachment/PDF source link if filename is available.
- Normalize basic organization/supplier fields.
- Compute 5-7 explainable metadata-only flags.
- Simple organization profile.
- Simple supplier profile, with caution for natural persons.
- Searchable table of flagged contracts.
- "Open in CRZ" link.
- "Open attachment" source link where available.
- CSV export of dashboard/API results.
- README.
- Methodology page.
- Docker Compose local setup.

MVP does not include:

- Automatic download of all attachments.
- Mass PDF storage.
- OCR.
- NLP classification.
- Legal interpretation.
- ÚVO/TED integration.
- Advanced ownership graphs.
- Public user accounts.
- Personal profiles of natural persons.

MVP flagged-contract table columns:

- contract ID
- contract title
- supplier
- buyer/organization
- XML price
- publication date
- signal/flag
- severity
- reason
- CRZ detail link
- attachment/PDF source link if available
- manual review note

## 8. Future PDF/Text Extraction Scope

Selective PDF/text processing is a later phase only after the metadata-only MVP is stable.

Selection criteria:

- Contract already has metadata flags.
- Attachment exists.
- File size below configured limit.
- Contract is within a configured queue limit.
- Source access can respect CRZ rate limits.
- No natural-person-specific profiling purpose.

Pipeline:

- Queue flagged contract attachments.
- Rate-limit downloader.
- Store source URL, response status, file size, MIME type, checksum, download timestamp, and failure reason.
- Try direct text extraction first with `pypdf`, `pdfplumber`, or `pymupdf`.
- Detect scanned/image-only PDFs.
- OCR only in a later optional phase after approval.
- Extract candidate price, IČO, supplier name, dates, and subject.
- Compare candidate extracted values to XML metadata.
- Emit only "possible mismatch" signals.

Example later output:

> Possible mismatch between XML metadata and PDF text:
>
> - XML price: 0 EUR
> - PDF candidate price: 24,000 EUR incl. VAT
> - XML supplier IČO: missing
> - PDF candidate IČO: 12345678
>
> This does not imply wrongdoing. It indicates metadata may be incomplete or inconsistent and requires manual review.

Explicitly prohibited:

- Downloading all PDFs.
- Claiming extracted data is legally authoritative.
- Mass OCR.
- OCR in MVP.
- Publishing automated mismatch findings without clear manual-review language.

## 9. Full Feature Scope

"Full feature" still means a deliberately limited project, not a giant procurement platform.

Full feature may include:

- Daily production ingestion.
- Limited or complete historical backfill after feasibility testing.
- Better entity resolution.
- Cached RPO enrichment.
- RPVS enrichment with natural-person safeguards.
- Public FastAPI API.
- Streamlit dashboard or later Next.js dashboard.
- Organization watchlist.
- Email or Telegram alerts.
- Monthly public reports.
- Monitoring dashboard.
- Backup and restore.
- Data-quality test suite.
- API docs.
- Public methodology docs.
- Selective PDF/text-extraction module for flagged contracts.
- Optional OCR module for selected scanned PDFs.

Still out of scope:

- Full procurement intelligence platform.
- Full legal analysis.
- Mass attachment mirroring.
- OCR at scale.
- Ownership graph visualizations unless explicitly approved later.
- Paid enterprise API.

## 10. Data Model

### `raw_crz_exports`

Purpose:

- Track daily source ZIP downloads and checksums.

Key columns:

- `id`
- `export_date`
- `source_url`
- `downloaded_at`
- `http_status`
- `zip_sha256`
- `zip_size_bytes`
- `xml_filename`
- `xml_sha256`
- `xml_size_bytes`
- `storage_path`
- `status`
- `error_message`

Primary key:

- `id`

Indexes:

- unique `export_date`
- `status`

Expected volume:

- One row per export date.

Phase:

- MVP.

### `crz_export_files`

Purpose:

- Store parsed file-level metadata and parser version.

Key columns:

- `id`
- `raw_export_id`
- `parser_version`
- `record_count`
- `attachment_count`
- `parsed_at`
- `parse_status`
- `schema_fingerprint`

Primary key:

- `id`

Foreign keys:

- `raw_export_id` -> `raw_crz_exports.id`

Phase:

- MVP.

### `contracts`

Purpose:

- Current contract-level metadata.

Key columns:

- `crz_contract_id`
- `title`
- `subject`
- `buyer_name`
- `buyer_ico`
- `buyer_address`
- `supplier_name`
- `supplier_ico`
- `supplier_address`
- `department`
- `contract_type`
- `contract_date`
- `publication_date`
- `effective_date`
- `valid_until`
- `price_contract`
- `price_total`
- `currency`
- `status`
- `source_export_date`
- `crz_detail_url`
- `created_at`
- `updated_at`

Primary key:

- `crz_contract_id`

Indexes:

- `publication_date`
- `buyer_ico`
- `supplier_ico`
- `price_total`
- full-text/search index on title/subject/supplier/buyer if supported.

Expected volume:

- Hundreds of thousands to millions for full history; rolling MVP much smaller.

Phase:

- MVP.

### `contract_versions`

Purpose:

- Preserve repeated appearances/changes for a contract across daily exports.

Key columns:

- `id`
- `crz_contract_id`
- `export_date`
- `raw_export_id`
- `payload_hash`
- `metadata_json`
- `change_note`
- `seen_at`

Primary key:

- `id`

Foreign keys:

- `crz_contract_id` -> `contracts.crz_contract_id`
- `raw_export_id` -> `raw_crz_exports.id`

Indexes:

- `crz_contract_id`, `export_date`
- unique `crz_contract_id`, `export_date`, `payload_hash`

Phase:

- MVP, at least as minimal event history.

### `contract_attachments_metadata`

Purpose:

- Store attachment metadata and source links only.

Key columns:

- `id`
- `crz_contract_id`
- `attachment_id`
- `attachment_name`
- `scan_filename`
- `scan_size_bytes`
- `scan_source_url`
- `text_filename`
- `text_size_bytes`
- `text_source_url`
- `channel`
- `source_export_date`

Primary key:

- `id`

Foreign keys:

- `crz_contract_id` -> `contracts.crz_contract_id`

Indexes:

- `crz_contract_id`
- `attachment_id`
- `scan_filename`
- `text_filename`

Phase:

- MVP.

Notes:

- MVP stores metadata and URLs only.
- No automatic attachment downloads in MVP.

### `downloaded_attachments_later_phase`

Purpose:

- Track later selective downloads for flagged contracts.

Key columns:

- `id`
- `attachment_metadata_id`
- `source_url`
- `queued_at`
- `downloaded_at`
- `status`
- `http_status`
- `file_sha256`
- `file_size_bytes`
- `mime_type`
- `storage_path`
- `failure_reason`

Phase:

- Later PDF phase.

### `attachment_text_extraction_later_phase`

Purpose:

- Store text extraction status and metadata, not necessarily full text in public outputs.

Key columns:

- `id`
- `downloaded_attachment_id`
- `extractor`
- `extractor_version`
- `status`
- `text_length`
- `page_count`
- `is_scanned_candidate`
- `extracted_text_path`
- `failure_reason`
- `created_at`

Phase:

- Later PDF phase.

### `pdf_xml_mismatch_signals_later_phase`

Purpose:

- Store possible XML/PDF mismatch signals.

Key columns:

- `id`
- `crz_contract_id`
- `attachment_text_extraction_id`
- `field_name`
- `xml_value`
- `pdf_candidate_value`
- `confidence`
- `reason`
- `created_at`

Phase:

- Later PDF phase.

### `organizations`

Purpose:

- Normalized buyer/public organization records.

Key columns:

- `id`
- `ico`
- `normalized_name`
- `display_name`
- `address`
- `entity_type`
- `rpo_entity_id`
- `first_seen_at`
- `last_seen_at`

Phase:

- MVP.

Indexes:

- unique/partial `ico`
- normalized name.

### `suppliers`

Purpose:

- Normalized supplier records, with caution for natural persons.

Key columns:

- `id`
- `ico`
- `normalized_name`
- `display_name`
- `address`
- `entity_type`
- `is_probable_natural_person`
- `rpo_entity_id`
- `first_seen_at`
- `last_seen_at`

Phase:

- MVP.

Notes:

- Natural-person supplier pages should be minimized or hidden by default.

### `supplier_aliases`

Purpose:

- Track observed supplier-name variants.

Key columns:

- `id`
- `supplier_id`
- `raw_name`
- `raw_ico`
- `source_count`
- `first_seen_at`
- `last_seen_at`

Phase:

- MVP/later.

### `rpo_entities`

Purpose:

- Cached official RPO enrichment.

Key columns:

- `id`
- `ico`
- `official_name`
- `legal_form`
- `address`
- `status`
- `source_json`
- `fetched_at`
- `source_url`

Phase:

- Later or optional MVP enrichment.

### `rpvs_partners`

Purpose:

- Cached RPVS partner records.

Key columns:

- `id`
- `ico`
- `partner_name`
- `rpvs_id`
- `source_json`
- `fetched_at`

Phase:

- Later.

### `rpvs_beneficial_owners`

Purpose:

- Store minimal RPVS beneficial-owner references if explicitly approved.

Key columns:

- `id`
- `rpvs_partner_id`
- `owner_name_hash_or_minimized_name`
- `source_json`
- `fetched_at`

Phase:

- Later only.

Notes:

- Avoid natural-person ranking and public profiles.

### `risk_flags`

Purpose:

- Catalog of flag definitions.

Key columns:

- `id`
- `flag_code`
- `name`
- `description`
- `severity_default`
- `methodology`
- `is_active`
- `phase`

Phase:

- MVP.

### `contract_risk_flags`

Purpose:

- Contract-level flag instances.

Key columns:

- `id`
- `crz_contract_id`
- `flag_id`
- `severity`
- `reason`
- `evidence_json`
- `created_at`
- `source_run_id`

Indexes:

- `crz_contract_id`
- `flag_id`
- `severity`
- `created_at`

Phase:

- MVP.

### `organization_metrics_monthly`

Purpose:

- Aggregated organization metrics.

Key columns:

- `id`
- `organization_id`
- `month`
- `contract_count`
- `total_value`
- `flagged_contract_count`
- `top_supplier_share`

Phase:

- MVP/later.

### `supplier_metrics_monthly`

Purpose:

- Aggregated supplier metrics.

Key columns:

- `id`
- `supplier_id`
- `month`
- `contract_count`
- `total_value`
- `buyer_count`
- `growth_ratio`

Phase:

- MVP/later.

### `ingestion_runs`

Purpose:

- Operational run log.

Key columns:

- `id`
- `run_type`
- `started_at`
- `finished_at`
- `status`
- `records_seen`
- `records_inserted`
- `records_updated`
- `error_message`

Phase:

- MVP.

### `data_quality_checks`

Purpose:

- Record parser/data validation checks.

Key columns:

- `id`
- `run_id`
- `check_name`
- `status`
- `observed_value`
- `threshold`
- `details_json`

Phase:

- MVP.

## 11. Risk/Data-Quality Flags

All flags are review aids, not accusations.

### Missing Price

Explanation:

- The contract price field is empty or not parseable.

Logic:

```sql
price_total IS NULL AND price_contract IS NULL
```

Severity:

- Medium.

False-positive risk:

- Some contracts legitimately do not state a simple price.

Useful because:

- Missing price slows oversight and may indicate incomplete metadata.

Phase:

- MVP.

### Zero Price

Explanation:

- XML price is zero.

Logic:

```sql
COALESCE(price_total, price_contract) = 0
```

Severity:

- Low to medium.

False-positive risk:

- Framework agreements, non-monetary contracts, corrections, or metadata conventions.

Useful because:

- Often worth opening original CRZ/PDF record manually.

Phase:

- MVP.

### Missing Supplier

Explanation:

- Supplier name is empty.

Logic:

```sql
supplier_name IS NULL OR trim(supplier_name) = ''
```

Severity:

- Medium.

False-positive risk:

- Some records may encode supplier elsewhere or be special contract types.

Phase:

- MVP.

### Missing Supplier IČO

Explanation:

- Supplier IČO is missing.

Logic:

```sql
supplier_ico IS NULL OR trim(supplier_ico) = ''
```

Severity:

- Medium.

False-positive risk:

- Foreign suppliers, natural persons, or special cases may not have Slovak IČO.

Phase:

- MVP.

### Invalid IČO Format

Explanation:

- Supplier or buyer IČO does not match expected normalized Slovak IČO format.

Logic:

```python
normalized = digits_only(raw_ico)
invalid = normalized != "" and len(normalized) != 8
```

Severity:

- Low to medium.

False-positive risk:

- Foreign identifiers and formatting quirks.

Phase:

- MVP.

### Missing Buyer/Organization Identifier

Explanation:

- Buyer/public organization IČO is missing.

Logic:

```sql
buyer_ico IS NULL OR trim(buyer_ico) = ''
```

Severity:

- Medium.

False-positive risk:

- Legacy records or unusual public entities.

Phase:

- MVP.

### Supplier Cannot Be Matched to RPO

Explanation:

- Supplier IČO is present but cached RPO lookup does not find a matching entity.

Logic:

```sql
supplier_ico IS NOT NULL
AND NOT EXISTS (
  SELECT 1 FROM rpo_entities r WHERE r.ico = contracts.supplier_ico
)
```

Severity:

- Low.

False-positive risk:

- RPO API outage, foreign supplier, stale cache, natural person, or rate-limit failure.

Phase:

- Optional MVP/later.

### High Supplier Concentration for Organization

Explanation:

- A supplier accounts for a high share of an organization's recent contract value or count.

Logic:

```sql
supplier_value_last_12m / organization_value_last_12m >= configured_threshold
```

Severity:

- Medium.

False-positive risk:

- Small organizations may naturally use a few suppliers.

Phase:

- MVP if enough data exists; otherwise later.

### Sudden Supplier Volume Increase

Explanation:

- Supplier contract count or value rises sharply compared with prior period.

Logic:

```python
growth_ratio = value_last_30d / max(value_previous_180d_monthly_average, epsilon)
flag = growth_ratio >= threshold and value_last_30d >= minimum_value
```

Severity:

- Medium.

False-positive risk:

- Seasonal contracts, one-off projects, new suppliers, or rolling-window limitations.

Phase:

- Later MVP or full feature after enough backfill exists.

### Unusually High Number of Amendments

Explanation:

- Contract appears repeatedly or has amendment-like records more often than similar contracts.

Logic:

```sql
count(contract_versions where crz_contract_id = ?) >= threshold
```

Severity:

- Low to medium.

False-positive risk:

- CRZ export semantics must be validated before relying on this.

Phase:

- Later unless version semantics are clear.

### Possible XML/PDF Price Mismatch

Explanation:

- Later PDF text extraction finds a candidate price different from XML price.

Severity:

- Medium.

False-positive risk:

- VAT wording, multiple prices, OCR errors, amendments, or extracted wrong number.

Phase:

- Later PDF phase only.

### Attachment Unavailable

Explanation:

- Later selective downloader cannot access a linked attachment.

Severity:

- Low.

Phase:

- Later PDF phase only.

### Attachment Not Machine-Readable

Explanation:

- Direct text extraction fails and file appears scanned/image-only.

Severity:

- Low.

Phase:

- Later PDF/OCR phase only.

## 12. Data Pipeline Architecture

MVP pipeline:

1. Source discovery: determine daily export dates to ingest.
2. Download daily CRZ ZIP/XML with CRZ-compliant rate limiting.
3. Checksum/logging: store ZIP/XML hashes and run metadata.
4. Raw XML storage: store raw files outside git.
5. Parse XML using a streaming parser such as `lxml.iterparse`.
6. Validate schema shape against observed required/optional fields.
7. Extract contract metadata.
8. Extract attachment metadata and source URLs if present.
9. Generate CRZ detail link with `index.php?ID={ID}`.
10. Clean metadata: dates, prices, whitespace, IČO normalization.
11. Transform into relational tables.
12. Optionally enrich with cached RPO/RPVS data.
13. Compute metadata-only flags.
14. Update aggregates.
15. Expose dashboard/API.
16. Monitor ingestion and alert on failures.

Later selective PDF pipeline:

1. Select flagged contracts.
2. Enqueue selected attachment source URLs.
3. Rate-limited download.
4. Store file metadata/checksum.
5. Try direct text extraction.
6. Detect scanned/image PDFs.
7. Optionally OCR only selected files.
8. Extract candidate structured values.
9. Compare XML metadata vs PDF text.
10. Create possible mismatch signals.
11. Expose as later-phase flags with manual-review language.

Incremental daily load:

- Use one export date as the natural batch key.
- Make each export idempotent by checksum and `export_date`.
- Upsert current `contracts`.
- Append `contract_versions` when payload hash changes.

Historical backfill:

- Start with 90-180 days for MVP.
- Backfill older dates in controlled batches after MVP is stable.
- Respect CRZ rate limits.
- Skip or mark empty ZIPs.

Retry strategy:

- Retry transient HTTP failures with exponential backoff.
- Keep failed export rows in `raw_crz_exports`.
- Do not retry attachments in MVP because they are not downloaded.

Failure modes:

- CRZ export missing for date.
- ZIP corrupt or empty.
- XML parse failure.
- New XML fields or missing expected fields.
- RPO API 429 or outage.
- Database migration mismatch.

Source outage handling:

- Mark ingestion run failed or partial.
- Keep previous dashboard data visible.
- Show data-status warning.

Attachment unavailable handling:

- MVP stores links only.
- Later phases store download status/failure reason.

## 13. Technical Architecture

Recommended stack:

- Python 3.12+
- `httpx` for HTTP
- `lxml` for XML streaming
- `pydantic` for settings and typed parsed records
- `polars` or `pandas` for batch analysis
- PostgreSQL
- SQLAlchemy
- Alembic
- FastAPI for API
- Streamlit for MVP dashboard
- Docker Compose
- pytest
- ruff/black
- GitHub Actions for tests
- Hetzner server pulling from GitHub and autodeploying

Later PDF/text extraction options:

- `pypdf`: simple text extraction, low dependency footprint.
- `pdfplumber`: useful for layout-aware extraction.
- `pymupdf`: fast and practical, check licensing/package implications.
- Apache Tika: useful but heavier JVM dependency.
- Tesseract: later optional OCR only.

Tradeoffs:

SQLite vs PostgreSQL:

- SQLite is fastest for prototypes but weak for production concurrent dashboard/API and large history.
- PostgreSQL should be used from early MVP to avoid migration pain.

Streamlit vs Next.js:

- Streamlit is fastest for portfolio-grade MVP and internal review.
- Next.js is more polished for public product UX but costs more implementation time.
- Recommendation: Streamlit MVP, FastAPI underneath only if API is needed early; Next.js later.

Direct CRZ export vs Slovensko.Digital API:

- Direct CRZ export is official and should be primary.
- Slovensko.Digital is useful but should be optional due to timeout/dependency risk.

Raw XML vs parsed-only:

- Store raw XML to support reproducibility, parser regression tests, and reprocessing.
- Parsed-only would reduce storage but weaken auditability.

Attachment URLs vs downloading attachments:

- Store URLs in MVP.
- Downloading attachments increases cost, bandwidth, legal, and operational risk.

Direct PDF text extraction vs OCR:

- Direct extraction is cheaper and more reliable where text layer exists.
- OCR is expensive, error-prone, and should remain optional.

Full historical backfill vs rolling window:

- Rolling window proves product value quickly.
- Full history is useful later for stronger trends and supplier concentration.

## 14. Implementation Phases

### Phase 0 — Research Validation and Project Setup

Goal:

- Convert research into repo structure, documentation, and source-risk checklist.

Tasks:

- Create README with safe positioning.
- Add methodology draft.
- Add `.env.example`.
- Add Docker Compose skeleton.
- Add dependency and tooling config.

Expected files/modules:

- `README.md`
- `docs/methodology.md`
- `docs/source-notes.md`
- `pyproject.toml`
- `docker-compose.yml`
- `.env.example`

Dependencies:

- None beyond repo setup.

Tests:

- Formatting/lint config smoke test.

Definition of done:

- Repo can install dependencies and run empty test suite.

Difficulty:

- 2/10.

Estimated time:

- 0.5-1 week.

Blockers:

- None.

Go/no-go checkpoint:

- Confirm safe wording before coding user-facing UI.

### Phase 1 — CRZ XML and Link Feasibility Prototype

Goal:

- Prove that CRZ XML can be downloaded, parsed, and used to derive CRZ detail links and attachment/PDF links.

Tasks:

- Download one or several daily ZIP/XML files.
- Inspect XML schema from real export files.
- Identify contract ID field.
- Identify attachment fields.
- Generate CRZ detail URL.
- Generate attachment source URLs.
- Store sample parsed rows.
- Do not mass-download PDFs.

Expected files/modules:

- `app/ingestion/crz/download.py`
- `app/ingestion/crz/parser.py`
- `tests/fixtures/xml/`
- `tests/test_crz_parser.py`
- `notebooks/` or `scripts/inspect_crz_export.py` if useful.

Dependencies:

- CRZ export access.

Tests:

- Parser fixture tests.
- Detail-link generation tests.
- Attachment URL derivation tests.

Definition of done:

- At least two real export days parse.
- Contract IDs and attachment URLs are extracted.
- Generated CRZ links open via official redirect pattern.

Difficulty:

- 4/10.

Estimated time:

- 1 week.

Blockers:

- CRZ export format changes.
- Attachment filename rules differ for some records.

Go/no-go checkpoint:

- If attachment links cannot be derived reliably, MVP still proceeds with CRZ links but attachment-link feature is degraded.

### Phase 2 — Local Data Ingestion Prototype

Goal:

- Build idempotent local ingestion for a rolling date range.

Tasks:

- Download daily ZIPs for configured range.
- Store raw files outside git.
- Compute checksums.
- Record ingestion runs.
- Handle empty/missing exports.
- Implement retry/backoff.

Expected files/modules:

- `app/ingestion/jobs.py`
- `app/ingestion/crz/client.py`
- `app/settings.py`
- `data/raw/` ignored by git.

Dependencies:

- Phase 1 parser.

Tests:

- HTTP client tests with mocked responses.
- Idempotency tests.

Definition of done:

- Re-running ingestion does not duplicate records.

Difficulty:

- 5/10.

Estimated time:

- 1 week.

Blockers:

- CRZ rate limits and outages.

Go/no-go checkpoint:

- If daily ingestion is unreliable, build manual import first and defer automation.

### Phase 3 — Database and Core Data Model

Goal:

- Create PostgreSQL schema and migrations.

Tasks:

- Add SQLAlchemy models.
- Add Alembic migrations.
- Create core tables.
- Add indexes.
- Add repository layer or simple query functions.

Expected files/modules:

- `app/db/base.py`
- `app/db/session.py`
- `app/db/models.py`
- `alembic/`
- `tests/test_db_models.py`

Dependencies:

- Docker Compose PostgreSQL.

Tests:

- Migration test.
- Insert/upsert test.

Definition of done:

- Parsed contracts and attachment metadata load into PostgreSQL.

Difficulty:

- 5/10.

Estimated time:

- 1 week.

Blockers:

- Schema uncertainty around repeated contract versions.

Go/no-go checkpoint:

- Keep schema simple if version semantics remain unclear.

### Phase 4 — Data Cleaning and Normalization

Goal:

- Clean prices, dates, names, IČO fields, and basic entities.

Tasks:

- Normalize whitespace.
- Parse dates.
- Parse monetary values.
- Normalize IČO digits.
- Create buyer/supplier records.
- Add probable-natural-person handling.

Expected files/modules:

- `app/transforms/cleaning.py`
- `app/transforms/entities.py`
- `tests/test_cleaning.py`

Dependencies:

- Phase 3 database.

Tests:

- Unit tests for dates, prices, IČO, and names.

Definition of done:

- Cleaned records can drive dashboard filters and flags.

Difficulty:

- 5/10.

Estimated time:

- 1 week.

Blockers:

- Ambiguous CRZ role fields.

Go/no-go checkpoint:

- If supplier/buyer mapping is uncertain, label fields conservatively and document assumptions.

### Phase 5 — MVP Metadata Risk Flags

Goal:

- Implement initial explainable metadata-only signals.

Tasks:

- Create flag catalog.
- Implement missing price, zero price, missing supplier, missing supplier IČO, invalid IČO, missing buyer IČO.
- Add optional supplier concentration only if enough data exists.
- Store evidence JSON and reason text.

Expected files/modules:

- `app/flags/definitions.py`
- `app/flags/evaluate.py`
- `tests/test_flags.py`

Dependencies:

- Cleaned contracts.

Tests:

- Regression tests for each flag.

Definition of done:

- Each flag has documented logic, severity, and false-positive note.

Difficulty:

- 4/10.

Estimated time:

- 0.5-1 week.

Blockers:

- Signals may be too noisy.

Go/no-go checkpoint:

- Manually review a sample of flagged contracts before public launch.

### Phase 6 — MVP Dashboard With CRZ/PDF Links

Goal:

- Build a usable metadata-only review interface.

Must include:

- Flagged contracts table.
- Organization profile.
- Supplier profile.
- Open in CRZ link.
- Attachment/PDF source link if available.
- CSV export.
- Manual review disclaimer.

Expected files/modules:

- `app/dashboard/Home.py`
- `app/dashboard/pages/Flagged_Contracts.py`
- `app/dashboard/pages/Organization.py`
- `app/dashboard/pages/Supplier.py`
- `app/dashboard/pages/Contract_Detail.py`

Dependencies:

- Flags and database.

Tests:

- Dashboard smoke tests if practical.
- Query tests for dashboard data.

Definition of done:

- A user can search, filter, open CRZ, open source attachment link, and export CSV.

Difficulty:

- 6/10.

Estimated time:

- 1-2 weeks.

Blockers:

- Streamlit performance over larger data.

Go/no-go checkpoint:

- If Streamlit is slow, add precomputed views and pagination before considering Next.js.

### Phase 7 — Documentation and Portfolio Packaging

Goal:

- Make the project understandable and credible.

Tasks:

- README.
- Methodology.
- Limitations.
- Architecture diagram.
- Data model diagram.
- Screenshots.
- Example analysis query.

Expected files/modules:

- `README.md`
- `docs/methodology.md`
- `docs/limitations.md`
- `docs/architecture.md`
- `docs/screenshots/`

Dependencies:

- MVP dashboard.

Tests:

- Link checks if practical.

Definition of done:

- A reviewer can understand the product, pipeline, and safe terminology without a call.

Difficulty:

- 3/10.

Estimated time:

- 0.5-1 week.

Blockers:

- Unclear positioning.

Go/no-go checkpoint:

- Remove any wording that implies corruption/fraud detection.

### Phase 8 — Production Deployment

Goal:

- Deploy to Hetzner server with GitHub pull/autodeploy.

Tasks:

- Add production Docker Compose.
- Add environment variables.
- Add database volume/backups.
- Add cron/systemd timer or lightweight scheduler.
- Add deployment docs.
- Add health checks.

Expected files/modules:

- `docker-compose.prod.yml`
- `deploy/`
- `docs/deployment.md`

Dependencies:

- MVP stable locally.

Tests:

- Deployment smoke test.
- Ingestion run test on server.

Definition of done:

- Server pulls from GitHub, deploys app, runs ingestion, and exposes dashboard.

Difficulty:

- 6/10.

Estimated time:

- 1 week.

Blockers:

- Server DNS/TLS/secrets setup.

Go/no-go checkpoint:

- Do not publicize until disclaimers, data-status page, and source attribution are visible.

### Phase 9 — Full Feature Enhancements

Goal:

- Improve usefulness without expanding into a broad procurement platform.

Tasks:

- RPO enrichment cache.
- RPVS enrichment with safeguards.
- Watchlists.
- Alerts.
- FastAPI public endpoints.
- API docs.
- Monthly reports.

Expected files/modules:

- `app/enrichment/rpo.py`
- `app/enrichment/rpvs.py`
- `app/api/`
- `app/alerts/`

Dependencies:

- Stable MVP.

Tests:

- API tests.
- Enrichment cache tests.

Definition of done:

- Enhancements are optional and do not break MVP.

Difficulty:

- 7/10.

Estimated time:

- 3-6 weeks.

Blockers:

- API rate limits and privacy concerns.

Go/no-go checkpoint:

- Skip RPVS natural-person exposure unless legal/ethical treatment is solid.

### Phase 10 — Later Selective PDF/Text Extraction

Goal:

- Only after MVP is stable, add selective PDF processing for flagged contracts.

Tasks:

- Create queue.
- Add rate-limited downloader.
- Store file metadata/checksum.
- Try direct text extraction.
- Detect scanned PDFs.
- Extract candidate structured values.
- Create possible XML/PDF mismatch flags.
- Add pause/disable switch.

Expected files/modules:

- `app/attachments/download_later/`
- `app/attachments/text_extract/`
- `app/flags/pdf_mismatch.py`

Dependencies:

- Stable metadata flags and attachment metadata.

Tests:

- Tiny manually selected PDF fixture tests.
- No mass download tests.

Definition of done:

- Only selected flagged attachments are processed; failures are stored; output says "possible mismatch".

Difficulty:

- 8/10.

Estimated time:

- 3-5 weeks.

Blockers:

- PDF complexity, text extraction accuracy, CRZ limits.

Go/no-go checkpoint:

- Kill this phase if it consumes more effort than the metadata product value justifies.

### Phase 11 — Optional OCR Module

Goal:

- OCR only selected scanned/image PDFs where text extraction fails.

Tasks:

- Evaluate Tesseract.
- Measure speed and accuracy on tiny sample.
- Add strict queue limits.
- Add error/status reporting.
- Keep OCR disabled by default.

Expected files/modules:

- `app/attachments/ocr_optional/`
- `tests/fixtures/pdf_optional/`

Dependencies:

- Phase 10.

Tests:

- OCR fixture tests only if legally usable.

Definition of done:

- OCR works on a small sample and remains optional.

Difficulty:

- 8/10.

Estimated time:

- 2-4 weeks.

Blockers:

- Cost, quality, installation complexity, false positives.

Go/no-go checkpoint:

- Do not add OCR unless direct text extraction has already proven useful and user demand exists.

## 15. Repository Structure

Recommended layout:

```text
app/
  api/
  ingestion/
    crz/
  transforms/
  flags/
  db/
  dashboard/
  enrichment/
  attachments/
    metadata/
    download_later/
    text_extract/
    ocr_optional/
docs/
  methodology.md
  limitations.md
  architecture.md
tests/
  fixtures/
    xml/
    pdf_optional/
  ingestion/
  transforms/
  flags/
  api/
data/
  raw/
  sample/
alembic/
docker-compose.yml
docker-compose.prod.yml
Makefile
README.md
.env.example
pyproject.toml
```

What belongs where:

- `app/ingestion/crz/`: CRZ export client, downloader, parser, link derivation.
- `app/transforms/`: cleaning and normalization.
- `app/flags/`: metadata and later PDF mismatch flags.
- `app/db/`: SQLAlchemy models, session, migrations integration.
- `app/dashboard/`: Streamlit pages.
- `app/api/`: FastAPI endpoints.
- `app/enrichment/`: RPO/RPVS/Slovensko.Digital integrations.
- `app/attachments/metadata/`: attachment metadata parsing and URL generation.
- `app/attachments/download_later/`: later selective downloader.
- `docs/`: methodology, limitations, architecture, source notes.
- `tests/fixtures/xml/`: small XML fixtures.
- `tests/fixtures/pdf_optional/`: tiny manually selected PDF fixtures only.
- `data/raw/`: ignored raw CRZ files.
- `data/sample/`: small safe samples only.

Rules:

- No large PDF corpus in git.
- No automatic PDF download in MVP.
- Raw CRZ exports should be ignored by git unless tiny sanitized fixtures.

## 16. API Design

MVP can use Streamlit directly. FastAPI becomes useful for public/API separation and later dashboard clients.

### `GET /health`

Purpose:

- Service health check.

Response shape:

```json
{"status": "ok", "version": "0.1.0"}
```

Phase:

- MVP.

### `GET /data-status`

Purpose:

- Show latest ingestion status.

Response:

- latest export date
- latest successful run
- failed runs
- record counts

Phase:

- MVP.

### `GET /contracts`

Purpose:

- Search/filter contracts.

Query params:

- `q`
- `buyer_ico`
- `supplier_ico`
- `date_from`
- `date_to`
- `flag`
- `severity`
- `limit`
- `offset`

Response:

- contract summary rows with CRZ link and top flags.

Phase:

- MVP/later API.

### `GET /contracts/{id}`

Purpose:

- Contract detail.

Response:

- metadata
- flags
- CRZ detail URL
- attachment metadata links
- disclaimer

Phase:

- MVP/later API.

### `GET /contracts/{id}/attachments`

Purpose:

- Attachment metadata.

MVP response:

- source URLs only.

Later response:

- extraction status and possible mismatch signals.

Phase:

- MVP/later.

### `GET /organizations`

Purpose:

- Search organizations.

Phase:

- MVP.

### `GET /organizations/{id}`

Purpose:

- Organization profile.

Response:

- metrics
- recent contracts
- flags summary

Phase:

- MVP.

### `GET /organizations/{id}/flags`

Purpose:

- Organization-specific flag list.

Phase:

- MVP/later.

### `GET /suppliers/{ico}`

Purpose:

- Supplier profile by IČO.

Privacy note:

- Suppress or minimize profiles for probable natural persons.

Phase:

- MVP/later.

### `GET /flags`

Purpose:

- Flag catalog and methodology.

Phase:

- MVP.

### `GET /exports/contracts.csv`

Purpose:

- Export filtered contract rows.

Phase:

- MVP.

Attachment API rule:

- Do not serve copied PDFs unless legally and technically justified.
- MVP returns source metadata and CRZ URLs only.

## 17. Dashboard Design

### Home / Search

User goal:

- Find contracts, organizations, or suppliers quickly.

Components:

- Search box.
- Date filter.
- Flag filter.
- Latest data status.
- Clear disclaimer.

Phase:

- MVP.

### Flagged Contracts

User goal:

- Review contracts worth checking.

Components:

- Table with contract ID, title, buyer, supplier, price, date, flags, severity, reason, CRZ link, attachment link.
- Filters.
- CSV export.

Phase:

- MVP.

### Contract Detail

User goal:

- Understand why a contract was flagged and open the source.

Components:

- CRZ metadata.
- Flags.
- Explanation of flags.
- Open in CRZ link.
- Attachment/PDF source links if available.
- Disclaimer:

> Original CRZ record is authoritative. This tool only highlights metadata signals.

Phase:

- MVP.

### Organization Profile

User goal:

- Review one buyer/public organization.

Components:

- Recent contracts.
- Flag counts.
- Supplier concentration summary.
- Trend metrics after enough data.

Phase:

- MVP.

### Supplier Profile

User goal:

- Review supplier metadata and recent public contracts.

Components:

- Supplier name/IČO.
- Recent contracts.
- Buyers.
- Flags involving supplier records.

Privacy rule:

- Minimize or suppress probable natural-person supplier profiles.

Phase:

- MVP with caution.

### Latest Changes

User goal:

- See newest ingested contracts.

Phase:

- MVP/later.

### Methodology

User goal:

- Understand signal logic and limitations.

Phase:

- MVP.

### Data Status

User goal:

- Check whether data is current.

Components:

- Last successful ingestion.
- Failed dates.
- Source warnings.
- Parser version.

Phase:

- MVP.

## 18. Monitoring and Operations

Update frequency:

- Daily, after CRZ daily export is expected to be available.

Logging:

- Structured logs for download, parse, transform, flag, and dashboard/API errors.

Ingestion run table:

- Required from MVP.

Failed run handling:

- Store status and error.
- Keep previous successful data visible.
- Show warning on data-status page.

Alerting:

- MVP: email or server log alert.
- Later: Telegram/email for ingestion failures.

Backups:

- Daily PostgreSQL dump.
- Retain at least 7 daily and 4 weekly backups.
- Raw XML can be redownloaded, but local raw cache improves reproducibility.

Database migrations:

- Alembic.
- Migration tested before deployment.

Data refresh:

- Daily incremental load.
- Rolling backfill job separate from daily job.

Source outage handling:

- Do not fail dashboard completely.
- Mark data stale.

Rate-limit compliance:

- Central HTTP client with CRZ throttle.
- Separate limits for CRZ, RPO, Slovensko.Digital, and RPVS.

Security basics:

- No secrets in git.
- Read-only public API where possible.
- Environment variables for DB credentials.
- Server firewall and HTTPS.

GDPR/privacy:

- Avoid natural-person profiles.
- Avoid ranking persons.
- Minimize RPVS beneficial-owner display.
- Attribute official sources.

Attachment/PDF operations:

- MVP should not download them automatically.
- Later downloader must have strict queue limits.
- Later downloader must obey CRZ rate limits.
- Later downloader must store status and failures.
- Later downloader must support pause/disable switch.

## 19. Legal, Ethical, and Communication Risks

Personal data risk:

- CRZ/RPVS may include natural persons.
- Do not build natural-person profiles.
- Consider hiding probable natural-person supplier pages by default.
- Show only contract-level source links where necessary.

Defamatory interpretation risk:

- A flag can be misread as wrongdoing.
- UI must repeat that signals require manual review.
- Avoid red/accusatory visual language.

Public-sector data caveats:

- Source metadata can be incomplete, delayed, corrected, or inconsistent.
- Missing or zero price does not imply wrongdoing.
- Missing IČO does not imply wrongdoing.

Source attribution:

- Attribute CRZ, Statistical Office RPO, Ministry of Justice RPVS, and any Slovensko.Digital data if used.

Licensing:

- CRZ official terms/rate limits must be followed.
- RPO API indicates CC BY 4.0 in live response.
- Slovensko.Digital terms require attribution and include no-warranty language.

What not to publish:

- Accusatory rankings.
- Natural-person leaderboards.
- "Most suspicious" lists.
- Claims of illegality.
- OCR-derived claims as authoritative.

False-positive handling:

- Every flag page must include explanation and common false positives.
- Add "manual review note" field to exported rows.

## 20. Testing Strategy

MVP tests:

- Unit tests for URL generation.
- Unit tests for IČO normalization.
- Unit tests for price parsing.
- Unit tests for date parsing.
- XML parser tests with sample fixtures.
- Attachment metadata extraction tests.
- Contract link generation tests.
- Database migration tests.
- Ingestion idempotency tests.
- Flag logic regression tests.
- API tests if FastAPI is included.
- Dashboard smoke tests if practical.
- Data validation checks for required fields and count anomalies.

Sample XML fixtures:

- Include tiny real or minimized XML snippets.
- Do not include large export files in git.

Later PDF tests:

- Tiny text-PDF fixture.
- Tiny scanned-PDF fixture only if legally usable.
- Text extraction tests.
- PDF metadata tests.
- XML/PDF mismatch detection tests.
- OCR tests only if OCR module is approved.

Regression tests:

- Any observed CRZ schema variation gets a fixture.
- Every flag bug gets a regression test.

## 21. Portfolio Presentation Plan

README sections:

- Problem.
- What the tool does.
- What the tool does not do.
- Data sources.
- Methodology.
- Architecture.
- Local setup.
- Screenshots.
- Known limitations.
- Roadmap.

Professional artifacts:

- Architecture diagram.
- Data model diagram.
- Pipeline diagram.
- Methodology page.
- Dashboard screenshots.
- Short demo video.
- Example SQL queries.
- Example analysis notebook.
- API docs.
- Known limitations.
- Future roadmap.

Portfolio message:

- Metadata-only MVP was a deliberate product and risk decision.
- PDF/OCR was deliberately postponed.
- The tool reduces manual review time.
- The methodology is transparent and reproducible.
- The product is careful about legal and ethical risk.

## 22. Cost and Hosting Estimate

Local development:

- Cost: 0 EUR beyond developer time.
- Storage: manageable for rolling XML window.

Hetzner VPS:

- Small VPS likely enough for MVP.
- Expected cost: roughly 5-15 EUR/month depending on instance and backups.

Database:

- PostgreSQL on same VPS for MVP.
- Managed DB later only if needed.

Bandwidth/storage:

- XML daily downloads are modest.
- Raw XML rolling cache is cheap.
- Not downloading PDFs keeps bandwidth/storage low.

Monitoring:

- Basic logs and cron/systemd status: free.
- Optional uptime monitor: free/low cost.

Cost impact of no PDF downloads in MVP:

- Major reduction in bandwidth, storage, backup, and legal review burden.

Selective PDF processing later:

- Costs grow with queue size and file sizes.
- Must cap downloads/day and max file size.

Mass PDF/OCR:

- Expensive and risky due to storage, bandwidth, OCR CPU, error rates, and maintenance.
- Should remain out of scope.

## 23. Biggest Blockers and Mitigations

### CRZ Schema Changes

Likelihood:

- Medium.

Impact:

- High.

Mitigation:

- Parser tests, schema fingerprinting, data-quality checks, and alerting.

Go/no-go threshold:

- Pause public updates if parser confidence is low.

### Source Rate Limits

Likelihood:

- High.

Impact:

- Medium.

Mitigation:

- Central throttled HTTP client and backoff.

Go/no-go threshold:

- Stop any job that risks violating official limits.

### Missing Fields

Likelihood:

- High.

Impact:

- Medium.

Mitigation:

- Treat as metadata signals only where meaningful; document false positives.

### Attachment Links Not Stable

Likelihood:

- Medium.

Impact:

- Medium.

Mitigation:

- Store CRZ detail link as fallback; periodically validate a sample.

Go/no-go threshold:

- If direct attachment links are unreliable, show only CRZ detail links in MVP.

### Attachment Metadata Not Always Present

Likelihood:

- High.

Impact:

- Low to medium.

Mitigation:

- Support contracts without attachments.

### Bad IČO Matching

Likelihood:

- Medium.

Impact:

- Medium.

Mitigation:

- Normalize carefully, cache RPO, show match confidence, avoid hard claims.

### Slovensko.Digital Dependency Risk

Likelihood:

- Medium.

Impact:

- Low if optional; high if hard dependency.

Mitigation:

- Do not make it hard MVP dependency.

### RPVS API Changes

Likelihood:

- Medium.

Impact:

- Medium.

Mitigation:

- Later-only integration with tests and source abstraction.

### Legal Wording Risk

Likelihood:

- High.

Impact:

- High.

Mitigation:

- Strict terminology, disclaimers, methodology, and manual-review framing.

Go/no-go threshold:

- Do not launch public dashboard if wording implies wrongdoing.

### Personal-Data Exposure

Likelihood:

- Medium.

Impact:

- High.

Mitigation:

- Hide/minimize natural-person profiles; avoid rankings and enrichment display.

### Low User Adoption

Likelihood:

- Medium.

Impact:

- Medium.

Mitigation:

- Keep portfolio value high; target journalists/watchdogs with concrete examples.

### Too Much Scope

Likelihood:

- High.

Impact:

- High.

Mitigation:

- Metadata MVP first; PDF later; OCR last.

### Historical Backfill Volume

Likelihood:

- Medium.

Impact:

- Medium.

Mitigation:

- Start with rolling window.

### PDF Complexity

Likelihood:

- High.

Impact:

- High.

Mitigation:

- Later selective processing only.

### OCR Complexity

Likelihood:

- High.

Impact:

- High.

Mitigation:

- Keep optional; disable by default.

### False-Positive Interpretation

Likelihood:

- High.

Impact:

- High.

Mitigation:

- Explanations, false-positive notes, manual-review labels, careful exports.

## 24. Final Recommended Roadmap

Week 1:

- Set up repo, docs, tooling, Docker Compose, PostgreSQL.
- Implement CRZ XML/link feasibility prototype.
- Prove CRZ detail and attachment URL derivation.

Week 2:

- Build local ingestion for daily exports and rolling date range.
- Store raw XML metadata and parsed rows.
- Add parser tests.

Week 3:

- Add database model, migrations, cleaning, normalization.
- Implement initial flags.

Week 4:

- Build Streamlit dashboard with flagged contracts, contract detail, organization profile, supplier profile, CRZ links, attachment source links, and CSV export.

Weeks 5-8:

- Polish dashboard.
- Add data-status page.
- Add docs, methodology, limitations, screenshots.
- Deploy to Hetzner via GitHub pull/autodeploy.
- Add monitoring and backups.
- Add optional cached RPO enrichment if time allows.

Later:

- Add FastAPI endpoints.
- Add watchlists and alerts.
- Add monthly reports.
- Add RPO/RPVS enrichment with safeguards.
- Consider selective PDF text extraction only after metadata product proves useful.
- OCR is last and optional.

Roadmap principle:

- First prove CRZ XML + CRZ/PDF links.
- Then build metadata-only MVP.
- Then add dashboard/API.
- Then add RPO/RPVS.
- Only then consider selective PDF text extraction.
- OCR is last and optional.

## 25. Open Questions

Decisions still needed before implementation:

- UI language: Slovak only, or Slovak UI with English README/portfolio summary?
- Exact rolling-window size for MVP: 90, 180, or 365 days?
- Should supplier profiles for probable natural persons be hidden entirely or shown only as contract-level source records?
- Should MVP include FastAPI immediately, or only Streamlit with direct database queries?
- Should RPO enrichment be included in MVP or deferred until after dashboard works?
- What public domain/subdomain will be used on Hetzner?
- What backup retention policy is acceptable for the VPS?
- Should CSV exports include all visible rows or require an explicit disclaimer acceptance?
- Should the dashboard show low-severity flags by default or only medium/high?
- Should historical backfill be attempted before public launch or after launch?

Recommended default answers:

- Slovak public UI plus English README summary.
- 180-day rolling window.
- Hide natural-person supplier profiles; show only contract-level source links.
- Streamlit first; FastAPI after MVP dashboard unless API is part of portfolio goal.
- Defer RPO enrichment until core CRZ ingestion/dashboard is stable.
- Require visible disclaimer on CSV export page.
- Show all severities but let users filter.
