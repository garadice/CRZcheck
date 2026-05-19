"""Dodávatelia — Prehľad dodávateľov (fyzické osoby skryté)."""

import streamlit as st
from sqlalchemy import select

from app.dashboard.components.connection import (
    get_session,
    show_disclaimer,
    show_freshness_banner,
)
from app.dashboard.components.filters import text_search_filter
from app.dashboard.components.queries import get_suppliers
from app.db.models import Contract

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
    with st.spinner("Načítavam dodávateľov…"):
        suppliers = get_suppliers(
            session,
            search=search_query,
            show_natural_persons=show_np,
            limit=100,
        )

    st.subheader(f"Výsledky: {len(suppliers)} dodávateľov")

    sup_icos = [sup.ico for sup in suppliers if sup.ico]
    contracts_by_ico: dict[str, list] = {}
    if sup_icos:
        all_contracts = list(
            session.execute(
                select(Contract)
                .where(Contract.supplier_ico.in_(sup_icos))
                .order_by(Contract.publication_date.desc())
            )
            .scalars()
            .all()
        )
        for c in all_contracts:
            lst = contracts_by_ico.setdefault(c.supplier_ico, [])
            if len(lst) < 10:
                lst.append(c)

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
                    contracts = contracts_by_ico.get(sup.ico, [])
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
        st.info("Žiadni dodávatelia.")
except Exception:
    st.error("❌ Nepodarilo sa načítať dáta. Skúste obnoviť stránku.")
finally:
    session.close()
