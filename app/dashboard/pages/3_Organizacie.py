"""Organizácie — Prehľad obstarávateľov."""

import streamlit as st

from app.dashboard.components.connection import (
    get_session,
    show_disclaimer,
    show_freshness_banner,
)
from app.dashboard.components.filters import text_search_filter
from app.dashboard.components.queries import get_organization_contracts, get_organizations

st.set_page_config(page_title="Organizácie", page_icon="🏛️", layout="wide")

st.title("🏛️ Organizácie — Obstarávatelia")

show_freshness_banner()
show_disclaimer()

# --- Search ---
search_query = text_search_filter(key_prefix="org")

session = get_session()
try:
    organizations = get_organizations(session, search=search_query, limit=100)

    st.subheader(f"Výsledky: {len(organizations)} organizácií")

    if organizations:
        for org in organizations:
            with st.expander(
                f"**{org.display_name or 'Neznáma organizácia'}** (IČO: {org.ico or '—'})"
            ):
                st.markdown(f"**Adresa:** {org.address or '—'}")
                first_seen = org.first_seen_at.strftime("%Y-%m-%d") if org.first_seen_at else "—"
                st.markdown(f"**Prvý výskyt:** {first_seen}")
                last_seen = org.last_seen_at.strftime("%Y-%m-%d") if org.last_seen_at else "—"
                st.markdown(f"**Posledný výskyt:** {last_seen}")

                if org.ico:
                    contracts = get_organization_contracts(session, org.ico, limit=10)
                    if contracts:
                        st.markdown(f"**Posledné zmluvy ({len(contracts)}):**")
                        for c in contracts:
                            st.markdown(
                                f"- {c.title or 'Bez názvu'} ({c.contract_date or '?'}) — "
                                f"{c.supplier_name or '?'}"
                            )
                    else:
                        st.info("Žiadne zmluvy.")
    else:
        st.info("Žiadne organizácie.")
finally:
    session.close()
