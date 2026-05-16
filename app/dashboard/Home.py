"""CRZ Risk & Quality Monitor — Domovská stránka."""

import streamlit as st

from app.dashboard.components.connection import (
    get_session,
    show_disclaimer,
    show_freshness_banner,
)
from app.dashboard.components.filters import date_range_filter, text_search_filter
from app.dashboard.components.queries import get_overview_stats, search_contracts

st.set_page_config(
    page_title="CRZ Monitor",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔍 CRZ Risk & Quality Monitor")
st.caption("Analýza kvality metadát zmlúv z Centrálneho registra zmlúv")

show_freshness_banner()
show_disclaimer()

# --- Overview Stats ---
session = get_session()
try:
    stats = get_overview_stats(session)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Zmluvy celkom", f"{stats['total_contracts']:,}")
    col2.metric("Označené zmluvy", f"{stats['total_flagged']:,}")
    col3.metric("Organizácie", f"{stats['total_organizations']:,}")
    col4.metric("Dodávatelia", f"{stats['total_suppliers']:,}")

    if stats["total_value"] > 0:
        st.info(f"💰 Celková hodnota zmlúv: **{stats['total_value']:,.2f} EUR**")

    st.divider()

    # --- Search ---
    st.subheader("🔎 Vyhľadávanie zmlúv")
    date_from, date_to = date_range_filter(key_prefix="home")
    search_query = text_search_filter(key_prefix="home")

    if search_query or date_from or date_to:
        results = search_contracts(
            session,
            query=search_query,
            date_from=date_from,
            date_to=date_to,
            limit=50,
        )
        if results:
            st.success(f"Nájdených **{len(results)}** zmlúv")
            for c in results[:20]:
                with st.container():
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.markdown(f"**{c.title or 'Bez názvu'}**")
                        price_str = f"{c.price_total:,} EUR" if c.price_total else "—"
                        st.caption(
                            f"{c.buyer_name or '?'} → {c.supplier_name or '?'}"
                            f" | {c.contract_date or '?'}"
                            f" | {price_str}"
                        )
                    with col_b:
                        if c.crz_detail_url:
                            st.link_button("Otvoriť v CRZ", c.crz_detail_url)
                    st.divider()
        else:
            st.warning("Žiadne výsledky.")
finally:
    session.close()
