"""CSV export helper with embedded disclaimer header."""

from __future__ import annotations

from datetime import UTC, datetime
from io import StringIO

import pandas as pd
import streamlit as st

from app.transforms.entities import is_probable_natural_person


def export_dataframe(df: pd.DataFrame, filename: str) -> None:
    """Export a DataFrame as CSV download with disclaimer header."""
    timestamp = datetime.now(UTC)
    disclaimer = (
        "# CRZ Risk & Quality Monitor — Export dát\n"
        "# Upozornenie: Tento export obsahuje analýzu metadát zmlúv z CRZ.\n"
        "# Označenia nie sú dôkazom protiprávneho konania.\n"
        "# Výsledky slúžia výhradne na informačné účely.\n"
        f"# Exportované: {timestamp.strftime('%Y-%m-%d %H:%M UTC')}\n"
    )

    csv_buffer = StringIO()
    csv_buffer.write(disclaimer)
    df.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()

    full_filename = f"{filename}_{timestamp.strftime('%Y%m%d_%H%M%S')}.csv"

    st.download_button(
        label="📥 Stiahnuť CSV",
        data=csv_data,
        file_name=full_filename,
        mime="text/csv",
    )


def contracts_to_dataframe(contracts_data: list[dict]) -> pd.DataFrame:
    """Convert flagged contract data to a DataFrame for export.

    Args:
        contracts_data: List of dicts with 'contract', 'flags', 'flag_count', 'compound_severity'

    Returns:
        DataFrame ready for CSV export.
    """
    rows = []
    for item in contracts_data:
        c = item["contract"]
        flag_names = ", ".join(f["name"] for f in item["flags"])

        supplier_name = c.supplier_name or ""
        supplier_ico = c.supplier_ico or ""

        if is_probable_natural_person(supplier_name, supplier_ico):
            supplier_name = "[fyzická osoba]"
            supplier_ico = ""

        rows.append(
            {
                "ID zmluvy": c.crz_contract_id,
                "Názov": c.title or "",
                "Obstarávateľ": c.buyer_name or "",
                "IČO obstarávateľa": c.buyer_ico or "",
                "Dodávateľ": supplier_name,
                "IČO dodávateľa": supplier_ico,
                "Cena celková": str(c.price_total) if c.price_total is not None else "",
                "Dátum zmluvy": str(c.contract_date) if c.contract_date else "",
                "Zverejnené": str(c.publication_date) if c.publication_date else "",
                "Počet oznamov": item["flag_count"],
                "Závažnosť": item["compound_severity"],
                "Oznamy": flag_names,
                "Odkaz CRZ": c.crz_detail_url or "",
            }
        )
    return pd.DataFrame(rows)
