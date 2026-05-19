"""Organizácie — Prehľad obstarávateľov."""

import streamlit as st
from sqlalchemy import select

from app.dashboard.components.connection import (
    get_session,
    show_disclaimer,
    show_freshness_banner,
)
from app.dashboard.components.filters import text_search_filter
from app.dashboard.components.queries import get_organizations
from app.db.models import Contract

st.set_page_config(page_title="Organizácie", page_icon="🏛️", layout="wide")

st.title("🏛️ Organizácie — Obstarávatelia")

show_freshness_banner()
show_disclaimer()

# --- Search ---
search_query = text_search_filter(key_prefix="org")

session = get_session()
try:
    with st.spinner("Načítavam organizácie…"):
        organizations = get_organizations(session, search=search_query, limit=100)

    st.subheader(f"Výsledky: {len(organizations)} organizácií")

    org_icos = [org.ico for org in organizations if org.ico]
    contracts_by_ico: dict[str, list] = {}
    if org_icos:
        all_contracts = list(
            session.execute(
                select(Contract)
                .where(Contract.buyer_ico.in_(org_icos))
                .order_by(Contract.publication_date.desc())
            )
            .scalars()
            .all()
        )
        for c in all_contracts:
            lst = contracts_by_ico.setdefault(c.buyer_ico, [])
            if len(lst) < 10:
                lst.append(c)

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
                    contracts = contracts_by_ico.get(org.ico, [])
                    if contracts:
                        st.markdown(f"**Posledné zmluvy ({len(contracts)}):**")
                        for c in contracts:
                            col_x, col_y = st.columns([4, 1])
                            with col_x:
                                st.markdown(
                                    f"**{c.title or 'Bez názvu'}** ({c.contract_date or '?'})"
                                )
                            with col_y:
                                if c.crz_detail_url:
                                    st.link_button("🔗", c.crz_detail_url)
                    else:
                        st.info("Žiadne zmluvy.")
                else:
                    st.info("Bez IČO nie je možné zobraziť súvisiace zmluvy.")
    else:
        st.info("Žiadne organizácie.")
except Exception:
    st.error("❌ Nepodarilo sa načítať dáta. Skúste obnoviť stránku.")
finally:
    session.close()
