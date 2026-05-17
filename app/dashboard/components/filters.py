"""Shared filter components for the dashboard sidebar."""

from __future__ import annotations

from datetime import date

import streamlit as st

from app.flags.definitions import FLAG_CATALOG


def date_range_filter(key_prefix: str = "") -> tuple[date | None, date | None]:
    """Date range filter in sidebar. Returns (date_from, date_to)."""
    key = f"{key_prefix}_date_range" if key_prefix else "date_range"
    date_range = st.sidebar.date_input(
        "Obdobie",
        value=[],
        key=key,
        help="Filtruj zmluvy podľa dátumu zverejnenia",
    )
    if len(date_range) == 2:
        return date_range[0], date_range[1]
    elif len(date_range) == 1:
        return date_range[0], None
    return None, None


def severity_filter(key_prefix: str = "") -> str | None:
    """Severity filter in sidebar. Returns selected severity level or None."""
    key = f"{key_prefix}_severity" if key_prefix else "severity"
    options = {
        "Všetky": None,
        "Stredná+ (predvolené)": "medium",
        "Vysoká": "high",
    }
    selection = st.sidebar.selectbox(
        "Závažnosť",
        options=list(options.keys()),
        index=1,
        key=key,
    )
    return options[selection]


def flag_type_filter(key_prefix: str = "") -> str | None:
    """Flag type filter in sidebar. Returns selected flag code or None."""
    key = f"{key_prefix}_flag_type" if key_prefix else "flag_type"
    options = {"Všetky typy": None}
    for code, defn in FLAG_CATALOG.items():
        options[f"{defn.name} ({code})"] = code

    selection = st.sidebar.selectbox(
        "Typ oznamu",
        options=list(options.keys()),
        index=0,
        key=key,
    )
    return options[selection]


def text_search_filter(key_prefix: str = "") -> str | None:
    """Text search input in sidebar."""
    key = f"{key_prefix}_search" if key_prefix else "search"
    value = st.sidebar.text_input(
        "Hľadať",
        placeholder="Názov, dodávateľ, IČO...",
        key=key,
    )
    return value.strip() or None
