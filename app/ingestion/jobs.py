from __future__ import annotations

import logging
import zipfile
from datetime import date, timedelta
from pathlib import Path

from app.db.repository import (
    acquire_ingestion_lock,
    finish_ingestion_run,
    record_contract_version,
    upsert_attachments,
    upsert_contract,
    upsert_organization,
    upsert_supplier,
)
from app.db.session import get_session_factory
from app.ingestion.crz.download import CRZDownloader
from app.ingestion.crz.parser import parse_xml
from app.settings import settings

logger = logging.getLogger(__name__)


def get_date_range(end_date: date | None = None) -> list[date]:
    if end_date is None:
        end_date = date.today()
    start_date = end_date - timedelta(days=settings.crz_rolling_window_days - 1)
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def process_export(zip_path: Path, export_date: date):
    with zipfile.ZipFile(zip_path, "r") as zf:
        xml_files = [n for n in zf.namelist() if n.endswith(".xml")]
        if not xml_files:
            raise ValueError(f"No XML file found in {zip_path}")
        xml_filename = xml_files[0]
        xml_bytes = zf.read(xml_filename)
    return parse_xml(xml_bytes)


def ingest_date(
    zip_path: Path, export_date: date, raw_export_id: int | None, run_id: int
) -> tuple[int, int]:
    parse_result = process_export(zip_path, export_date)
    inserted = 0
    updated = 0

    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        for parsed_contract in parse_result.contracts:
            _, was_created = upsert_contract(session, parsed_contract, export_date)

            if was_created:
                inserted += 1
            else:
                updated += 1

            record_contract_version(
                session,
                parsed_contract.crz_contract_id,
                export_date,
                raw_export_id,
                parsed_contract,
            )

            if parsed_contract.attachments:
                upsert_attachments(
                    session,
                    parsed_contract.crz_contract_id,
                    parsed_contract.attachments,
                    export_date,
                )

            if parsed_contract.buyer_name or parsed_contract.buyer_ico:
                upsert_organization(session, parsed_contract.buyer_name, parsed_contract.buyer_ico)
            if parsed_contract.supplier_name or parsed_contract.supplier_ico:
                upsert_supplier(
                    session,
                    parsed_contract.supplier_name,
                    parsed_contract.supplier_ico,
                    parsed_contract.supplier_address,
                )

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return inserted, updated


def run_ingestion(end_date: date | None = None) -> None:
    SessionLocal = get_session_factory()
    session = SessionLocal()

    try:
        run_id = acquire_ingestion_lock(session)
        session.commit()
    except RuntimeError as e:
        logger.error(str(e))
        session.close()
        return
    session.close()

    dates = get_date_range(end_date)
    downloader = CRZDownloader()

    total_seen = 0
    total_inserted = 0
    total_updated = 0

    SessionLocal2 = get_session_factory()
    status_session = SessionLocal2()
    try:
        for target_date in dates:
            date_str = target_date.isoformat()
            try:
                logger.info(f"Processing {date_str}...")
                zip_path = downloader.download_export(date_str)
                inserted, updated = ingest_date(zip_path, target_date, None, run_id)
                total_inserted += inserted
                total_updated += updated
                total_seen += inserted + updated
                logger.info(f"  {date_str}: {inserted} inserted, {updated} updated")
            except Exception as e:
                logger.warning(f"  {date_str}: FAILED - {e}")
                continue

        finish_ingestion_run(
            status_session,
            run_id,
            "completed",
            records_seen=total_seen,
            records_inserted=total_inserted,
            records_updated=total_updated,
        )
        status_session.commit()
        logger.info(
            f"Ingestion complete: {total_seen} seen, "
            f"{total_inserted} inserted, {total_updated} updated"
        )
    except Exception as e:
        finish_ingestion_run(status_session, run_id, "failed", error_message=str(e))
        status_session.commit()
        logger.error(f"Ingestion failed: {e}")
    finally:
        status_session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_ingestion()
