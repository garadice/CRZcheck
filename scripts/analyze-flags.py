# ruff: noqa: E501
"""Analyze flagged contracts to understand false-positive patterns.

This script queries the production database and produces a report showing:
1. How many flagged contracts involve natural person suppliers
2. What contract titles are most common among flagged contracts
3. What flag combinations appear and which involve natural persons
4. Impact of proposed suppression rules

Usage:
    cd /opt/crz-monitor && .venv/bin/python scripts/analyze-flags.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Contract, ContractRiskFlag, RiskFlag, Supplier
from app.db.session import get_engine

# ─── Title keyword patterns ─────────────────────────────────────────────────

CONTRACT_TYPE_KEYWORDS = {
    "nájom": ["nájom", "najom", "nájomn", "najomn", "prenájom", "prenajom"],
    "dohoda o spolupráci": ["dohoda o spolupráci", "dohoda o spolupraci", "spolupráci", "spolupraci"],
    "darovacia/dar": ["darovac", "darovací", "bezplatn", "dar ", "darom"],
    "kúpna/nákup": ["kúpn", "kupn", "nákup", "nakup", "obstaráv", "obstarav"],
    "služba/service": ["služb", "sluzb", "servis"],
    "pracovná/zamestnanie": ["pracovn", "brigádnic", "brigadnic", "zamestnan", "dohoda o vykonaní práce", "dohoda o brigádnickej"],
    "mandátna": ["mandátn", "mandatn"],
    "dielo/dielo": ["dielo", "vykonaní diela", "vykonani diela"],
    "úver/pôžička": ["úver", "uver", "pôžičk", "pozick", "financov"],
    "prevod/prevod vlastníctva": ["prevod vlast", "prevod nehnuteľn", "prevod nehytnuteľn"],
    "o pitnej vode": ["pitnej vode", "vodovod", "vodárensk"],
    "vzdelávanie/prax": ["odborná prax", "vzdeláv", "vzdelav", "stáž", "staz", "prax"],
}


def classify_title(title: str | None) -> str | None:
    """Classify a contract title into a category. Returns first match or None."""
    if not title:
        return None
    title_lower = title.lower()
    for category, keywords in CONTRACT_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in title_lower:
                return category
    return None


def is_natural_person_supplier(session: Session, supplier_name: str | None, supplier_ico: str | None) -> bool | None:
    """Check if supplier is flagged as natural person in the suppliers table."""
    if not supplier_name:
        return None
    # Try to match by ICO first
    if supplier_ico:
        stmt = select(Supplier.is_probable_natural_person).where(Supplier.ico == supplier_ico)
        result = session.execute(stmt).scalar_one_or_none()
        if result is not None:
            return result
    # Try to match by normalized name
    from app.transforms.entities import normalize_entity_name
    norm = normalize_entity_name(supplier_name)
    if norm:
        stmt = select(Supplier.is_probable_natural_person).where(Supplier.normalized_name == norm)
        result = session.execute(stmt).scalar_one_or_none()
        if result is not None:
            return result
    return None


def extract_title_words(title: str | None) -> list[str]:
    """Extract meaningful words from a title for frequency analysis."""
    if not title:
        return []
    # Remove common stop words
    stop_words = {
        "a", "o", "na", "v", "z", "zo", "za", "do", "od", "pre", "pod",
        "nad", "pri", "s", "so", "k", "ku", "po", "bez", "medzi", "cez",
        "the", "of", "and", "for", "in", "to", "–", "-", "/", ":", ";",
        "je", "sa", "si", "by", "aj", "alebo", "nie", "tam", "tu",
        "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
        "i", "ii", "iii", "iv", "vi",
    }
    words = re.findall(r"[a-záäčďéíĺľňóôŕšťúýž]{3,}", title.lower())
    return [w for w in words if w not in stop_words]


def main():
    engine = get_engine()
    with Session(engine) as session:
        print("=" * 80)
        print("FLAG ANALYSIS REPORT — CRZ Risk & Quality Monitor")
        print("=" * 80)

        # ── 1. Overall stats ──
        print("\n## 1. OVERALL STATS\n")

        total_contracts = session.execute(select(func.count(Contract.crz_contract_id))).scalar()
        total_flagged = session.execute(
            select(func.count(func.distinct(ContractRiskFlag.crz_contract_id)))
        ).scalar()
        total_flags = session.execute(select(func.count(ContractRiskFlag.id))).scalar()

        # Count distinct natural person suppliers
        total_np_suppliers = session.execute(
            select(func.count(Supplier.id)).where(Supplier.is_probable_natural_person == True)  # noqa: E712
        ).scalar()
        total_legal_suppliers = session.execute(
            select(func.count(Supplier.id)).where(Supplier.is_probable_natural_person == False)  # noqa: E712
        ).scalar()

        print(f"Total contracts:              {total_contracts:,}")
        print(f"Flagged contracts:            {total_flagged:,} ({total_flagged/total_contracts*100:.1f}%)")
        print(f"Total flags:                  {total_flags:,}")
        print(f"Avg flags per flagged:        {total_flags/total_flagged:.2f}")
        print(f"Natural person suppliers:     {total_np_suppliers:,}")
        print(f"Legal entity suppliers:       {total_legal_suppliers:,}")

        # ── 2. Flag distribution ──
        print("\n## 2. FLAG DISTRIBUTION\n")

        flag_dist = session.execute(
            select(RiskFlag.flag_code, func.count(ContractRiskFlag.id))
            .join(RiskFlag, RiskFlag.id == ContractRiskFlag.flag_id)
            .group_by(RiskFlag.flag_code)
            .order_by(func.count(ContractRiskFlag.id).desc())
        ).all()

        for flag_code, count in flag_dist:
            pct = count / total_flags * 100
            print(f"  {flag_code:30s}  {count:6,}  ({pct:5.1f}%)")

        # ── 3. Flagged contracts with natural person suppliers ──
        print("\n## 3. NATURAL PERSON ANALYSIS\n")

        # Get all flagged contracts with their supplier info
        flagged_contracts = session.execute(
            select(
                Contract.crz_contract_id,
                Contract.title,
                Contract.supplier_name,
                Contract.supplier_ico,
                Contract.price_total,
                Contract.price_contract,
            )
            .join(ContractRiskFlag, ContractRiskFlag.crz_contract_id == Contract.crz_contract_id)
            .distinct()
        ).all()

        print(f"Total flagged contracts: {len(flagged_contracts):,}")

        # Classify each flagged contract
        np_count = 0
        legal_count = 0
        unknown_count = 0
        title_categories = Counter()
        np_title_categories = Counter()
        title_words_all = Counter()
        title_words_np = Counter()
        Counter()
        Counter()
        np_with_price = 0
        np_without_price = 0
        legal_with_price = 0
        legal_without_price = 0

        # Cache for natural person lookups
        np_cache: dict[str, bool | None] = {}

        for row in flagged_contracts:
            cid, title, supplier_name, supplier_ico, price_total, price_contract = row

            # Check natural person status
            cache_key = f"{supplier_ico}:{supplier_name}"
            if cache_key not in np_cache:
                np_cache[cache_key] = is_natural_person_supplier(session, supplier_name, supplier_ico)
            is_np = np_cache[cache_key]

            if is_np is True:
                np_count += 1
            elif is_np is False:
                legal_count += 1
            else:
                unknown_count += 1

            # Title classification
            category = classify_title(title)
            if category:
                title_categories[category] += 1
                if is_np:
                    np_title_categories[category] += 1

            # Title word frequency
            words = extract_title_words(title)
            title_words_all.update(words)
            if is_np:
                title_words_np.update(words)

            # Price analysis
            has_price = price_total is not None or price_contract is not None
            if is_np:
                if has_price:
                    np_with_price += 1
                else:
                    np_without_price += 1
            elif is_np is False:
                if has_price:
                    legal_with_price += 1
                else:
                    legal_without_price += 1

        print(f"\nSupplier type breakdown (among {len(flagged_contracts):,} flagged):")
        print(f"  Natural person:     {np_count:,} ({np_count/len(flagged_contracts)*100:.1f}%)")
        print(f"  Legal entity:       {legal_count:,} ({legal_count/len(flagged_contracts)*100:.1f}%)")
        print(f"  Unknown/uncached:   {unknown_count:,} ({unknown_count/len(flagged_contracts)*100:.1f}%)")

        print("\nPrice analysis:")
        print(f"  Natural persons WITH price:    {np_with_price:,} / {np_count:,}")
        print(f"  Natural persons WITHOUT price: {np_without_price:,} / {np_count:,}")
        print(f"  Legal entities WITH price:     {legal_with_price:,} / {legal_count:,}")
        print(f"  Legal entities WITHOUT price:  {legal_without_price:,} / {legal_count:,}")

        # ── 4. Title categories ──
        print("\n## 4. CONTRACT TITLE CATEGORIES\n")

        print("All flagged contracts:")
        for cat, count in title_categories.most_common(15):
            np_of_cat = np_title_categories.get(cat, 0)
            pct = count / len(flagged_contracts) * 100
            print(f"  {cat:40s}  {count:5,} ({pct:5.1f}%)  [NP: {np_of_cat}]")

        # ── 5. Top title words ──
        print("\n## 5. TOP TITLE WORDS (flagged contracts)\n")

        print("All flagged:")
        for word, count in title_words_all.most_common(30):
            print(f"  {word:25s}  {count:5,}")

        print("\nNatural person flagged only:")
        for word, count in title_words_np.most_common(30):
            print(f"  {word:25s}  {count:5,}")

        # ── 6. Flag combinations on natural person contracts ──
        print("\n## 6. FLAGS ON NATURAL PERSON CONTRACTS\n")

        np_contract_ids = set()
        for row in flagged_contracts:
            cid, title, supplier_name, supplier_ico, _, _ = row
            cache_key = f"{supplier_ico}:{supplier_name}"
            if np_cache.get(cache_key):
                np_contract_ids.add(cid)

        if np_contract_ids:
            np_flags = session.execute(
                select(ContractRiskFlag.crz_contract_id, RiskFlag.flag_code)
                .join(RiskFlag, RiskFlag.id == ContractRiskFlag.flag_id)
                .where(ContractRiskFlag.crz_contract_id.in_(np_contract_ids))
            ).all()

            flags_per_np_contract: dict[str, list[str]] = {}
            for cid, flag_code in np_flags:
                flags_per_np_contract.setdefault(cid, []).append(flag_code)

            combo_counter = Counter()
            for _cid, flags in flags_per_np_contract.items():
                combo = " + ".join(sorted(flags))
                combo_counter[combo] += 1

            print(f"Flag combinations on {len(np_contract_ids):,} natural person contracts:")
            for combo, count in combo_counter.most_common(20):
                print(f"  [{count:5,}]  {combo}")

        # ── 7. Suppression rule impact ──
        print("\n## 7. SUPPRESSION RULE IMPACT ESTIMATE\n")

        # Rule: suppress MISSING_SUPPLIER_ICO if natural person
        rule1_removed = 0
        rule2_removed = 0
        rule3_removed = 0
        rule4_removed = 0
        total_removed = 0

        for row in flagged_contracts:
            cid, title, supplier_name, supplier_ico, price_total, price_contract = row
            cache_key = f"{supplier_ico}:{supplier_name}"
            is_np = np_cache.get(cache_key)
            category = classify_title(title)

            flags_for_contract = []
            if cid in np_contract_ids:
                flags_for_contract = [f for c, f in np_flags if c == cid]
            else:
                # Get flags for this contract
                c_flags = session.execute(
                    select(RiskFlag.flag_code)
                    .join(ContractRiskFlag, ContractRiskFlag.flag_id == RiskFlag.id)
                    .where(ContractRiskFlag.crz_contract_id == cid)
                ).scalars().all()
                flags_for_contract = list(c_flags)

            removed_any = False

            # Rule 1: Natural person → suppress MISSING_SUPPLIER_ICO
            if is_np and "MISSING_SUPPLIER_ICO" in flags_for_contract:
                rule1_removed += 1
                removed_any = True

            # Rule 2: Title "dohoda o spolupráci" / "spolupráca" → suppress MISSING_PRICE
            if category == "dohoda o spolupráci" and "MISSING_PRICE" in flags_for_contract:
                rule2_removed += 1
                removed_any = True

            # Rule 3: Title "darovacia/dar" → suppress MISSING_PRICE, ZERO_PRICE
            if category == "darovacia/dar" and ("MISSING_PRICE" in flags_for_contract or "ZERO_PRICE" in flags_for_contract):
                rule3_removed += 1
                removed_any = True

            # Rule 4: Title "vzdelávanie/prax" → suppress MISSING_PRICE
            if category == "vzdelávanie/prax" and "MISSING_PRICE" in flags_for_contract:
                rule4_removed += 1
                removed_any = True

            if removed_any:
                total_removed += 1

        print("Rule 1: Natural person → suppress MISSING_SUPPLIER_ICO")
        print(f"  Flags removed:  {rule1_removed:,}")
        print()
        print("Rule 2: 'Dohoda o spolupráci' → suppress MISSING_PRICE")
        print(f"  Flags removed:  {rule2_removed:,}")
        print()
        print("Rule 3: 'Darovacia/dar' → suppress MISSING_PRICE, ZERO_PRICE")
        print(f"  Flags removed:  {rule3_removed:,}")
        print()
        print("Rule 4: 'Vzdelávanie/prax' → suppress MISSING_PRICE")
        print(f"  Flags removed:  {rule4_removed:,}")
        print()
        print(f"Total flag suppressions:  {total_removed:,}")
        print(f"Current total flags:      {total_flags:,}")
        print(f"Reduction:                {total_removed/total_flags*100:.1f}%")

        # ── 8. What Oznamy would look like ──
        print("\n## 8. WHAT REMAINS IN OZNAMY AFTER SUPPRESSION\n")

        # Contracts that would have ZERO flags remaining
        contracts_with_only_suppressed_flags = set()
        for row in flagged_contracts:
            cid, title, supplier_name, supplier_ico, price_total, price_contract = row
            cache_key = f"{supplier_ico}:{supplier_name}"
            is_np = np_cache.get(cache_key)
            category = classify_title(title)

            c_flags = session.execute(
                select(RiskFlag.flag_code)
                .join(ContractRiskFlag, ContractRiskFlag.flag_id == RiskFlag.id)
                .where(ContractRiskFlag.crz_contract_id == cid)
            ).scalars().all()

            remaining = list(c_flags)
            if is_np and "MISSING_SUPPLIER_ICO" in remaining:
                remaining.remove("MISSING_SUPPLIER_ICO")
            if category == "dohoda o spolupráci" and "MISSING_PRICE" in remaining:
                remaining.remove("MISSING_PRICE")
            if category == "darovacia/dar":
                if "MISSING_PRICE" in remaining:
                    remaining.remove("MISSING_PRICE")
                if "ZERO_PRICE" in remaining:
                    remaining.remove("ZERO_PRICE")
            if category == "vzdelávanie/prax" and "MISSING_PRICE" in remaining:
                remaining.remove("MISSING_PRICE")

            if not remaining:
                contracts_with_only_suppressed_flags.add(cid)

        print(f"Contracts currently in Oznamy:                    {total_flagged:,}")
        print(f"Contracts FULLY cleared by suppression rules:      {len(contracts_with_only_suppressed_flags):,}")
        print(f"Remaining in Oznamy after suppression:             {total_flagged - len(contracts_with_only_suppressed_flags):,}")
        print(f"Reduction:                                         {len(contracts_with_only_suppressed_flags)/total_flagged*100:.1f}%")

        # ── 9. Sample titles from contracts that would be removed ──
        print("\n## 9. SAMPLE TITLES OF CONTRACTS THAT WOULD BE REMOVED\n")

        removed_titles = session.execute(
            select(Contract.title, Contract.supplier_name)
            .where(Contract.crz_contract_id.in_(list(contracts_with_only_suppressed_flags)[:30]))
        ).all()

        for i, (title, supplier) in enumerate(removed_titles[:20], 1):
            t = (title or "(no title)")[:70]
            s = (supplier or "(no supplier)")[:40]
            print(f"  {i:2d}. {t}")
            print(f"      Supplier: {s}")

        # ── 10. Sample titles of contracts that would REMAIN ──
        print("\n## 10. SAMPLE TITLES OF CONTRACTS THAT WOULD REMAIN\n")

        remaining_ids = [
            row[0] for row in flagged_contracts
            if row[0] not in contracts_with_only_suppressed_flags
        ][:30]

        remaining_samples = session.execute(
            select(Contract.title, Contract.supplier_name, Contract.price_total)
            .where(Contract.crz_contract_id.in_(remaining_ids[:20]))
        ).all()

        for i, (title, supplier, price) in enumerate(remaining_samples[:15], 1):
            t = (title or "(no title)")[:60]
            s = (supplier or "(no supplier)")[:30]
            p = f"€{price:,.0f}" if price else "(no price)"
            print(f"  {i:2d}. {t}")
            print(f"      Supplier: {s} | Price: {p}")

        print("\n" + "=" * 80)
        print("END OF REPORT")


if __name__ == "__main__":
    main()
