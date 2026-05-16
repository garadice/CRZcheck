from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.ingestion.crz.download import CRZDownloader


class TestCRZDownloader:
    def test_download_export_success(self, tmp_path):
        downloader = CRZDownloader()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake zip content"
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(downloader.client, "get", return_value=mock_response),
            patch.object(downloader, "_wait_for_rate_limit"),
            patch("app.ingestion.crz.download.settings") as mock_settings,
        ):
            mock_settings.raw_data_dir = tmp_path / "raw"
            result = downloader.download_export("2026-05-14")

        assert result.exists()
        assert result.read_bytes() == b"fake zip content"
        assert result.name == "2026-05-14.zip"

    def test_download_export_http_error(self):
        downloader = CRZDownloader()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Not Found", request=MagicMock(), response=mock_response
            )
        )

        with (
            patch.object(downloader.client, "get", return_value=mock_response),
            patch.object(downloader, "_wait_for_rate_limit"),
            pytest.raises(httpx.HTTPStatusError),
        ):
            downloader.download_export("2026-01-01")

    def test_compute_sha256(self, tmp_path):
        downloader = CRZDownloader()
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        result = downloader.compute_sha256(test_file)
        assert result == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

    def test_rate_limit_day(self):
        downloader = CRZDownloader()
        with patch("app.ingestion.crz.download.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 12
            assert downloader._rate_limit_delay() == 2.0

    def test_rate_limit_night(self):
        downloader = CRZDownloader()
        with patch("app.ingestion.crz.download.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 22
            assert downloader._rate_limit_delay() == 0.4

    def test_rate_limit_early_morning(self):
        downloader = CRZDownloader()
        with patch("app.ingestion.crz.download.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 3
            assert downloader._rate_limit_delay() == 0.4

    def test_rate_limit_boundary_6am(self):
        downloader = CRZDownloader()
        with patch("app.ingestion.crz.download.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 6
            assert downloader._rate_limit_delay() == 2.0

    def test_rate_limit_boundary_7pm(self):
        downloader = CRZDownloader()
        with patch("app.ingestion.crz.download.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 19
            assert downloader._rate_limit_delay() == 2.0

    def test_rate_limit_boundary_8pm(self):
        downloader = CRZDownloader()
        with patch("app.ingestion.crz.download.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 20
            assert downloader._rate_limit_delay() == 0.4
