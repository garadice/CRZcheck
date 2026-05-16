from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Contract,
    ContractAttachmentMetadata,
    ContractVersion,
    IngestionRun,
    Organization,
    Supplier,
)
from app.ingestion.crz.links import make_attachment_url, make_detail_url
from app.ingestion.crz.models import ParsedAttachment, ParsedContract


def upsert_contract(
    session: Session, parsed: ParsedContract, export_date: date
) -> tuple[Contract, bool]:
    from app.transforms.cleaning import (
        clean_name,
        normalize_ico,
        parse_crz_date,
        parse_crz_datetime,
        parse_int_or_none,
        parse_slovak_price,
    )

    contract_id = parsed.crz_contract_id
    stmt = select(Contract).where(Contract.crz_contract_id == contract_id)
    existing = session.execute(stmt).scalar_one_or_none()

    price_contract = parse_slovak_price(parsed.price_contract)
    price_total = parse_slovak_price(parsed.price_total)

    if existing:
        existing.title = clean_name(parsed.title)
        existing.subject = clean_name(parsed.subject)
        existing.buyer_name = clean_name(parsed.buyer_name)
        existing.buyer_ico = normalize_ico(parsed.buyer_ico)
        existing.buyer_address = clean_name(parsed.buyer_address)
        existing.supplier_name = clean_name(parsed.supplier_name)
        existing.supplier_ico = normalize_ico(parsed.supplier_ico)
        existing.supplier_address = clean_name(parsed.supplier_address)
        existing.department = clean_name(parsed.department)
        existing.contract_type = parse_int_or_none(parsed.contract_type)
        existing.contract_kind = parse_int_or_none(parsed.contract_kind)
        existing.contract_date = parse_crz_date(parsed.contract_date)
        existing.publication_date = parse_crz_datetime(parsed.publication_date)
        existing.effective_date = parse_crz_date(parsed.effective_date)
        existing.valid_until = parse_crz_date(parsed.valid_until)
        existing.price_contract = price_contract
        existing.price_total = price_total
        existing.source_export_date = export_date
        existing.crz_detail_url = make_detail_url(contract_id)
        return existing, False
    else:
        contract = Contract(
            crz_contract_id=contract_id,
            title=clean_name(parsed.title),
            subject=clean_name(parsed.subject),
            buyer_name=clean_name(parsed.buyer_name),
            buyer_ico=normalize_ico(parsed.buyer_ico),
            buyer_address=clean_name(parsed.buyer_address),
            supplier_name=clean_name(parsed.supplier_name),
            supplier_ico=normalize_ico(parsed.supplier_ico),
            supplier_address=clean_name(parsed.supplier_address),
            department=clean_name(parsed.department),
            contract_type=parse_int_or_none(parsed.contract_type),
            contract_kind=parse_int_or_none(parsed.contract_kind),
            contract_date=parse_crz_date(parsed.contract_date),
            publication_date=parse_crz_datetime(parsed.publication_date),
            effective_date=parse_crz_date(parsed.effective_date),
            valid_until=parse_crz_date(parsed.valid_until),
            price_contract=price_contract,
            price_total=price_total,
            currency="EUR",
            source_export_date=export_date,
            crz_detail_url=make_detail_url(contract_id),
        )
        session.add(contract)
        return contract, True


def record_contract_version(
    session: Session,
    contract_id: str,
    export_date: date,
    raw_export_id: int | None,
    parsed: ParsedContract,
) -> None:
    payload = parsed.model_dump_json()
    payload_hash = hashlib.sha256(payload.encode()).hexdigest()

    stmt = select(ContractVersion).where(
        ContractVersion.crz_contract_id == contract_id,
        ContractVersion.export_date == export_date,
        ContractVersion.payload_hash == payload_hash,
    )
    existing = session.execute(stmt).scalar_one_or_none()
    if existing:
        return

    version = ContractVersion(
        crz_contract_id=contract_id,
        export_date=export_date,
        raw_export_id=raw_export_id,
        payload_hash=payload_hash,
        metadata_json=parsed.unmapped_fields,
    )
    session.add(version)


def upsert_attachments(
    session: Session,
    contract_id: str,
    attachments: list[ParsedAttachment],
    export_date: date,
) -> None:
    stmt = select(ContractAttachmentMetadata).where(
        ContractAttachmentMetadata.crz_contract_id == contract_id
    )
    for existing in session.execute(stmt).scalars():
        session.delete(existing)

    for att in attachments:
        attachment = ContractAttachmentMetadata(
            crz_contract_id=contract_id,
            attachment_id=att.attachment_id,
            attachment_name=att.attachment_name,
            scan_filename=att.scan_filename,
            scan_size_bytes=att.scan_size_bytes,
            scan_source_url=make_attachment_url(att.scan_filename),
            text_filename=att.text_filename,
            text_size_bytes=att.text_size_bytes,
            text_source_url=make_attachment_url(att.text_filename),
            source_export_date=export_date,
        )
        session.add(attachment)


def upsert_organization(session: Session, name: str | None, ico: str | None) -> Organization | None:
    from app.transforms.cleaning import clean_name, normalize_ico
    from app.transforms.entities import normalize_entity_name

    cleaned_name = clean_name(name)
    cleaned_ico = normalize_ico(ico)
    norm_name = normalize_entity_name(cleaned_name)

    if not cleaned_ico and not norm_name:
        return None

    if cleaned_ico:
        stmt = select(Organization).where(Organization.ico == cleaned_ico)
        existing = session.execute(stmt).scalar_one_or_none()
        if existing:
            if cleaned_name:
                existing.display_name = cleaned_name
            if norm_name:
                existing.normalized_name = norm_name
            existing.last_seen_at = datetime.now(UTC)
            return existing

    if norm_name:
        stmt = select(Organization).where(Organization.normalized_name == norm_name)
        existing = session.execute(stmt).scalar_one_or_none()
        if existing:
            if cleaned_ico:
                existing.ico = cleaned_ico
            if cleaned_name:
                existing.display_name = cleaned_name
            existing.last_seen_at = datetime.now(UTC)
            return existing

    org = Organization(
        ico=cleaned_ico,
        normalized_name=norm_name,
        display_name=cleaned_name,
    )
    session.add(org)
    session.flush()
    return org


def upsert_supplier(
    session: Session, name: str | None, ico: str | None, address: str | None = None
) -> Supplier | None:
    from app.transforms.cleaning import clean_name, normalize_ico
    from app.transforms.entities import is_probable_natural_person, normalize_entity_name

    cleaned_name = clean_name(name)
    cleaned_ico = normalize_ico(ico)
    norm_name = normalize_entity_name(cleaned_name)
    cleaned_address = clean_name(address)

    if not cleaned_ico and not norm_name:
        return None

    is_np = is_probable_natural_person(cleaned_name, cleaned_ico)

    if cleaned_ico:
        stmt = select(Supplier).where(Supplier.ico == cleaned_ico)
        existing = session.execute(stmt).scalar_one_or_none()
        if existing:
            if cleaned_name:
                existing.display_name = cleaned_name
            if norm_name:
                existing.normalized_name = norm_name
            if cleaned_address:
                existing.address = cleaned_address
            existing.is_probable_natural_person = is_np
            existing.last_seen_at = datetime.now(UTC)
            return existing

    if norm_name:
        stmt = select(Supplier).where(Supplier.normalized_name == norm_name)
        existing = session.execute(stmt).scalar_one_or_none()
        if existing:
            if cleaned_ico:
                existing.ico = cleaned_ico
            if cleaned_name:
                existing.display_name = cleaned_name
            if cleaned_address:
                existing.address = cleaned_address
            existing.is_probable_natural_person = is_np
            existing.last_seen_at = datetime.now(UTC)
            return existing

    supplier = Supplier(
        ico=cleaned_ico,
        normalized_name=norm_name,
        display_name=cleaned_name,
        address=cleaned_address,
        is_probable_natural_person=is_np,
    )
    session.add(supplier)
    session.flush()
    return supplier


def acquire_ingestion_lock(session: Session, run_type: str = "daily") -> int:
    """Acquire ingestion lock. Raises RuntimeError if another run is in progress.

    Uses application-level check with stale-run cleanup. For true atomicity
    with multiple processes, use pg_advisory_lock.
    """
    stale_threshold = datetime.now(UTC) - timedelta(hours=6)
    stmt = select(IngestionRun).where(
        IngestionRun.status == "running",
        IngestionRun.run_type == run_type,
        IngestionRun.started_at < stale_threshold,
    )
    for stale_run in session.execute(stmt).scalars():
        stale_run.status = "failed"
        stale_run.finished_at = datetime.now(UTC)
        stale_run.error_message = "Automatický cleanup: prekročený časový limit (6h)"
    if session.execute(stmt).scalars():
        session.flush()

    stmt = select(IngestionRun).where(
        IngestionRun.status == "running",
        IngestionRun.run_type == run_type,
    )
    in_progress = session.execute(stmt).scalar_one_or_none()
    if in_progress:
        raise RuntimeError(
            f"Ingestion already in progress (run_id={in_progress.id}, "
            f"started_at={in_progress.started_at})"
        )
    run = IngestionRun(run_type=run_type, status="running")
    session.add(run)
    session.flush()
    return run.id


def finish_ingestion_run(
    session: Session,
    run_id: int,
    status: str,
    records_seen: int = 0,
    records_inserted: int = 0,
    records_updated: int = 0,
    error_message: str | None = None,
) -> None:
    stmt = select(IngestionRun).where(IngestionRun.id == run_id)
    run = session.execute(stmt).scalar_one()
    run.status = status
    run.finished_at = datetime.now(UTC)
    run.records_seen = records_seen
    run.records_inserted = records_inserted
    run.records_updated = records_updated
    if error_message:
        run.error_message = error_message
