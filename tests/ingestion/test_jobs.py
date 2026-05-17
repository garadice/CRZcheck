from __future__ import annotations

import io
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.ingestion.jobs import get_date_range, process_export
from app.settings import settings


class TestGetDateRange:
    def test_default_range_length(self):
        dates = get_date_range(end_date=date(2026, 5, 14))
        assert len(dates) == 90

    def test_range_order(self):
        dates = get_date_range(end_date=date(2026, 5, 14))
        assert dates[0] == date(2026, 2, 14)
        assert dates[-1] == date(2026, 5, 14)

    def test_single_day(self):
        dates = get_date_range(end_date=date(2026, 1, 1))
        assert len(dates) == 90

    def test_default_end_is_today(self):
        dates = get_date_range()
        assert dates[-1] == date.today()

    def test_custom_end_date(self):
        dates = get_date_range(end_date=date(2026, 5, 17))
        assert dates[-1] == date(2026, 5, 17)

    def test_window_size_matches_settings(self):
        dates = get_date_range(end_date=date(2026, 5, 17))
        assert len(dates) == settings.crz_rolling_window_days

    def test_start_date_is_end_minus_window_plus_one(self):
        end = date(2026, 5, 17)
        dates = get_date_range(end_date=end)
        expected_start = end - timedelta(days=settings.crz_rolling_window_days - 1)
        assert dates[0] == expected_start


class TestProcessExport:
    def test_process_sample_fixture(self):
        fixture = Path("tests/fixtures/xml/sample.xml")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.write(fixture, "2026-05-14.xml")
        buf.seek(0)

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(buf.read())
            tmp_path = Path(tmp.name)

        try:
            result = process_export(tmp_path, date(2026, 5, 14))
            assert len(result.contracts) == 5
            assert result.export_date == "2026-05-14"
        finally:
            tmp_path.unlink()

    def test_process_export_valid_zip(self, tmp_path):
        fixture = Path("tests/fixtures/xml/sample.xml")
        zip_path = tmp_path / "2026-05-14.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(fixture, "2026-05-14.xml")
        result = process_export(zip_path, date(2026, 5, 14))
        assert result.contracts
        assert len(result.contracts) == 5

    def test_process_export_empty_zip(self, tmp_path):
        zip_path = tmp_path / "empty.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("readme.txt", "no xml here")
        with pytest.raises(ValueError, match="No XML file found"):
            process_export(zip_path, date(2026, 5, 14))
