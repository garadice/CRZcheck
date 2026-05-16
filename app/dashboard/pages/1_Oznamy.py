"""Oznamy — Prehľad označených zmlúv."""

import streamlit as st

from app.dashboard.components.connection import (
    get_session,
    show_disclaimer,
    show_freshness_banner,
)
from app.dashboard.components.export import contracts_to_dataframe, export_dataframe
from app.dashboard.components.filters import date_range_filter, flag_type_filter, severity_filter
from app.dashboard.components.queries import get_flagged_contracts

st.set_page_config(page_title="Oznamy", page_icon="🚩", layout="wide")

st.title("🚩 Oznamy — Označené zmluvy")

show_freshness_banner()

# --- Sidebar filters ---
st.sidebar.header("Filtre")
severity = severity_filter(key_prefix="oznamy")
flag_code = flag_type_filter(key_prefix="oznamy")
date_from, date_to = date_range_filter(key_prefix="oznamy")

show_disclaimer()

# --- Load data ---
session = get_session()
try:
    results = get_flagged_contracts(
        session,
        severity_filter=severity,
        flag_code_filter=flag_code,
        date_from=date_from,
        date_to=date_to,
        limit=200,
    )

    st.subheader(f"Výsledky: {len(results)} zmlúv")

    if results:
        # CSV export
        df = contracts_to_dataframe(results)
        export_dataframe(df, "crz_oznamy")

        st.divider()

        # Display results
        for item in results:
            contract = item["contract"]
            sev = item["compound_severity"]
            flag_count = item["flag_count"]

            # Severity color
            sev_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
            sev_label = {"high": "vysoká", "medium": "stredná", "low": "nízka"}.get(sev, "žiadna")

            with st.container():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(
                        f"**{sev_emoji} {contract.title or 'Bez názvu'}** "
                        f"({flag_count} oznamov, závažnosť: {sev_label})"
                    )
                    st.caption(
                        f"ID: {contract.crz_contract_id} | "
                        f"{contract.buyer_name or '?'} → {contract.supplier_name or '?'} | "
                        f"{contract.contract_date or '?'}"
                    )
                    # Show flag names
                    flag_names = ", ".join(f["name"] for f in item["flags"])
                    st.markdown(f"*{flag_names}*")
                with col2:
                    if contract.crz_detail_url:
                        st.link_button("🔗 CRZ", contract.crz_detail_url)
                st.divider()
    else:
        st.info("Žiadne označené zmluvy pre zvolené filtre.")
finally:
    session.close()
