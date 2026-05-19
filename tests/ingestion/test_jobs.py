"""Tests for app.ingestion.jobs."""

from __future__ import annotations

import io
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.ingestion.crz.models import ParsedContract, ParseResult, SchemaFingerprint
from app.ingestion.jobs import get_date_range, ingest_date, process_export, run_ingestion
from app.settings import settings

# ── Reusable helpers ──────────────────────────────────────────────────────────


def _make_parse_result(n_contracts: int = 1) -> ParseResult:
    """Create a minimal ParseResult with n contracts."""
    contracts = [
        ParsedContract(
            crz_contract_id=f"CRZ-{i:05d}",
            title=f"Contract {i}",
            buyer_name=f"Buyer {i}",
            buyer_ico=f"1000000{i}",
            supplier_name=f"Supplier {i}",
            supplier_ico=f"2000000{i}",
            supplier_address="Bratislava",
            attachments=[],
        )
        for i in range(n_contracts)
    ]
    return ParseResult(
        export_date="2026-05-14",
        contracts=contracts,
        schema_fingerprint=SchemaFingerprint(
            element_names=["ID"], fingerprint="abc", contract_count=n_contracts
        ),
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def ingest_deps():
    """Mock all ingest_date dependencies."""
    with (
        patch("app.ingestion.jobs.get_session_factory") as mock_sf,
        patch("app.ingestion.jobs.process_export") as mock_pe,
        patch("app.ingestion.jobs.upsert_contract") as mock_uc,
        patch("app.ingestion.jobs.record_contract_version") as mock_rcv,
        patch("app.ingestion.jobs.upsert_attachments") as mock_ua,
        patch("app.ingestion.jobs.upsert_supplier") as mock_us,
        patch("app.ingestion.jobs.upsert_organization") as mock_uo,
    ):
        mock_session = MagicMock()
        mock_sf.return_value = MagicMock(return_value=mock_session)
        yield {
            "session": mock_session,
            "sf": mock_sf,
            "process_export": mock_pe,
            "upsert_contract": mock_uc,
            "record_contract_version": mock_rcv,
            "upsert_attachments": mock_ua,
            "upsert_supplier": mock_us,
            "upsert_organization": mock_uo,
        }


@pytest.fixture
def run_ingestion_deps():
    """Mock all run_ingestion dependencies."""
    with (
        patch("app.ingestion.jobs.acquire_ingestion_lock") as mock_al,
        patch("app.ingestion.jobs.get_session_factory") as mock_sf,
        patch("app.ingestion.jobs.ingest_date") as mock_id,
        patch("app.ingestion.jobs.CRZDownloader") as mock_dl_cls,
        patch("app.ingestion.jobs.run_flag_evaluation") as mock_fe,
        patch("app.ingestion.jobs.finish_ingestion_run") as mock_fi,
    ):
        mock_session = MagicMock()
        mock_sf.return_value = MagicMock(return_value=mock_session)
        yield {
            "session": mock_session,
            "sf": mock_sf,
            "acquire_lock": mock_al,
            "ingest_date": mock_id,
            "downloader_cls": mock_dl_cls,
            "flag_eval": mock_fe,
            "finish": mock_fi,
        }


# ── TestGetDateRange ──────────────────────────────────────────────────────────


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

    def test_consecutive_dates(self):
        """Every date in the range should be exactly 1 day after the previous."""
        dates = get_date_range(end_date=date(2026, 5, 14))
        for i in range(1, len(dates)):
            assert dates[i] - dates[i - 1] == timedelta(days=1)


# ── TestProcessExport ─────────────────────────────────────────────────────────


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

    def test_process_export_picks_first_xml(self, tmp_path):
        """When zip has multiple XML files, the first is used."""
        fixture = Path("tests/fixtures/xml/sample.xml")
        zip_path = tmp_path / "multi.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(fixture, "a.xml")
            zf.write(fixture, "b.xml")
        # Should not raise — picks one XML and parses it
        result = process_export(zip_path, date(2026, 5, 14))
        assert len(result.contracts) == 5


# ── TestIngestDate ────────────────────────────────────────────────────────────


class TestIngestDate:
    """Tests for ingest_date using heavy mocking of session and repository."""

    def test_insert_single_contract(self, ingest_deps):
        deps = ingest_deps
        deps["process_export"].return_value = _make_parse_result(n_contracts=1)
        deps["upsert_contract"].return_value = (MagicMock(), True)  # (contract, was_created)
        deps["upsert_organization"].return_value = MagicMock()
        deps["upsert_supplier"].return_value = MagicMock()

        inserted, updated = ingest_date(
            Path("/fake.zip"), date(2026, 5, 14), raw_export_id=1, run_id=10
        )

        assert inserted == 1
        assert updated == 0
        deps["session"].commit.assert_called_once()
        deps["session"].close.assert_called_once()

    def test_update_existing_contract(self, ingest_deps):
        deps = ingest_deps
        deps["process_export"].return_value = _make_parse_result(n_contracts=1)
        deps["upsert_contract"].return_value = (MagicMock(), False)  # was_created=False
        deps["upsert_organization"].return_value = MagicMock()
        deps["upsert_supplier"].return_value = MagicMock()

        inserted, updated = ingest_date(
            Path("/fake.zip"), date(2026, 5, 14), raw_export_id=None, run_id=5
        )

        assert inserted == 0
        assert updated == 1

    def test_mixed_insert_and_update(self, ingest_deps):
        deps = ingest_deps
        deps["process_export"].return_value = _make_parse_result(n_contracts=3)
        # First: insert, Second: update, Third: insert
        deps["upsert_contract"].side_effect = [
            (MagicMock(), True),
            (MagicMock(), False),
            (MagicMock(), True),
        ]
        deps["upsert_organization"].return_value = MagicMock()
        deps["upsert_supplier"].return_value = MagicMock()

        inserted, updated = ingest_date(
            Path("/fake.zip"), date(2026, 5, 14), raw_export_id=1, run_id=10
        )

        assert inserted == 2
        assert updated == 1

    def test_rollback_on_exception(self, ingest_deps):
        deps = ingest_deps
        deps["process_export"].return_value = _make_parse_result(n_contracts=1)
        deps["upsert_contract"].side_effect = Exception("DB error")

        with pytest.raises(Exception, match="DB error"):
            ingest_date(Path("/fake.zip"), date(2026, 5, 14), raw_export_id=1, run_id=10)

        deps["session"].rollback.assert_called_once()
        deps["session"].close.assert_called_once()
        deps["session"].commit.assert_not_called()

    def test_calls_upsert_org_and_supplier(self, ingest_deps):
        deps = ingest_deps
        deps["process_export"].return_value = _make_parse_result(n_contracts=1)
        deps["upsert_contract"].return_value = (MagicMock(), True)
        deps["upsert_organization"].return_value = MagicMock()
        deps["upsert_supplier"].return_value = MagicMock()

        ingest_date(Path("/fake.zip"), date(2026, 5, 14), raw_export_id=1, run_id=10)

        deps["upsert_organization"].assert_called_once()
        deps["upsert_supplier"].assert_called_once()

    def test_skips_org_when_no_name_or_ico(self, ingest_deps):
        deps = ingest_deps
        # Contract with no buyer_name or buyer_ico
        result = ParseResult(
            export_date="2026-05-14",
            contracts=[
                ParsedContract(
                    crz_contract_id="CRZ-00001",
                    buyer_name=None,
                    buyer_ico=None,
                    supplier_name="Sup",
                    supplier_ico="12345678",
                    attachments=[],
                )
            ],
            schema_fingerprint=SchemaFingerprint(
                element_names=["ID"], fingerprint="abc", contract_count=1
            ),
        )
        deps["process_export"].return_value = result
        deps["upsert_contract"].return_value = (MagicMock(), True)
        deps["upsert_supplier"].return_value = MagicMock()

        ingest_date(Path("/fake.zip"), date(2026, 5, 14), raw_export_id=1, run_id=10)

        deps["upsert_organization"].assert_not_called()
        deps["upsert_supplier"].assert_called_once()

    def test_calls_upsert_attachments_when_present(self, ingest_deps):
        from app.ingestion.crz.models import ParsedAttachment

        deps = ingest_deps
        result = ParseResult(
            export_date="2026-05-14",
            contracts=[
                ParsedContract(
                    crz_contract_id="CRZ-00001",
                    attachments=[ParsedAttachment(attachment_id="att001")],
                )
            ],
            schema_fingerprint=SchemaFingerprint(
                element_names=["ID"], fingerprint="abc", contract_count=1
            ),
        )
        deps["process_export"].return_value = result
        deps["upsert_contract"].return_value = (MagicMock(), True)
        deps["upsert_organization"].return_value = MagicMock()
        deps["upsert_supplier"].return_value = MagicMock()

        ingest_date(Path("/fake.zip"), date(2026, 5, 14), raw_export_id=1, run_id=10)

        deps["upsert_attachments"].assert_called_once()

    def test_no_attachments_skips_upsert_attachments(self, ingest_deps):
        deps = ingest_deps
        deps["process_export"].return_value = _make_parse_result(n_contracts=1)
        deps["upsert_contract"].return_value = (MagicMock(), True)
        deps["upsert_organization"].return_value = MagicMock()
        deps["upsert_supplier"].return_value = MagicMock()

        ingest_date(Path("/fake.zip"), date(2026, 5, 14), raw_export_id=1, run_id=10)

        deps["upsert_attachments"].assert_not_called()


# ── TestRunIngestion ──────────────────────────────────────────────────────────


class TestRunIngestion:
    """Tests for run_ingestion with full mocking of all dependencies."""

    def test_lock_failure_returns_early(self, run_ingestion_deps):
        deps = run_ingestion_deps
        deps["acquire_lock"].side_effect = RuntimeError("Ingestion already in progress")

        run_ingestion(end_date=date(2026, 5, 14))

        # Should return early without downloading or ingesting
        deps["downloader_cls"].assert_not_called()
        deps["ingest_date"].assert_not_called()
        deps["flag_eval"].assert_not_called()

    def test_happy_path_downloads_and_ingests(self, run_ingestion_deps):
        deps = run_ingestion_deps
        deps["acquire_lock"].return_value = 42  # run_id

        mock_downloader = MagicMock()
        mock_downloader.download_export.return_value = Path("/fake/2026-05-14.zip")
        deps["downloader_cls"].return_value = mock_downloader

        deps["ingest_date"].return_value = (5, 3)
        deps["flag_eval"].return_value = (8, 2)

        known_dates = [date(2026, 5, 10), date(2026, 5, 11)]
        with patch("app.ingestion.jobs.get_date_range") as mock_range:
            mock_range.return_value = known_dates
            run_ingestion(end_date=date(2026, 5, 11))

        # Should download for each date in the patched range
        assert mock_downloader.download_export.call_count == len(known_dates)
        assert deps["ingest_date"].call_count == len(known_dates)
        deps["flag_eval"].assert_called_once()
        deps["finish"].assert_called()

    def test_download_failure_continues(self, run_ingestion_deps):
        deps = run_ingestion_deps
        deps["acquire_lock"].return_value = 42

        mock_downloader = MagicMock()
        # First download fails, second succeeds
        mock_downloader.download_export.side_effect = [
            Exception("Network error"),
            Path("/fake/2026-05-13.zip"),
        ]
        deps["downloader_cls"].return_value = mock_downloader

        deps["ingest_date"].return_value = (1, 0)
        deps["flag_eval"].return_value = (1, 0)

        # Use a short date range to make test fast
        with patch("app.ingestion.jobs.get_date_range") as mock_range:
            mock_range.return_value = [date(2026, 5, 13), date(2026, 5, 14)]
            run_ingestion(end_date=date(2026, 5, 14))

        # First date failed, so ingest_date called only once
        assert deps["ingest_date"].call_count == 1
        deps["flag_eval"].assert_called_once()

    def test_finish_called_with_completed(self, run_ingestion_deps):
        deps = run_ingestion_deps
        deps["acquire_lock"].return_value = 42

        mock_downloader = MagicMock()
        mock_downloader.download_export.return_value = Path("/fake/2026-05-14.zip")
        deps["downloader_cls"].return_value = mock_downloader

        deps["ingest_date"].return_value = (10, 5)
        deps["flag_eval"].return_value = (15, 3)

        with patch("app.ingestion.jobs.get_date_range") as mock_range:
            mock_range.return_value = [date(2026, 5, 14)]
            run_ingestion(end_date=date(2026, 5, 14))

        # Verify finish_ingestion_run called with "completed"
        deps["finish"].assert_any_call(
            deps["session"], 42, "completed",
            records_seen=15, records_inserted=10, records_updated=5,
        )
        deps["session"].commit.assert_called()

    def test_flag_evaluation_failure_does_not_crash(self, run_ingestion_deps):
        deps = run_ingestion_deps
        deps["acquire_lock"].return_value = 42

        mock_downloader = MagicMock()
        mock_downloader.download_export.return_value = Path("/fake/2026-05-14.zip")
        deps["downloader_cls"].return_value = mock_downloader

        deps["ingest_date"].return_value = (1, 0)
        deps["flag_eval"].side_effect = Exception("Flag eval crashed")

        with patch("app.ingestion.jobs.get_date_range") as mock_range:
            mock_range.return_value = [date(2026, 5, 14)]
            run_ingestion(end_date=date(2026, 5, 14))

        # Should still finish with "completed"
        deps["finish"].assert_any_call(
            deps["session"], 42, "completed",
            records_seen=1, records_inserted=1, records_updated=0,
        )

    def test_outer_exception_finishes_with_failed(self):
        """Outer exception should call finish with 'failed' status."""
        # run_ingestion creates 3 sessions from the factory:
        #   1. lock_session (lines 103-113) — acquire lock, commit, close
        #   2. status_session (line 123) — used for the main try/except/finally
        #   3. eval_session (line 141) — flag evaluation
        #
        # We need distinct mock sessions so we can control side_effects.
        lock_session = MagicMock()
        status_session = MagicMock()
        eval_session = MagicMock()

        with (
            patch("app.ingestion.jobs.acquire_ingestion_lock") as mock_al,
            patch("app.ingestion.jobs.get_session_factory") as mock_sf,
            patch("app.ingestion.jobs.ingest_date") as mock_id,
            patch("app.ingestion.jobs.CRZDownloader") as mock_dl_cls,
            patch("app.ingestion.jobs.run_flag_evaluation") as mock_fe,
            patch("app.ingestion.jobs.finish_ingestion_run") as mock_fi,
        ):
            # factory() returns a session; get_session_factory() returns a factory
            factory = MagicMock(side_effect=[lock_session, status_session, eval_session])
            mock_sf.return_value = factory

            mock_al.return_value = 42
            mock_downloader = MagicMock()
            mock_downloader.download_export.return_value = Path("/fake/2026-05-14.zip")
            mock_dl_cls.return_value = mock_downloader
            mock_id.return_value = (1, 0)
            mock_fe.return_value = (1, 0)

            # Make status_session.commit raise on the FIRST call (line 163)
            # to trigger the outer except block
            status_session.commit.side_effect = [  # fail first, succeed second
                Exception("Commit failed"), None
            ]

            with patch("app.ingestion.jobs.get_date_range") as mock_range:
                mock_range.return_value = [date(2026, 5, 14)]
                run_ingestion(end_date=date(2026, 5, 14))

        # The outer except calls finish_ingestion_run with "failed"
        # The second commit in the except handler succeeds
        mock_fi.assert_any_call(
            status_session, 42, "failed", error_message="Commit failed"
        )

    def test_status_session_closed_in_finally(self, run_ingestion_deps):
        deps = run_ingestion_deps
        deps["acquire_lock"].return_value = 42

        mock_downloader = MagicMock()
        mock_downloader.download_export.return_value = Path("/fake/2026-05-14.zip")
        deps["downloader_cls"].return_value = mock_downloader

        deps["ingest_date"].return_value = (1, 0)
        deps["flag_eval"].return_value = (1, 0)

        with patch("app.ingestion.jobs.get_date_range") as mock_range:
            mock_range.return_value = [date(2026, 5, 14)]
            run_ingestion(end_date=date(2026, 5, 14))

        # The status_session (mock_session instances) should have close called
        assert deps["session"].close.called
