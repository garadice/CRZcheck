from __future__ import annotations

import io
import tempfile
import zipfile
from datetime import date
from pathlib import Path

from app.ingestion.jobs import get_date_range, process_export


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
