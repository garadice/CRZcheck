"""Tests for app.dashboard.components.filters — sidebar filter components."""

from __future__ import annotations

import sys
from datetime import date
from unittest.mock import MagicMock, patch

from app.flags.definitions import FLAG_CATALOG

# ── Streamlit mock ────────────────────────────────────────────────────────────

if "streamlit" not in sys.modules:
    _st_mock = MagicMock()
    sys.modules["streamlit"] = _st_mock

import streamlit as st

from app.dashboard.components import filters as filters_module

# ── TestDateRangeFilter ───────────────────────────────────────────────────────


class TestDateRangeFilter:
    @patch.object(st, "sidebar")
    def test_empty_range_returns_none_none(self, mock_sidebar):
        mock_sidebar.date_input.return_value = []
        result = filters_module.date_range_filter()
        assert result == (None, None)

    @patch.object(st, "sidebar")
    def test_single_date_returns_date_none(self, mock_sidebar):
        d = date(2026, 5, 14)
        mock_sidebar.date_input.return_value = [d]
        result = filters_module.date_range_filter()
        assert result == (d, None)

    @patch.object(st, "sidebar")
    def test_two_dates_returns_tuple(self, mock_sidebar):
        d1 = date(2026, 1, 1)
        d2 = date(2026, 5, 14)
        mock_sidebar.date_input.return_value = [d1, d2]
        result = filters_module.date_range_filter()
        assert result == (d1, d2)

    @patch.object(st, "sidebar")
    def test_key_without_prefix(self, mock_sidebar):
        mock_sidebar.date_input.return_value = []
        filters_module.date_range_filter()
        call_kwargs = mock_sidebar.date_input.call_args
        assert call_kwargs[1]["key"] == "date_range"

    @patch.object(st, "sidebar")
    def test_key_with_prefix(self, mock_sidebar):
        mock_sidebar.date_input.return_value = []
        filters_module.date_range_filter(key_prefix="contracts")
        call_kwargs = mock_sidebar.date_input.call_args
        assert call_kwargs[1]["key"] == "contracts_date_range"


# ── TestSeverityFilter ────────────────────────────────────────────────────────


class TestSeverityFilter:
    @patch.object(st, "sidebar")
    def test_default_returns_medium(self, mock_sidebar):
        # Default index=1 → "Stredná+ (predvolené)" → "medium"
        mock_sidebar.selectbox.return_value = "Stredná+ (predvolené)"
        result = filters_module.severity_filter()
        assert result == "medium"

    @patch.object(st, "sidebar")
    def test_all_returns_none(self, mock_sidebar):
        mock_sidebar.selectbox.return_value = "Všetky"
        result = filters_module.severity_filter()
        assert result is None

    @patch.object(st, "sidebar")
    def test_high_returns_high(self, mock_sidebar):
        mock_sidebar.selectbox.return_value = "Vysoká"
        result = filters_module.severity_filter()
        assert result == "high"

    @patch.object(st, "sidebar")
    def test_key_with_prefix(self, mock_sidebar):
        mock_sidebar.selectbox.return_value = "Všetky"
        filters_module.severity_filter(key_prefix="test")
        call_kwargs = mock_sidebar.selectbox.call_args
        assert call_kwargs[1]["key"] == "test_severity"

    @patch.object(st, "sidebar")
    def test_options_include_all_choices(self, mock_sidebar):
        mock_sidebar.selectbox.return_value = "Všetky"
        filters_module.severity_filter()
        call_args = mock_sidebar.selectbox.call_args
        options = call_args[1]["options"]
        assert "Všetky" in options
        assert "Stredná+ (predvolené)" in options
        assert "Vysoká" in options


# ── TestFlagTypeFilter ────────────────────────────────────────────────────────


class TestFlagTypeFilter:
    @patch.object(st, "sidebar")
    def test_all_types_returns_none(self, mock_sidebar):
        mock_sidebar.selectbox.return_value = "Všetky typy"
        result = filters_module.flag_type_filter()
        assert result is None

    @patch.object(st, "sidebar")
    def test_specific_flag_returns_code(self, mock_sidebar):
        # Pick a known flag from the catalog
        first_code = list(FLAG_CATALOG.keys())[0]
        first_name = FLAG_CATALOG[first_code].name
        selection_label = f"{first_name} ({first_code})"
        mock_sidebar.selectbox.return_value = selection_label

        result = filters_module.flag_type_filter()
        assert result == first_code

    @patch.object(st, "sidebar")
    def test_options_include_all_flags(self, mock_sidebar):
        mock_sidebar.selectbox.return_value = "Všetky typy"
        filters_module.flag_type_filter()
        call_args = mock_sidebar.selectbox.call_args
        options = call_args[1]["options"]

        # Should start with "Všetky typy"
        assert options[0] == "Všetky typy"

        # Should include each flag from catalog
        for code, defn in FLAG_CATALOG.items():
            expected_label = f"{defn.name} ({code})"
            assert expected_label in options

    @patch.object(st, "sidebar")
    def test_key_with_prefix(self, mock_sidebar):
        mock_sidebar.selectbox.return_value = "Všetky typy"
        filters_module.flag_type_filter(key_prefix="page")
        call_kwargs = mock_sidebar.selectbox.call_args
        assert call_kwargs[1]["key"] == "page_flag_type"


# ── TestTextSearchFilter ──────────────────────────────────────────────────────


class TestTextSearchFilter:
    @patch.object(st, "sidebar")
    def test_empty_string_returns_none(self, mock_sidebar):
        mock_sidebar.text_input.return_value = ""
        result = filters_module.text_search_filter()
        assert result is None

    @patch.object(st, "sidebar")
    def test_whitespace_only_returns_none(self, mock_sidebar):
        mock_sidebar.text_input.return_value = "   "
        result = filters_module.text_search_filter()
        assert result is None

    @patch.object(st, "sidebar")
    def test_text_returned_stripped(self, mock_sidebar):
        mock_sidebar.text_input.return_value = "  hello world  "
        result = filters_module.text_search_filter()
        assert result == "hello world"

    @patch.object(st, "sidebar")
    def test_normal_text_returned(self, mock_sidebar):
        mock_sidebar.text_input.return_value = "supplier name"
        result = filters_module.text_search_filter()
        assert result == "supplier name"

    @patch.object(st, "sidebar")
    def test_key_without_prefix(self, mock_sidebar):
        mock_sidebar.text_input.return_value = ""
        filters_module.text_search_filter()
        call_kwargs = mock_sidebar.text_input.call_args
        assert call_kwargs[1]["key"] == "search"

    @patch.object(st, "sidebar")
    def test_key_with_prefix(self, mock_sidebar):
        mock_sidebar.text_input.return_value = ""
        filters_module.text_search_filter(key_prefix="org")
        call_kwargs = mock_sidebar.text_input.call_args
        assert call_kwargs[1]["key"] == "org_search"

    @patch.object(st, "sidebar")
    def test_unicode_text(self, mock_sidebar):
        mock_sidebar.text_input.return_value = "Ministerstvo financií"
        result = filters_module.text_search_filter()
        assert result == "Ministerstvo financií"
