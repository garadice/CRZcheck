"""Detail zmluvy — Úplné informácie o zmluve."""

import streamlit as st

from app.dashboard.components.connection import (
    get_session,
    show_disclaimer,
    show_freshness_banner,
)
from app.dashboard.components.queries import (
    get_contract_attachments,
    get_contract_detail,
    get_contract_flags,
)

st.set_page_config(page_title="Detail zmluvy", page_icon="📄", layout="wide")

st.title("📄 Detail zmluvy")

show_freshness_banner()
show_disclaimer()

# --- Contract lookup ---
contract_id = st.text_input(
    "Zadajte ID zmluvy:",
    placeholder="napr. 123456",
    key="detail_contract_id",
)

session = get_session()
try:
    if contract_id:
        contract = get_contract_detail(session, contract_id)

        if contract is None:
            st.error(f"Zmluva s ID **{contract_id}** nebola nájdená.")
        else:
            # Header
            st.header(contract.title or "Bez názvu")

            # CRZ link
            if contract.crz_detail_url:
                st.link_button("🔗 Otvoriť v CRZ", contract.crz_detail_url)

            st.caption("⚠️ Údaje môžu obsahovať osobné informácie.")

            # Main info
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Informácie o zmluve")
                st.markdown(f"**ID:** {contract.crz_contract_id}")
                st.markdown(f"**Predmet:** {contract.subject or '—'}")
                st.markdown(f"**Dátum zmluvy:** {contract.contract_date or '—'}")
                st.markdown(f"**Zverejnené:** {contract.publication_date or '—'}")
                st.markdown(f"**Platnosť od:** {contract.effective_date or '—'}")
                st.markdown(f"**Platnosť do:** {contract.valid_until or '—'}")
                if contract.price_total is not None:
                    st.markdown(
                        f"**Cena celková:** {contract.price_total:,.2f} {contract.currency}"
                    )
                if contract.price_contract is not None:
                    st.markdown(
                        f"**Cena zmluvná:** {contract.price_contract:,.2f} {contract.currency}"
                    )

            with col2:
                st.subheader("Strany zmluvy")
                st.markdown(f"**Obstarávateľ:** {contract.buyer_name or '—'}")
                st.markdown(f"**IČO:** {contract.buyer_ico or '—'}")
                st.markdown(f"**Adresa:** {contract.buyer_address or '—'}")
                st.divider()
                st.markdown(f"**Dodávateľ:** {contract.supplier_name or '—'}")
                st.markdown(f"**IČO:** {contract.supplier_ico or '—'}")
                st.markdown(f"**Adresa:** {contract.supplier_address or '—'}")

            # Flags
            st.divider()
            flags = get_contract_flags(session, contract.crz_contract_id)
            if flags:
                st.subheader(f"🚩 Oznamy ({len(flags)})")
                for flag in flags:
                    sev_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                        flag["severity"], "⚪"
                    )
                    st.markdown(f"{sev_emoji} **{flag['name']}** ({flag['severity']})")
                    st.caption(flag.get("reason", ""))
            else:
                st.success("✅ Žiadne oznamy — zmluva vyzerá v poriadku.")

            # Attachments
            attachments = get_contract_attachments(session, contract.crz_contract_id)
            if attachments:
                st.divider()
                st.subheader(f"📎 Prílohy ({len(attachments)})")
                for att in attachments:
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.markdown(f"**{att.attachment_name or 'Príloha'}**")
                        if att.scan_filename:
                            st.caption(f"Sken: {att.scan_filename}")
                        if att.text_filename:
                            st.caption(f"Text: {att.text_filename}")
                    with col_b:
                        if att.scan_source_url:
                            st.link_button("📎 Príloha", att.scan_source_url)
    else:
        st.info("Zadajte ID zmluvy pre zobrazenie detailu.")
finally:
    session.close()
