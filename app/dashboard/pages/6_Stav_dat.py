"""Stav dát — Informácie o stave a aktuálnosti dát."""

import streamlit as st

from app.dashboard.components.connection import (
    get_session,
    show_disclaimer,
    show_freshness_banner,
)
from app.dashboard.components.queries import (
    get_ingestion_history,
    get_overview_stats,
)

st.set_page_config(page_title="Stav dát", page_icon="📊", layout="wide")

st.title("📊 Stav dát")

show_freshness_banner()
show_disclaimer()

session = get_session()
try:
    # --- Overview stats ---
    stats = get_overview_stats(session)

    st.header("Štatistiky")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Zmluvy celkom", f"{stats['total_contracts']:,}")
    col2.metric("Označené zmluvy", f"{stats['total_flagged']:,}")
    col3.metric("Organizácie", f"{stats['total_organizations']:,}")
    col4.metric("Dodávatelia", f"{stats['total_suppliers']:,}")

    if stats["total_contracts"] > 0:
        flag_pct = (stats["total_flagged"] / stats["total_contracts"]) * 100
        st.metric("Podiel označených", f"{flag_pct:.1f} %")

    # --- Data freshness ---
    st.divider()
    st.header("Aktuálnosť dát")

    from app.flags.freshness import check_data_freshness

    freshness = check_data_freshness(session)

    if freshness["status"] == "fresh":
        st.success(
            f"✅ Dáta sú aktuálne. Posledná ingestia: "
            f"**{freshness['last_success'].strftime('%Y-%m-%d %H:%M UTC')}** "
            f"(pred {freshness['hours_since']}h)"
        )
    elif freshness["status"] == "stale":
        st.error(
            f"🔴 **{freshness['warning']}**\n\n"
            f"Posledná ingestia: {freshness['last_success'].strftime('%Y-%m-%d %H:%M UTC')}"
        )
    else:
        st.warning("⚠️ Zatiaľ neboli načítané žiadne dáta.")

    # --- Ingestion history ---
    st.divider()
    st.header("História ingestií")

    runs = get_ingestion_history(session, limit=20)
    if runs:
        for run in runs:
            status_emoji = {
                "completed": "✅",
                "running": "🔄",
                "failed": "❌",
            }.get(run.status, "❓")

            col_a, col_b, col_c = st.columns([1, 2, 1])
            with col_a:
                st.markdown(f"{status_emoji} **{run.status}**")
            with col_b:
                st.markdown(
                    f"{run.started_at.strftime('%Y-%m-%d %H:%M')} → "
                    f"{run.finished_at.strftime('%H:%M') if run.finished_at else '...'}"
                )
            with col_c:
                st.markdown(
                    f"{run.records_seen} zmlúv "
                    f"({run.records_inserted} nových, {run.records_updated} aktualizovaných)"
                )
            if run.error_message:
                st.error(f"Chyba: {run.error_message}")
    else:
        st.info("Žiadne záznamy o ingestii.")
finally:
    session.close()
