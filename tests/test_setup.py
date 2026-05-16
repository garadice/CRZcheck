"""Smoke tests for project setup."""


def test_settings_import():
    """Test that settings can be imported."""
    from app.settings import settings

    assert settings.app_env == "development"
    assert settings.crz_export_base_url == "https://www.crz.gov.sk/export"


def test_rolling_window_default():
    """Test default rolling window."""
    from app.settings import settings

    assert settings.crz_rolling_window_days == 90
