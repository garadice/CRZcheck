"""Tests for app.dashboard.components.connection — engine, session, disclaimer, freshness."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.dashboard.components import connection as conn_module

# ── TestGetEngine ─────────────────────────────────────────────────────────────


class TestGetEngine:
    @patch("app.dashboard.components.connection.create_engine")
    @patch("app.dashboard.components.connection.settings")
    def test_returns_engine_with_correct_url(self, mock_settings, mock_create_engine):
        mock_settings.database_url = "postgresql://user:pass@localhost/test"
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        engine = conn_module.get_engine()

        mock_create_engine.assert_called_once()
        call_args = mock_create_engine.call_args
        assert call_args[0][0] == "postgresql://user:pass@localhost/test"
        assert call_args[1]["pool_size"] == 5
        assert call_args[1]["max_overflow"] == 10
        assert call_args[1]["pool_pre_ping"] is True
        assert call_args[1]["pool_recycle"] == 300
        assert engine is mock_engine


class TestGetSession:
    @patch("app.dashboard.components.connection._get_session_factory")
    def test_returns_session_from_factory(self, mock_factory_fn):
        mock_session = MagicMock()
        mock_factory = MagicMock(return_value=mock_session)
        mock_factory_fn.return_value = mock_factory

        session = conn_module.get_session()

        mock_factory.assert_called_once()
        assert session is mock_session


class TestShowDisclaimer:
    @patch("app.dashboard.components.connection.st")
    def test_calls_st_warning(self, mock_st):
        conn_module.show_disclaimer()
        mock_st.warning.assert_called_once()
        call_args = mock_st.warning.call_args
        assert "Upozornenie" in call_args[0][0]
        assert call_args[1]["icon"] == "⚠️"


class TestShowFreshnessBanner:
    """Freshness banner tests.

    check_data_freshness is imported locally inside show_freshness_banner(),
    so we patch it at the source module: app.flags.freshness.check_data_freshness
    """

    @patch("app.dashboard.components.connection.st")
    @patch("app.dashboard.components.connection.get_session")
    @patch("app.flags.freshness.check_data_freshness")
    def test_stale_status_shows_error(self, mock_check, mock_get_session, mock_st):
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_check.return_value = {
            "status": "stale",
            "warning": "Dáta sú neaktuálne",
        }

        conn_module.show_freshness_banner()

        mock_st.error.assert_called_once()
        assert "Dáta sú neaktuálne" in mock_st.error.call_args[0][0]
        mock_session.close.assert_called_once()

    @patch("app.dashboard.components.connection.st")
    @patch("app.dashboard.components.connection.get_session")
    @patch("app.flags.freshness.check_data_freshness")
    def test_no_data_status_shows_info(self, mock_check, mock_get_session, mock_st):
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_check.return_value = {
            "status": "no_data",
            "warning": "Žiadne dáta",
        }

        conn_module.show_freshness_banner()

        mock_st.info.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("app.dashboard.components.connection.st")
    @patch("app.dashboard.components.connection.get_session")
    @patch("app.flags.freshness.check_data_freshness")
    def test_fresh_status_no_banner(self, mock_check, mock_get_session, mock_st):
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_check.return_value = {
            "status": "fresh",
            "hours_since": 1.0,
            "records_seen": 100,
        }

        conn_module.show_freshness_banner()

        mock_st.error.assert_not_called()
        mock_st.info.assert_not_called()
        mock_session.close.assert_called_once()

    @patch("app.dashboard.components.connection.st")
    @patch("app.dashboard.components.connection.get_session")
    @patch("app.flags.freshness.check_data_freshness")
    def test_stores_freshness_in_session_state(self, mock_check, mock_get_session, mock_st):
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        freshness_data = {"status": "fresh", "hours_since": 1.0}
        mock_check.return_value = freshness_data
        mock_st.session_state = {}

        conn_module.show_freshness_banner()

        assert mock_st.session_state["_freshness_result"] == freshness_data

    @patch("app.dashboard.components.connection.logger")
    @patch("app.dashboard.components.connection.get_session")
    def test_exception_does_not_crash(self, mock_get_session, mock_logger):
        """Freshness check failure should be caught and logged, not crash."""
        mock_get_session.side_effect = Exception("DB connection failed")

        # Should not raise
        conn_module.show_freshness_banner()

        mock_logger.warning.assert_called_once()
