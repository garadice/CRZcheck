from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime
from pathlib import Path

import httpx

from app.settings import settings

logger = logging.getLogger(__name__)


class CRZDownloader:
    def __init__(self) -> None:
        self.client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            event_hooks={"response": [self._validate_redirect]},
        )
        self._last_request_time: float = 0.0

    @staticmethod
    def _validate_redirect(response: httpx.Response) -> None:
        """Validate that redirects stay within crz.gov.sk domain."""
        if response.history:
            final_host = response.url.host
            if not final_host.endswith(".crz.gov.sk") and final_host != "crz.gov.sk":
                raise httpx.TransportError(f"Redirect outside CRZ domain blocked: {response.url}")

    def _rate_limit_delay(self) -> float:
        hour = datetime.now().hour
        if 6 <= hour < 20:
            return settings.crz_rate_limit_day_seconds
        return settings.crz_rate_limit_night_seconds

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        delay = self._rate_limit_delay()
        if elapsed < delay:
            time.sleep(delay - elapsed)

    def download_export(self, date_str: str, max_retries: int = 3) -> Path:
        """Download CRZ export ZIP for given date (YYYY-MM-DD) with retry."""
        url = f"{settings.crz_export_base_url}/{date_str}.zip"
        last_error: Exception | None = None

        for attempt in range(max_retries):
            self._wait_for_rate_limit()
            try:
                response = self.client.get(url)
                self._last_request_time = time.time()
                response.raise_for_status()

                dest = settings.raw_data_dir / f"{date_str}.zip"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(response.content)
                return dest
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code < 500:
                    raise
                if attempt < max_retries - 1:
                    wait = 2**attempt
                    logger.warning(
                        f"  {date_str}: HTTP {e.response.status_code}, "
                        f"retrying in {wait}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait)
            except httpx.TransportError as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait = 2**attempt
                    logger.warning(
                        f"  {date_str}: transport error, "
                        f"retrying in {wait}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait)

        raise last_error  # type: ignore[misc]

    def compute_sha256(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
