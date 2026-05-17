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

    def test_validate_redirect_within_crz(self):
        response = MagicMock(spec=httpx.Response)
        response.history = [MagicMock()]
        response.url = MagicMock()
        response.url.host = "www.crz.gov.sk"
        CRZDownloader._validate_redirect(response)

    def test_validate_redirect_outside_crz(self):
        response = MagicMock(spec=httpx.Response)
        response.history = [MagicMock()]
        response.url = MagicMock()
        response.url.host = "evil.com"
        with pytest.raises(httpx.TransportError, match="Redirect outside CRZ"):
            CRZDownloader._validate_redirect(response)

    def test_validate_redirect_subdomain_crz(self):
        response = MagicMock(spec=httpx.Response)
        response.history = [MagicMock()]
        response.url = MagicMock()
        response.url.host = "data.crz.gov.sk"
        CRZDownloader._validate_redirect(response)

    def test_no_redirect_passes(self):
        response = MagicMock(spec=httpx.Response)
        response.history = []
        CRZDownloader._validate_redirect(response)

    def test_rate_limit_delay_daytime(self):
        dl = CRZDownloader()
        with patch("app.ingestion.crz.download.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 12
            assert dl._rate_limit_delay() == 2.0

    def test_rate_limit_delay_nighttime(self):
        dl = CRZDownloader()
        with patch("app.ingestion.crz.download.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 22
            assert dl._rate_limit_delay() == 0.4

    def test_download_retries_on_5xx(self, tmp_path):
        dl = CRZDownloader()
        dl._wait_for_rate_limit = MagicMock()

        response_500 = MagicMock()
        response_500.status_code = 500
        response_500.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=response_500
        )

        response_200 = MagicMock()
        response_200.status_code = 200
        response_200.content = b"fake zip"
        response_200.raise_for_status.return_value = None

        dl.client.get = MagicMock(side_effect=[response_500, response_200])

        with (
            patch("app.ingestion.crz.download.time.sleep"),
            patch("app.ingestion.crz.download.settings") as mock_settings,
        ):
            mock_settings.raw_data_dir = tmp_path
            result = dl.download_export("2026-05-14", max_retries=3)

        assert dl.client.get.call_count == 2
        assert result.read_bytes() == b"fake zip"

    def test_download_no_retry_on_4xx(self):
        dl = CRZDownloader()
        dl._wait_for_rate_limit = MagicMock()

        response_404 = MagicMock()
        response_404.status_code = 404
        response_404.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=response_404
        )

        dl.client.get = MagicMock(return_value=response_404)

        with pytest.raises(httpx.HTTPStatusError):
            dl.download_export("2026-01-01", max_retries=3)

        assert dl.client.get.call_count == 1
