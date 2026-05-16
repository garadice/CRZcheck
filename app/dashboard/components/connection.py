"""Streamlit connection pooling with cached engine."""

from __future__ import annotations

import streamlit as st
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.settings import settings


@st.cache_resource
def get_engine() -> Engine:
    """Get or create a cached SQLAlchemy engine for Streamlit."""
    return create_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=300,
    )


@st.cache_resource
def _get_session_factory() -> sessionmaker:
    """Cached session factory bound to the cached engine."""
    return sessionmaker(bind=get_engine())


def get_session() -> Session:
    """Create a new session from the cached factory."""
    return _get_session_factory()()


DISCLAIMER_TEXT = (
    "⚠️ **Upozornenie:** Tento nástroj analyzuje metadáta zmlúv z CRZ na základe "
    "kvality a úplnosti údajov. Označenia nie sú dôkazom protiprávneho konania. "
    "Výsledky slúžia výhradne na informačné účely a nepredstavujú právne ani "
    "finančné hodnotenie zmlúv alebo zúčastnených strán."
)


def show_disclaimer():
    """Show the standard disclaimer banner."""
    st.warning(DISCLAIMER_TEXT, icon="⚠️")


def show_freshness_banner():
    """Show data freshness warning banner if data is stale."""
    from app.flags.freshness import check_data_freshness

    session = get_session()
    try:
        freshness = check_data_freshness(session)
        if freshness["status"] == "stale":
            st.error(
                f"🔴 **{freshness['warning']}**",
                icon="🔴",
            )
        elif freshness["status"] == "no_data":
            st.info(
                "ℹ️ Zatiaľ neboli načítané žiadne dáta. Spustite ingestiu.",
                icon="ℹ️",
            )
    finally:
        session.close()
