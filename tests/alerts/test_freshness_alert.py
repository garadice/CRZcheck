"""Tests for the freshness alert module."""

import contextlib
from unittest.mock import MagicMock, patch

import pytest

from app.alerts.freshness_alert import check_and_alert, main


class TestCheckAndAlert:
    """Tests for check_and_alert()."""

    @patch("app.alerts.freshness_alert.get_session_factory")
    def test_returns_false_when_fresh(self, mock_factory):
        """Fresh data should return False (no alert)."""
        mock_session = MagicMock()
        mock_factory.return_value.return_value = mock_session

        with patch("app.alerts.freshness_alert.check_data_freshness") as mock_check:
            mock_check.return_value = {
                "status": "fresh",
                "hours_since": 2.0,
                "records_seen": 5000,
            }
            result = check_and_alert()

        assert result is False
        mock_session.close.assert_called_once()

    @patch("app.alerts.freshness_alert.get_session_factory")
    def test_returns_true_when_stale(self, mock_factory):
        """Stale data should return True (alert)."""
        mock_session = MagicMock()
        mock_factory.return_value.return_value = mock_session

        with patch("app.alerts.freshness_alert.check_data_freshness") as mock_check:
            mock_check.return_value = {
                "status": "stale",
                "warning": "Posledná úspešná ingestia bola pred 50 hodinami.",
            }
            result = check_and_alert()

        assert result is True
        mock_session.close.assert_called_once()

    @patch("app.alerts.freshness_alert.get_session_factory")
    def test_returns_true_when_no_data(self, mock_factory):
        """No data should return True (alert)."""
        mock_session = MagicMock()
        mock_factory.return_value.return_value = mock_session

        with patch("app.alerts.freshness_alert.check_data_freshness") as mock_check:
            mock_check.return_value = {
                "status": "no_data",
                "warning": "Zatiaľ nebola zaznamenaná žiadna úspešná ingestia.",
            }
            result = check_and_alert()

        assert result is True
        mock_session.close.assert_called_once()

    @patch("app.alerts.freshness_alert.get_session_factory")
    def test_session_closed_on_exception(self, mock_factory):
        """Session should be closed even if check raises."""
        mock_session = MagicMock()
        mock_factory.return_value.return_value = mock_session

        with patch("app.alerts.freshness_alert.check_data_freshness") as mock_check:
            mock_check.side_effect = RuntimeError("DB down")
            with contextlib.suppress(RuntimeError):
                check_and_alert()

        mock_session.close.assert_called_once()


class TestMain:
    """Tests for the main() CLI entry point."""

    @patch("app.alerts.freshness_alert.check_and_alert", return_value=False)
    def test_exits_0_when_fresh(self, mock_alert):
        """main() should exit 0 when data is fresh."""
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    @patch("app.alerts.freshness_alert.check_and_alert", return_value=True)
    def test_exits_1_when_stale(self, mock_alert):
        """main() should exit 1 when data is stale."""
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    @patch("app.alerts.freshness_alert.check_and_alert", side_effect=RuntimeError("DB unreachable"))
    def test_exits_2_on_unexpected_error(self, mock_alert):
        """main() should exit 2 on unexpected exceptions."""
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2

    @patch(
        "app.alerts.freshness_alert.check_and_alert",
        side_effect=ConnectionError("network down"),
    )
    def test_exits_2_on_connection_error(self, mock_alert):
        """main() should exit 2 for connection errors too."""
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2
