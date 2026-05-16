# Metodológia príznakov kvality — CRZ Risk & Quality Monitor

> **Verzia:** MVP (fáza 1)
> **Posledná aktualizácia:** 2026-05

Tento dokument popisuje príznakový systém (flag system) používaný v projekte **CRZ Risk & Quality Monitor** na hodnotenie kvality metadát verejných zmlúv z Centrálneho registra zmlúv (CRZ). Každý príznak (flag) je automaticky vypočítaný na základe štrukturálnych metadát — **bez analýzy PDF dokumentov, OCR ani spracovania prirodzeného jazyka**.

Príznaky signalizujú **kvalitu údajov**, nie podozrenie z podvodu. Chýbajúce alebo nezvyčajné hodnoty môžu mať legitímne dôvody, ktoré sú pre každý príznak uvedené nižšie.

---

## Prehľad príznakov

| # | Kód | Názov | Závažnosť | Krátky popis |
|---|-----|-------|-----------|-------------|
| 1 | `MISSING_PRICE` | Chýba cena | medium | Žiadna informácia o cene |
| 2 | `ZERO_PRICE` | Nulová cena | low | Uvedená cena je 0 |
| 3 | `MISSING_SUPPLIER` | Chýba dodávateľ | medium | Názov dodávateľa chýba |
| 4 | `MISSING_SUPPLIER_ICO` | Chýba IČO dodávateľa | medium | IČO dodávateľa chýba |
| 5 | `INVALID_ICO_FORMAT` | Neplatný formát IČO | low | IČO nie je 8-miestne |
| 6 | `MISSING_BUYER_ICO` | Chýba IČO obstarávateľa | medium | IČO obstarávateľa chýba |

---

## Detailný opis príznakov

### 1. `MISSING_PRICE` — Chýba cena

| Atribút | Hodnota |
|---------|---------|
| **Kód** | `MISSING_PRICE` |
| **Závažnosť** | medium |
| **Podmienka aktivácie** | `price_total` aj `price_contract` sú `NULL` |
| **Približná frekvencia** | ~34,5 % zmlúv |

**Popis:**
Zmluva neobsahuje žiadnu informáciu o cene — ani celkovú (`price_total`), ani zmluvnú (`price_contract`). Ide o najčastejší príznak v celom registri.

**Legitímne prípady:**
- Rámcové dohody, kde konečná cena nie je v čase zverejnenia známa
- Bezodplatné prevody (darovacie zmluvy, prevody majetku)
- Zmluvy s nepeňažným plnením

---

### 2. `ZERO_PRICE` — Nulová cena

| Atribút | Hodnota |
|---------|---------|
| **Kód** | `ZERO_PRICE` |
| **Závažnosť** | low |
| **Podmienka aktivácie** | `COALESCE(price_total, price_contract) = 0` |

**Popis:**
Zmluva má uvedenú cenu, ale jej hodnota je nulová. Nižšia závažnosť odráža fakt, že ide o explicitne zadanú hodnotu (nie o chýbajúci údaj).

**Legitímne prípady:**
- Rámcové dohody s nulovou počiatočnou hodnotou
- Bezodplatné prevody
- Opravy a údržba bez nákladov na zadávateľa
- Metadatové konvencie CRZ (nulová cena ako placeholder)

---

### 3. `MISSING_SUPPLIER` — Chýba dodávateľ

| Atribút | Hodnota |
|---------|---------|
| **Kód** | `MISSING_SUPPLIER` |
| **Závažnosť** | medium |
| **Podmienka aktivácie** | `supplier_name` je `NULL`, prázdny reťazec alebo len medzery |

**Popis:**
Zmluva neobsahuje názov dodávateľa. Bez tohto údaju nie je možné zmluvu priradiť ku konkrétnemu subjektu, čo sťažuje analýzu trhu a overenie transparentnosti.

**Legitímne prípady:**
- Dodávateľ je uvedený v prílohe, nie v metadátach
- Špeciálne typy zmlúv (napr. zmluvy o posielení budúcej zmluvy)

---

### 4. `MISSING_SUPPLIER_ICO` — Chýba IČO dodávateľa

| Atribút | Hodnota |
|---------|---------|
| **Kód** | `MISSING_SUPPLIER_ICO` |
| **Závažnosť** | medium |
| **Podmienka aktivácie** | `supplier_ico` je `NULL`, prázdny reťazec alebo len medzery |
| **Približná frekvencia** | ~23 % zmlúv |

**Popis:**
Zmluva neobsahuje identifikačné číslo organizácie (IČO) dodávateľa. Chýbajúce IČO znemožňuje automatické prepojenie s Registrom právnických osôb a agregáciu zmlúv pod jedného dodávateľa.

**Legitímne prípady:**
- Zahraniční dodávatelia bez slovenského IČO
- Fyzické osoby (živnostníci, OSČD), ktoré nie sú v RPO
- Špeciálne prípady (diplomatické misie, medzinárodné organizácie)

---

### 5. `INVALID_ICO_FORMAT` — Neplatný formát IČO

| Atribút | Hodnota |
|---------|---------|
| **Kód** | `INVALID_ICO_FORMAT` |
| **Závažnosť** | low |
| **Podmienka aktivácie** | IČO je prítomné, ale po normalizácii (odstránenie nečíslic) neobsahuje presne 8 číslic |

**Popis:**
Identifikačné číslo je vyplnené, ale nespĺňa očakávaný formát slovenského IČO (8 číslic po normalizácii). Kontroluje sa `supplier_ico` aj `buyer_ico`. Príznak sa aktivuje, ak aspoň jedno z nich má neplatný formát.

**Legitímne prípady:**
- Zahraničné identifikátory (napr. české IČO môže mať 8 číslic, ale iné krajiny používajú odlišné formáty)
- Chyby vo formátovaní (medzery, pomlčky, predpony)
- Staršie záznamy s nekonzistentným zápisom

---

### 6. `MISSING_BUYER_ICO` — Chýba IČO obstarávateľa

| Atribút | Hodnota |
|---------|---------|
| **Kód** | `MISSING_BUYER_ICO` |
| **Závažnosť** | medium |
| **Podmienka aktivácie** | `buyer_ico` je `NULL`, prázdny reťazec alebo len medzery |
| **Približná frekvencia** | ~17,5 % zmlúv |

**Popis:**
Zmluva neobsahuje IČO obstarávateľa (verejného subjektu, ktorý zmluvu uzavrel). Chýbajúce IČO obstarávateľa sťažuje filtrovanie a agregáciu zmlúv podľa inštitúcií.

**Legitímne prípady:**
- Staršie záznamy pred zavedením povinného IČO obstarávateľa
- Nezvyčajné verejné subjekty bez štandardného IČO

---

## Zložená závažnosť (Compound Severity)

Každá zmluva môže mať aktivovaných viacero príznakov súčasne. Zložená závažnosť sa vypočíta podľa nasledujúcich pravidiel:

| Podmienka | Výsledná závažnosť |
|-----------|-------------------|
| 3 alebo viac príznakov | **high** |
| 1–2 príznaky | maximum z individuálnych závažností |
| 0 príznakov | **none** |

**Hierarchia závažností:** `low` < `medium` < `high`

Pravidlo 3+ príznakov odráža skutočnosť, že kumulatívny nedostatok metadát zvyšuje riziko nemožnosti overiť zmluvu — aj keď jednotlivé príznaky sú menej závažné.

### Príklady

| Aktivované príznaky | Individuálne závažnosti | Výsledok |
|---------------------|------------------------|----------|
| `ZERO_PRICE` | low | **low** |
| `MISSING_PRICE` | medium | **medium** |
| `ZERO_PRICE`, `MISSING_SUPPLIER_ICO` | low, medium | **medium** |
| `MISSING_PRICE`, `MISSING_SUPPLIER`, `MISSING_BUYER_ICO` | medium, medium, medium | **high** |
| `ZERO_PRICE`, `INVALID_ICO_FORMAT`, `MISSING_SUPPLIER_ICO`, `MISSING_BUYER_ICO` | low, low, medium, medium | **high** |

---

## Cyklus prehodnotenia (Re-flagging Lifecycle)

Príznaky nie sú statické — prepočítavajú sa pri každom spustení procesu:

1. **Každé spustenie má identifikátor** (`source_run_id`), ktorý sa viaže na konkrétny beh ingestcie (`ingestion_runs`).
2. **Počas iterácie** sa vymažú staré príznaky z predchádzajúcich behov pre každú zmluvu (`source_run_id != aktuálny run_id`), s konečným upratovacím prechodom pre prípadné zostávajúce zastarané príznaky.
3. **Vyhodnotenie** — pre každú zmluvu sa spustia všetky aktívne kontroléry v poradí definovanom v `FLAG_CHECKERS`.
4. **Uloženie** — nové príznaky sa zapíšu s aktuálnym `source_run_id`, závažnosťou, dôvodom a evidenciou (JSON).

Tento prístup zaručuje, že **príznaky vždy odrážajú aktuálny stav zmluvy** a nie sú ovplyvnené historickými artefaktmi z predchádzajúcich spustení.

```
┌──────────────┐    ┌──────────────────────┐    ┌──────────────────┐
│ Ingestcia    │───▶│ Zmazanie starých     │───▶│ Vyhodnotenie     │
│ (run_id = N) │    │ príznakov (run_id≠N) │    │ nových príznakov │
└──────────────┘    └──────────────────────┘    └──────────────────┘
                                                          │
                                                          ▼
                                                ┌──────────────────┐
                                                │ Uloženie s       │
                                                │ source_run_id = N│
                                                └──────────────────┘
```

---

## Technická implementácia

Príznaky sú implementované v nasledujúcich moduloch:

| Súbor | Účel |
|-------|------|
| `app/flags/definitions.py` | Definície príznakov (kód, názov, popis, závažnosť, metodika) |
| `app/flags/evaluate.py` | Vyhodnocovací engine — kontroléry a zložená závažnosť |
| `app/flags/flags_catalog.py` | Seedovanie definícií do databázy |

Každý kontrolér prijíma objekt `Contract` a vracia `FlagMatch` alebo `None`. Výsledok obsahuje kód príznaku, závažnosť, dôvod a evidenciu (slovník s konkrétnymi hodnotami, ktoré príznak spustili).

---

## Obmedzenia MVP fázy

- Všetky príznaky pracujú **výhradne s metadátami** — neanalyzujú obsah PDF príloh.
- Nevyužíva sa OCR, NLP ani strojové učenie.
- Príznaky neberú do úvahy historické zmeny zmlúv (verzie).
- Príznaky sú binárne (aktivovaný/neaktivovaný) — nepoužívajú vážené skóre.

---

> **Upozornenie:** Tieto príznaky signalizujú kvalitu metadát, nie podozrenie z podvodu. Ich účelom je pomôcť identifikovať zmluvy s neúplnými údajmi pre ďalšiu manuálnu kontrolu alebo pre zlepšenie kvality dát v registri.

---

# Flag Methodology — CRZ Risk & Quality Monitor

> **Version:** MVP (phase 1)
> **Last updated:** 2026-05

This document describes the flag system used by the **CRZ Risk & Quality Monitor** project to assess metadata quality of public contracts from the Central Register of Contracts (CRZ, Slovakia). Each flag is computed automatically from structural metadata — **no PDF analysis, OCR, or NLP is involved**.

Flags signal **data quality**, not fraud. Missing or unusual values may have legitimate reasons, documented below for each flag.

---

## Flag Overview

| # | Code | Name | Severity | Brief Description |
|---|------|------|----------|-------------------|
| 1 | `MISSING_PRICE` | Missing Price | medium | No price information at all |
| 2 | `ZERO_PRICE` | Zero Price | low | Stated price is 0 |
| 3 | `MISSING_SUPPLIER` | Missing Supplier | medium | Supplier name is absent |
| 4 | `MISSING_SUPPLIER_ICO` | Missing Supplier IČO | medium | Supplier IČO is absent |
| 5 | `INVALID_ICO_FORMAT` | Invalid IČO Format | low | IČO is not 8 digits |
| 6 | `MISSING_BUYER_ICO` | Missing Buyer IČO | medium | Buyer IČO is absent |

---

## Detailed Flag Descriptions

### 1. `MISSING_PRICE` — Missing Price

| Attribute | Value |
|-----------|-------|
| **Code** | `MISSING_PRICE` |
| **Severity** | medium |
| **Trigger condition** | Both `price_total` and `price_contract` are `NULL` |
| **Approximate frequency** | ~34.5% of contracts |

**Description:**
The contract contains no price information — neither total price (`price_total`) nor contract price (`price_contract`). This is the most frequently triggered flag in the entire register.

**Legitimate cases:**
- Framework agreements where the final price is unknown at publication time
- Gratuitous transfers (donation agreements, property transfers)
- Contracts with non-monetary consideration

---

### 2. `ZERO_PRICE` — Zero Price

| Attribute | Value |
|-----------|-------|
| **Code** | `ZERO_PRICE` |
| **Severity** | low |
| **Trigger condition** | `COALESCE(price_total, price_contract) = 0` |

**Description:**
The contract has a stated price, but the value is zero. The lower severity reflects that this is an explicitly provided value (not missing data).

**Legitimate cases:**
- Framework agreements with zero initial value
- Gratuitous transfers
- Repairs and maintenance at no cost to the contracting authority
- CRZ metadata conventions (zero as a placeholder)

---

### 3. `MISSING_SUPPLIER` — Missing Supplier

| Attribute | Value |
|-----------|-------|
| **Code** | `MISSING_SUPPLIER` |
| **Severity** | medium |
| **Trigger condition** | `supplier_name` is `NULL`, empty string, or whitespace only |

**Description:**
The contract does not include the supplier's name. Without this field, the contract cannot be linked to a specific entity, making market analysis and transparency verification difficult.

**Legitimate cases:**
- Supplier is listed in an attachment rather than in metadata
- Special contract types (e.g., agreements to conclude a future contract)

---

### 4. `MISSING_SUPPLIER_ICO` — Missing Supplier IČO

| Attribute | Value |
|-----------|-------|
| **Code** | `MISSING_SUPPLIER_ICO` |
| **Severity** | medium |
| **Trigger condition** | `supplier_ico` is `NULL`, empty string, or whitespace only |
| **Approximate frequency** | ~23% of contracts |

**Description:**
The contract does not include the supplier's organization identification number (IČO). Missing IČO prevents automatic linking with the Register of Legal Entities (RPO) and aggregation of contracts under a single supplier.

**Legitimate cases:**
- Foreign suppliers without a Slovak IČO
- Natural persons (self-employed, OSČD) not registered in RPO
- Special cases (diplomatic missions, international organizations)

---

### 5. `INVALID_ICO_FORMAT` — Invalid IČO Format

| Attribute | Value |
|-----------|-------|
| **Code** | `INVALID_ICO_FORMAT` |
| **Severity** | low |
| **Trigger condition** | IČO is present but, after normalization (removing non-digits), does not contain exactly 8 digits |

**Description:**
An identification number is filled in but does not meet the expected format of a Slovak IČO (8 digits after normalization). Both `supplier_ico` and `buyer_ico` are checked. The flag fires if at least one has an invalid format.

**Legitimate cases:**
- Foreign identifiers (e.g., Czech IČO may have 8 digits, but other countries use different formats)
- Formatting errors (spaces, dashes, prefixes)
- Legacy records with inconsistent notation

---

### 6. `MISSING_BUYER_ICO` — Missing Buyer IČO

| Attribute | Value |
|-----------|-------|
| **Code** | `MISSING_BUYER_ICO` |
| **Severity** | medium |
| **Trigger condition** | `buyer_ico` is `NULL`, empty string, or whitespace only |
| **Approximate frequency** | ~17.5% of contracts |

**Description:**
The contract does not include the buyer's IČO (the public entity that concluded the contract). Missing buyer IČO makes it harder to filter and aggregate contracts by institution.

**Legitimate cases:**
- Older records from before mandatory buyer IČO was introduced
- Unusual public entities without a standard IČO

---

## Compound Severity

A contract may have multiple flags active simultaneously. Compound severity is computed according to these rules:

| Condition | Resulting Severity |
|-----------|--------------------|
| 3 or more flags | **high** |
| 1–2 flags | maximum of individual severities |
| 0 flags | **none** |

**Severity hierarchy:** `low` < `medium` < `high`

The 3+ flag rule reflects the fact that cumulative metadata deficiency increases the risk of being unable to verify a contract — even when individual flags are less severe.

### Examples

| Active Flags | Individual Severities | Result |
|-------------|----------------------|--------|
| `ZERO_PRICE` | low | **low** |
| `MISSING_PRICE` | medium | **medium** |
| `ZERO_PRICE`, `MISSING_SUPPLIER_ICO` | low, medium | **medium** |
| `MISSING_PRICE`, `MISSING_SUPPLIER`, `MISSING_BUYER_ICO` | medium, medium, medium | **high** |
| `ZERO_PRICE`, `INVALID_ICO_FORMAT`, `MISSING_SUPPLIER_ICO`, `MISSING_BUYER_ICO` | low, low, medium, medium | **high** |

---

## Re-flagging Lifecycle

Flags are not static — they are recalculated on every pipeline run:

1. **Each run has an identifier** (`source_run_id`) tied to a specific ingestion run (`ingestion_runs`).
2. **During iteration**, old flags from previous runs are deleted per-contract (`source_run_id != current run_id`), with a final cleanup pass for any remaining stale flags.
3. **Evaluation** — all active flag checkers are run for each contract in the order defined by `FLAG_CHECKERS`.
4. **Persistence** — new flags are written with the current `source_run_id`, severity, reason, and evidence (JSON).

This approach guarantees that **flags always reflect the current contract state** and are not affected by stale artifacts from previous runs.

```
┌──────────────┐    ┌──────────────────────┐    ┌──────────────────┐
│ Ingestion    │───▶│ Delete old flags     │───▶│ Evaluate         │
│ (run_id = N) │    │ (run_id ≠ N)         │    │ new flags        │
└──────────────┘    └──────────────────────┘    └──────────────────┘
                                                          │
                                                          ▼
                                                ┌──────────────────┐
                                                │ Persist with     │
                                                │ source_run_id = N│
                                                └──────────────────┘
```

---

## Technical Implementation

Flags are implemented in the following modules:

| File | Purpose |
|------|---------|
| `app/flags/definitions.py` | Flag definitions (code, name, description, severity, methodology) |
| `app/flags/evaluate.py` | Evaluation engine — checkers and compound severity |
| `app/flags/flags_catalog.py` | Seeding definitions into the database |

Each checker accepts a `Contract` object and returns a `FlagMatch` or `None`. The result includes the flag code, severity, reason, and evidence (a dictionary of specific values that triggered the flag).

---

## MVP Phase Limitations

- All flags work **exclusively with metadata** — they do not analyze PDF attachment contents.
- No OCR, NLP, or machine learning is used.
- Flags do not account for historical contract changes (versions).
- Flags are binary (active/inactive) — no weighted scoring is applied.

---

> **Disclaimer:** These flags signal metadata quality, not suspicion of fraud. Their purpose is to help identify contracts with incomplete data for further manual review or for improving data quality in the register.
