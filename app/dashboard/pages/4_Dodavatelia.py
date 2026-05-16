"""Dodávatelia — Prehľad dodávateľov (fyzické osoby skryté)."""

import streamlit as st

from app.dashboard.components.connection import (
    get_session,
    show_disclaimer,
    show_freshness_banner,
)
from app.dashboard.components.filters import text_search_filter
from app.dashboard.components.queries import get_supplier_contracts, get_suppliers

st.set_page_config(page_title="Dodávatelia", page_icon="🏢", layout="wide")

st.title("🏢 Dodávatelia")

show_freshness_banner()
show_disclaimer()

# --- Search & natural person toggle ---
search_query = text_search_filter(key_prefix="supplier")
show_np = st.sidebar.checkbox(
    "Zobraziť fyzické osoby",
    value=False,
    key="show_natural_persons",
    help="Predvolene sú profily fyzických osôb skryté",
)

session = get_session()
try:
    suppliers = get_suppliers(
        session,
        search=search_query,
        show_natural_persons=show_np,
        limit=100,
    )

    st.subheader(f"Výsledky: {len(suppliers)} dodávateľov")

    if suppliers:
        for sup in suppliers:
            np_tag = " 👤 (pravdepodobne fyzická osoba)" if sup.is_probable_natural_person else ""
            with st.expander(
                f"**{sup.display_name or 'Neznámy dodávateľ'}** (IČO: {sup.ico or '—'}){np_tag}"
            ):
                st.markdown(f"**Adresa:** {sup.address or '—'}")
                first_seen = sup.first_seen_at.strftime("%Y-%m-%d") if sup.first_seen_at else "—"
                st.markdown(f"**Prvý výskyt:** {first_seen}")
                last_seen = sup.last_seen_at.strftime("%Y-%m-%d") if sup.last_seen_at else "—"
                st.markdown(f"**Posledný výskyt:** {last_seen}")

                if sup.ico:
                    contracts = get_supplier_contracts(session, sup.ico, limit=10)
                    if contracts:
                        st.markdown(f"**Posledné zmluvy ({len(contracts)}):**")
                        for c in contracts:
                            st.markdown(
                                f"- {c.title or 'Bez názvu'} ({c.contract_date or '?'}) — "
                                f"{c.buyer_name or '?'}"
                            )
                    else:
                        st.info("Žiadne zmluvy.")
    else:
        st.info("Žiadni dodávatelia.")
finally:
    session.close()
