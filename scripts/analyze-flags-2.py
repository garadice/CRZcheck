# ruff: noqa: E501
"""Second-pass flag analysis: what remains after natural person suppression?

Focuses on:
1. ZERO_PRICE on legal-entity contracts — what are these?
2. MISSING_BUYER_ICO — which buyers have no IČO? Why?
3. Remaining MISSING_SUPPLIER_ICO on legal entities
4. Flag combinations among remaining contracts
5. Title/subject patterns in the remaining pool

Usage:
    cd /opt/crz-monitor && .venv/bin/python scripts/analyze-flags-2.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Contract, ContractRiskFlag, RiskFlag, Supplier
from app.db.session import get_engine
from app.transforms.entities import normalize_entity_name


def get_np_status(
    session: Session, supplier_name: str | None, supplier_ico: str | None
) -> bool | None:
    """Check if supplier is natural person via suppliers table."""
    if not supplier_name:
        return None
    if supplier_ico:
        stmt = (
            select(Supplier.is_probable_natural_person).where(Supplier.ico == supplier_ico).limit(1)
        )
        result = session.execute(stmt).scalar_one_or_none()
        if result is not None:
            return result
    norm = normalize_entity_name(supplier_name)
    if norm:
        stmt = (
            select(Supplier.is_probable_natural_person)
            .where(Supplier.normalized_name == norm)
            .limit(1)
        )
        result = session.execute(stmt).scalar_one_or_none()
        if result is not None:
            return result
    return None


TITLE_CATEGORIES = {
    "výpožička zberných nádob": ["výpožičk", "zberných nádob", "zbernych nadob"],
    "nájom / vodomer": [
        "nájme",
        "najme",
        "vodomer",
        "nájomn",
        "najomn",
        "nájom",
        "najom nehnuteľn",
    ],
    "dodatok / oprava": ["dodatok", "doplnok", "oprav", "zmena zmluvy"],
    "dohoda": ["dohoda"],
    "erasmus / grant": ["erasmus", "grant", "projekt"],
    "dar / bezplatný": ["darovac", "bezplatn", "dar ", "darom"],
    "kúpna / nákup": ["kúpn", "kupn", "nákup", "nakup"],
    "služba / dodávka": ["služb", "sluzb", "dodáv", "dodav"],
    "výkon / dielo": ["dielo", "vykonaní diela", "výkon", "vykon"],
    "prevod / prevod": ["prevod"],
    "o vode / vodovode": ["pitnej vode", "vodovod", "vodárensk", "vody"],
}


def classify_title(title: str | None) -> str | None:
    if not title:
        return None
    title_lower = title.lower()
    for category, keywords in TITLE_CATEGORIES.items():
        for kw in keywords:
            if kw in title_lower:
                return category
    return None


def extract_words(text: str | None) -> list[str]:
    if not text:
        return []
    stop = {
        "a",
        "o",
        "na",
        "v",
        "z",
        "zo",
        "za",
        "do",
        "od",
        "pre",
        "pod",
        "nad",
        "pri",
        "s",
        "so",
        "k",
        "ku",
        "po",
        "bez",
        "medzi",
        "cez",
        "the",
        "of",
        "and",
        "for",
        "in",
        "to",
        "je",
        "sa",
        "si",
        "by",
        "aj",
        "alebo",
        "nie",
        "tam",
        "tu",
        "no",
    }
    words = re.findall(r"[a-záäčďéíĺľňóôŕšťúýž]{3,}", text.lower())
    return [w for w in words if w not in stop]


def main():
    engine = get_engine()
    with Session(engine) as session:
        print("=" * 80)
        print("FLAG ANALYSIS #2 — What remains after natural person suppression?")
        print("=" * 80)

        # ── Step A: Build the suppression map ──
        print("\n## A. BUILDING SUPPRESSION MAP\n")

        # Get all flagged contract IDs with supplier info
        flagged = session.execute(
            select(
                Contract.crz_contract_id,
                Contract.title,
                Contract.subject,
                Contract.supplier_name,
                Contract.supplier_ico,
                Contract.buyer_name,
                Contract.buyer_ico,
                Contract.price_total,
                Contract.price_contract,
            )
            .join(ContractRiskFlag, ContractRiskFlag.crz_contract_id == Contract.crz_contract_id)
            .distinct()
        ).all()

        np_cache: dict[str, bool | None] = {}
        suppressed_contracts: set[str] = set()  # fully cleared
        remaining_contracts: set[str] = set()

        for row in flagged:
            (
                cid,
                title,
                subject,
                sup_name,
                sup_ico,
                buyer_name,
                buyer_ico,
                price_total,
                price_contract,
            ) = row
            cache_key = f"{sup_ico}:{sup_name}"
            if cache_key not in np_cache:
                np_cache[cache_key] = get_np_status(session, sup_name, sup_ico)
            is_np = np_cache[cache_key]

            # Get flags for this contract
            c_flags = list(
                session.execute(
                    select(RiskFlag.flag_code)
                    .join(ContractRiskFlag, ContractRiskFlag.flag_id == RiskFlag.id)
                    .where(ContractRiskFlag.crz_contract_id == cid)
                ).scalars()
            )

            remaining = list(c_flags)

            # Rule 1: natural person → suppress MISSING_SUPPLIER_ICO
            if is_np and "MISSING_SUPPLIER_ICO" in remaining:
                remaining.remove("MISSING_SUPPLIER_ICO")

            # Rule 2: natural person → suppress ZERO_PRICE
            if is_np and "ZERO_PRICE" in remaining:
                remaining.remove("ZERO_PRICE")

            if not remaining:
                suppressed_contracts.add(cid)
            else:
                remaining_contracts.add(cid)

        print(f"Total flagged:          {len(flagged):,}")
        print(f"Fully suppressed (NP):  {len(suppressed_contracts):,}")
        print(f"Remaining flagged:      {len(remaining_contracts):,}")

        # ── Step B: Remaining flag distribution ──
        print("\n## B. REMAINING FLAG DISTRIBUTION\n")

        if not remaining_contracts:
            print("No remaining contracts!")
            return

        remaining_flag_dist = session.execute(
            select(RiskFlag.flag_code, func.count(ContractRiskFlag.id))
            .join(RiskFlag, RiskFlag.id == ContractRiskFlag.flag_id)
            .where(ContractRiskFlag.crz_contract_id.in_(remaining_contracts))
            .group_by(RiskFlag.flag_code)
            .order_by(func.count(ContractRiskFlag.id).desc())
        ).all()

        remaining_flag_total = sum(count for _, count in remaining_flag_dist)
        for flag_code, count in remaining_flag_dist:
            pct = count / remaining_flag_total * 100
            print(f"  {flag_code:30s}  {count:6,}  ({pct:5.1f}%)")

        # ── Step C: ZERO_PRICE deep dive ──
        print("\n## C. ZERO_PRICE DEEP DIVE (remaining contracts)\n")

        zero_price_contracts = (
            session.execute(
                select(Contract)
                .join(
                    ContractRiskFlag, ContractRiskFlag.crz_contract_id == Contract.crz_contract_id
                )
                .join(RiskFlag, RiskFlag.id == ContractRiskFlag.flag_id)
                .where(
                    ContractRiskFlag.crz_contract_id.in_(remaining_contracts),
                    RiskFlag.flag_code == "ZERO_PRICE",
                )
                .distinct()
            )
            .scalars()
            .all()
        )

        print(f"Contracts with ZERO_PRICE: {len(zero_price_contracts):,}")

        # Title categories
        zp_categories = Counter()
        for c in zero_price_contracts:
            cat = classify_title(c.title)
            if cat:
                zp_categories[cat] += 1

        print("\nTitle categories:")
        for cat, count in zp_categories.most_common(20):
            print(f"  {cat:35s}  {count:5,}  ({count / len(zero_price_contracts) * 100:.1f}%)")

        # Title words
        zp_words = Counter()
        for c in zero_price_contracts:
            zp_words.update(extract_words(c.title))
        print("\nTop title words:")
        for word, count in zp_words.most_common(25):
            print(f"  {word:25s}  {count:5,}")

        # Supplier analysis for zero-price
        zp_supplier_types = {"legal": 0, "np": 0, "unknown": 0}
        zp_supplier_names: Counter = Counter()
        for c in zero_price_contracts:
            cache_key = f"{c.supplier_ico}:{c.supplier_name}"
            is_np = np_cache.get(cache_key)
            if is_np:
                zp_supplier_types["np"] += 1
            elif is_np is False:
                zp_supplier_types["legal"] += 1
            else:
                zp_supplier_types["unknown"] += 1
            if c.supplier_name:
                zp_supplier_names[c.supplier_name[:60]] += 1

        print("\nSupplier types:")
        print(f"  Legal entity:   {zp_supplier_types['legal']:,}")
        print(f"  Natural person: {zp_supplier_types['np']:,}")
        print(f"  Unknown:        {zp_supplier_types['unknown']:,}")

        print("\nTop suppliers on zero-price contracts:")
        for name, count in zp_supplier_names.most_common(20):
            print(f"  [{count:4,}]  {name}")

        # Buyer analysis for zero-price
        zp_buyer_names: Counter = Counter()
        for c in zero_price_contracts:
            if c.buyer_name:
                zp_buyer_names[c.buyer_name[:60]] += 1
        print("\nTop buyers on zero-price contracts:")
        for name, count in zp_buyer_names.most_common(15):
            print(f"  [{count:4,}]  {name}")

        # What other flags do zero-price contracts have?
        zp_flag_combos = Counter()
        for c in zero_price_contracts:
            c_flags = sorted(
                session.execute(
                    select(RiskFlag.flag_code)
                    .join(ContractRiskFlag, ContractRiskFlag.flag_id == RiskFlag.id)
                    .where(ContractRiskFlag.crz_contract_id == c.crz_contract_id)
                ).scalars()
            )
            zp_flag_combos[" + ".join(c_flags)] += 1

        print("\nFlag combinations (zero-price contracts):")
        for combo, count in zp_flag_combos.most_common(15):
            print(f"  [{count:5,}]  {combo}")

        # Sample zero-price contract titles
        print("\nSample zero-price contracts (first 30):")
        for i, c in enumerate(zero_price_contracts[:30], 1):
            t = (c.title or "(no title)")[:70]
            s = (c.supplier_name or "?")[:40]
            b = (c.buyer_name or "?")[:40]
            print(f"  {i:2d}. {t}")
            print(f"      Buyer: {b} | Supplier: {s}")

        # ── Step D: MISSING_BUYER_ICO deep dive ──
        print("\n## D. MISSING_BUYER_ICO DEEP DIVE\n")

        mbi_contracts = (
            session.execute(
                select(Contract)
                .join(
                    ContractRiskFlag, ContractRiskFlag.crz_contract_id == Contract.crz_contract_id
                )
                .join(RiskFlag, RiskFlag.id == ContractRiskFlag.flag_id)
                .where(
                    ContractRiskFlag.crz_contract_id.in_(remaining_contracts),
                    RiskFlag.flag_code == "MISSING_BUYER_ICO",
                )
                .distinct()
            )
            .scalars()
            .all()
        )

        print(f"Contracts with MISSING_BUYER_ICO: {len(mbi_contracts):,}")

        # Who are these buyers?
        buyer_names: Counter = Counter()
        for c in mbi_contracts:
            if c.buyer_name:
                buyer_names[c.buyer_name[:70]] += 1

        print("\nTop buyers WITHOUT IČO:")
        for name, count in buyer_names.most_common(30):
            print(f"  [{count:4,}]  {name}")

        # Are these foreign buyers?
        foreign_keywords = [
            "gmbh",
            "gesellschaft",
            "universit",
            "city",
            "council",
            "municipal",
            "region",
            "county",
            "commune",
            "ministry",
            "school",
            "college",
            "academy",
            "institut",
        ]
        foreign_count = 0
        slovak_count = 0
        for name, _ in buyer_names.most_common(100):
            name_lower = name.lower()
            if any(kw in name_lower for kw in foreign_keywords):
                foreign_count += 1
            else:
                slovak_count += 1

        print("\nOf top 100 buyers without IČO:")
        print(f"  Possibly foreign (keyword match): {foreign_count}")
        print(f"  Likely Slovak:                    {slovak_count}")

        # What other flags accompany MISSING_BUYER_ICO?
        mbi_flag_combos = Counter()
        for c in mbi_contracts:
            c_flags = sorted(
                session.execute(
                    select(RiskFlag.flag_code)
                    .join(ContractRiskFlag, ContractRiskFlag.flag_id == RiskFlag.id)
                    .where(ContractRiskFlag.crz_contract_id == c.crz_contract_id)
                ).scalars()
            )
            mbi_flag_combos[" + ".join(c_flags)] += 1

        print("\nFlag combinations (MISSING_BUYER_ICO contracts):")
        for combo, count in mbi_flag_combos.most_common(15):
            print(f"  [{count:5,}]  {combo}")

        # ── Step E: MISSING_SUPPLIER_ICO on legal entities ──
        print("\n## E. MISSING_SUPPLIER_ICO ON LEGAL ENTITIES\n")

        msi_legal = []
        for row in flagged:
            cid = row[0]
            if cid not in remaining_contracts:
                continue
            sup_name, sup_ico = row[3], row[4]
            cache_key = f"{sup_ico}:{sup_name}"
            is_np = np_cache.get(cache_key)

            c_flags = list(
                session.execute(
                    select(RiskFlag.flag_code)
                    .join(ContractRiskFlag, ContractRiskFlag.flag_id == RiskFlag.id)
                    .where(ContractRiskFlag.crz_contract_id == cid)
                ).scalars()
            )
            if "MISSING_SUPPLIER_ICO" in c_flags and is_np is False:
                msi_legal.append(row)

        print(f"Legal entities with MISSING_SUPPLIER_ICO: {len(msi_legal):,}")

        legal_supplier_names: Counter = Counter()
        for row in msi_legal:
            _, title, _, sup_name, sup_ico, _, _, _, _ = row
            if sup_name:
                legal_supplier_names[sup_name[:70]] += 1

        print("\nTop legal entity suppliers WITHOUT IČO:")
        for name, count in legal_supplier_names.most_common(20):
            print(f"  [{count:4,}]  {name}")

        # ── Step F: Summary — what's genuinely interesting? ──
        print("\n## F. SUMMARY — WHAT'S GENUINELY INTERESTING?\n")

        # Count contracts that ONLY have MISSING_BUYER_ICO
        only_mbi = 0
        # Count contracts that ONLY have ZERO_PRICE
        only_zp = 0
        # Count contracts with both
        both_mbi_zp = 0
        # Count contracts with other interesting combos
        other = 0

        for cid in remaining_contracts:
            c_flags = set(
                session.execute(
                    select(RiskFlag.flag_code)
                    .join(ContractRiskFlag, ContractRiskFlag.flag_id == RiskFlag.id)
                    .where(ContractRiskFlag.crz_contract_id == cid)
                ).scalars()
            )

            if c_flags == {"MISSING_BUYER_ICO"}:
                only_mbi += 1
            elif c_flags == {"ZERO_PRICE"}:
                only_zp += 1
            elif c_flags == {"MISSING_BUYER_ICO", "ZERO_PRICE"}:
                both_mbi_zp += 1
            else:
                other += 1

        print(f"Remaining {len(remaining_contracts):,} contracts breakdown:")
        print(f"  ONLY ZERO_PRICE:               {only_zp:,}")
        print(f"  ONLY MISSING_BUYER_ICO:        {only_mbi:,}")
        print(f"  BOTH ZERO_PRICE + MISSING_BUYER_ICO: {both_mbi_zp:,}")
        print(f"  Other combos (genuinely interesting): {other:,}")

        # ── Step G: What if we also suppress these? ──
        print("\n## G. IMPACT OF ADDITIONAL SUPPRESSION\n")

        # Scenario A: Also suppress MISSING_BUYER_ICO → reclassify as data completeness
        len(remaining_contracts) - only_mbi - both_mbi_zp
        # But wait, both_mbi_zp still has ZERO_PRICE
        # After removing MBI, those contracts still have ZERO_PRICE
        # Only "only_mbi" would be fully cleared
        cleared_by_mbi_reclassify = only_mbi

        # Scenario B: Also suppress ZERO_PRICE on specific title patterns
        zp_title_suppressed = 0
        for c in zero_price_contracts:
            cat = classify_title(c.title)
            if cat in ("výpožička zberných nádob", "nájom / vodomer", "dodatok / oprava"):
                zp_title_suppressed += 1

        print("If we also reclassify MISSING_BUYER_ICO as 'data completeness':")
        print(f"  Contracts fully cleared:  {cleared_by_mbi_reclassify:,}")
        print(
            f"  Remaining:                {len(remaining_contracts) - cleared_by_mbi_reclassify:,}"
        )
        print()
        print("If we also suppress ZERO_PRICE for výpožička/nájom/dodatok titles:")
        print(f"  ZERO_PRICE flags removed: {zp_title_suppressed:,}")
        print()
        print("Combined scenario (NP + MBI reclassify + title-based ZERO_PRICE):")
        # Final remaining = remaining - cleared_by_mbi - those cleared by title suppressions
        # (rough estimate — some may overlap)
        final_estimate = len(remaining_contracts) - cleared_by_mbi_reclassify
        print(f"  Remaining in Oznamy:      ~{final_estimate:,} (down from {len(flagged):,})")
        print(f"  Total reduction:          ~{(1 - final_estimate / len(flagged)) * 100:.0f}%")

        # ── Step H: Final remaining samples ──
        print("\n## H. SAMPLE CONTRACTS IN FINAL OZNAMY VIEW\n")

        # Show contracts that would remain after ALL proposed suppressions
        final_remaining = []
        for row in flagged:
            cid = row[0]
            if cid in suppressed_contracts:
                continue

            c_flags = set(
                session.execute(
                    select(RiskFlag.flag_code)
                    .join(ContractRiskFlag, ContractRiskFlag.flag_id == RiskFlag.id)
                    .where(ContractRiskFlag.crz_contract_id == cid)
                ).scalars()
            )

            # Remove NP-suppressed flags
            cache_key = f"{row[4]}:{row[3]}"
            is_np = np_cache.get(cache_key)
            if is_np:
                c_flags.discard("MISSING_SUPPLIER_ICO")
                c_flags.discard("ZERO_PRICE")

            # Remove MISSING_BUYER_ICO (reclassified)
            c_flags.discard("MISSING_BUYER_ICO")

            # Remove title-based ZERO_PRICE suppressions
            cat = classify_title(row[1])
            if cat in ("výpožička zberných nádob", "nájom / vodomer", "dodatok / oprava"):
                c_flags.discard("ZERO_PRICE")

            if c_flags:
                final_remaining.append(row)

        print(f"Contracts in final Oznamy view: {len(final_remaining):,}")
        print()

        # Sample the final remaining
        for i, row in enumerate(final_remaining[:20], 1):
            (
                cid,
                title,
                subject,
                sup_name,
                sup_ico,
                buyer_name,
                buyer_ico,
                price_total,
                price_contract,
            ) = row
            t = (title or "(no title)")[:65]
            s = (sup_name or "?")[:35]
            b = (buyer_name or "?")[:35]
            p = (
                f"€{price_total:,.0f}"
                if price_total
                else ("€" + str(price_contract) if price_contract else "€0")
            )

            cache_key = f"{sup_ico}:{sup_name}"
            is_np = np_cache.get(cache_key)

            c_flags = list(
                session.execute(
                    select(RiskFlag.flag_code)
                    .join(ContractRiskFlag, ContractRiskFlag.flag_id == RiskFlag.id)
                    .where(ContractRiskFlag.crz_contract_id == cid)
                ).scalars()
            )

            flags_str = ", ".join(c_flags)
            print(f"  {i:2d}. {t}")
            print(f"      Buyer: {b} | Supplier: {s}")
            print(f"      Price: {p} | Flags: {flags_str}")

        print("\n" + "=" * 80)
        print("END OF REPORT")


if __name__ == "__main__":
    main()
