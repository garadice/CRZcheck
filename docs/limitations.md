# Known Limitations

> CRZ Risk & Quality Monitor — honest accounting of what this project does **not** do, and where its outputs should be interpreted with caution.

This document is written for reviewers, hiring managers, and anyone evaluating the project's analytical claims. Understanding boundaries is as important as understanding capabilities.

---

## 1. Scope Limitations

### Metadata-only analysis

All risk flags are computed from **XML metadata fields** — the structured data CRZ publishes alongside each contract. The system does **not** download, parse, or OCR contract PDFs. A contract whose PDF contains suspicious pricing, scope changes, or irregular terms will pass every flag if its metadata is clean.

In other words: this tool catches *lazy* bad reporting, not *clever* bad reporting.

### No semantic or NLP analysis

There is no natural-language processing of contract subjects, descriptions, or supplementary text. The system cannot determine whether a contract's stated subject matches its actual purpose, detect vague or overly broad descriptions, or classify contracts by risk category based on text content.

### No cross-referencing with external data

The system operates entirely within CRZ data. There is no connection to:

- **Obchodný register** (Slovak Commercial Register) — cannot verify whether a supplier is an active legal entity
- **ÚVO** (Office for Public Procurement) — cannot cross-check procurement procedure compliance
- **Beneficial ownership registers** — cannot detect conflicts of interest or related-party transactions
- **Financial databases** — cannot assess supplier financial health or market concentration

Flags are computed in isolation, without enrichment from any external source.

---

## 2. Data Quality Limitations

### CRZ data is self-reported

Slovak public institutions self-report contracts to CRZ. CRZ itself does **not** validate metadata completeness or accuracy. Missing fields, typos, and inconsistent formatting in the source data directly propagate into this system's analysis. A high flag count for an institution may reflect poor reporting hygiene rather than actual procurement risk.

### No entity resolution beyond IČO

Organizations and suppliers are matched exclusively by **IČO** ( Slovak company ID). Entities that:

- are reported without an IČO,
- have IČO typos or transpositions,
- use variant name spellings,

will appear as **separate entries** rather than being deduplicated. There is no fuzzy name matching, no organizational hierarchy resolution, and no parent-subsidiary linking.

### Natural person detection is heuristic

The system identifies natural persons (fyzické osoby) using a heuristic: a supplier is classified as a natural person if it has **no IČO** and **no legal form suffix**. The suffix list covers 12 common Slovak forms:

| Suffix | Legal Form |
|--------|-----------|
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

This heuristic produces both false positives (entities that happen to lack a suffix but are legal persons) and false negatives (natural persons who include titles or qualifiers that look like legal forms).

---

## 3. Technical Limitations

### 90-day rolling window

By default, the system maintains a **90-day rolling window** of contract data. Contracts older than the window are purged from the active dataset. This means:

- Historical trend analysis is limited to the window depth
- Seasonal patterns (e.g., end-of-year contract spikes) are only visible if the window captures them
- Year-over-year comparisons are not available

The window is configurable, but extending it increases storage and processing requirements linearly.

### No real-time data

Data is ingested **once daily** via scheduled download of CRZ's daily XML exports. There is no webhook, streaming, or polling mechanism. The lag between CRZ publication and dashboard update is typically **up to 24 hours**. Newly published contracts are not visible until the next ingestion cycle completes.

### Rate-limited downloads

Downloads from CRZ use a **day/night rate split** — 2.0-second intervals during daytime (06:00–22:00) and 0.4-second intervals at night (22:00–06:00) — to stay below CRZ's approximately 3 requests/second rate limit. This means a full 90-day backfill (downloading ~90 daily ZIP archives, each requiring an HTTP request) takes **several hours** to complete. This is by design — the project prioritizes being a respectful API consumer over ingestion speed.

### Slovak language dependency

The dashboard UI, flag names, and legal form detection are implemented in **Slovak**. This is appropriate for the target domain (Slovak public procurement) but creates friction for non-Slovak-speaking reviewers. Specifically:

- Flag labels use Slovak legal terminology
- Company suffix detection relies on Slovak legal form abbreviations
- Dashboard navigation and filter labels are in Slovak

---

## 4. Analytical Limitations

### Flags are boolean, not statistically normalized

Each risk flag is a simple **boolean** (present / absent). There is no statistical baseline comparing a contract's flag profile against its peer group. This creates an important gap:

| Scenario | Flag behavior | Interpretation |
|----------|-------------|----------------|
| Contract missing price in a category where 90% also miss price | Flagged | Low signal — this is the norm, not an outlier |
| Contract missing price in a category where 5% miss price | Flagged | High signal — genuine anomaly |

Both contracts receive the **same flag** despite vastly different analytical significance. The system does not distinguish between them.

### Individual flags are noisy

Based on analysis of CRZ data, individual flags have high base rates:

- **~34.5%** of contracts have **missing price information** (both price fields are NULL)
- **~23%** are missing supplier IČO

This means any single flag is a **weak signal**. A contract flagged for zero price alone is statistically unremarkable. Compound severity — contracts with **3 or more concurrent flags** — is considerably more informative and should be the primary analytical lens.

### No temporal anomaly detection

The system does not detect temporal anomalies such as:

- Sudden spikes in flag rates for a specific institution
- Unusual patterns in contract timing (e.g., many contracts published on the same day)
- Gradual deterioration of reporting quality over time

---

## 5. Mitigation Strategies

These limitations are acknowledged, not ignored. The project applies the following mitigations:

| Limitation | Mitigation |
|-----------|-----------|
| Boolean flags are noisy | **Compound severity scoring** — contracts with 3+ concurrent flags are surfaced as high-priority. This is the primary signal, not individual flags. |
| No external cross-referencing | Flagged contracts are presented with **full metadata context** so analysts can manually cross-reference. Export functionality supports follow-up investigation in external tools. |
| Self-reported data quality | Flags are framed as **data quality indicators**, not fraud accusations. Dashboard language reflects this distinction. |
| No statistical baselines | Flag rates are displayed **per-institution** and **per-category**, giving reviewers implicit peer comparison even without formal normalization. |
| Heuristic person detection | The heuristic is documented (see above) with its failure modes. Detected natural persons are flagged for **manual review**, not treated as conclusions. |
| 90-day window | The window is **configurable** via environment variable. Users who need deeper history can extend it at the cost of storage. |
| Slovak-only UI | This is a feature, not a bug, for the target audience. English documentation (like this file) bridges the gap for international reviewers. |

---

## 6. Future Roadmap

Items that could address current limitations, roughly ordered by impact-to-effort ratio:

1. **Statistical normalization** — Compute flag rates per CPV category and institution, surface Z-scores instead of booleans. High analytical value, moderate effort.

2. **External register integration** — Connect to Obchodný register API to verify supplier existence and status. High value for entity resolution, moderate effort.

3. **PDF text extraction** — Download and OCR contract PDFs for full-text analysis. High value but significant infrastructure cost (storage, processing, legal considerations).

4. **Fuzzy entity matching** — Implement name similarity scoring for supplier deduplication. Moderate value, moderate effort (e.g., using `rapidfuzz` or similar).

5. **Historical trend tracking** — Persist daily aggregate statistics beyond the rolling window, enabling long-term trend visualization even when raw contracts are purged. Low effort, moderate value.

6. **Temporal anomaly detection** — Flag institutions whose flag rates deviate significantly from their own historical baseline. Moderate effort, high analytical value.

7. **NLP contract classification** — Classify contract subjects by risk category using Slovak-language NLP. High effort, uncertain payoff given the metadata-focused architecture.

8. **i18n / English dashboard** — Add language toggle for international reviewers. Low analytical value but high portfolio value. Low effort with Streamlit's built-in support.

---

## Summary

This tool is a **metadata quality radar**, not an audit system. It identifies contracts with incomplete or suspicious metadata fields — a necessary but insufficient condition for detecting procurement irregularities. Its value lies in surfacing data quality issues at scale, not in drawing conclusions about individual contracts.

The honest interpretation of a flagged contract is: *"this contract's metadata is incomplete or anomalous — it warrants closer inspection."* The dishonest interpretation is: *"this contract is fraudulent."* This tool supports the former.
