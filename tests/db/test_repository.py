from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import JSON, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.db.models import (
    Base,
    ContractAttachmentMetadata,
    ContractVersion,
    IngestionRun,
)
from app.db.repository import (
    acquire_ingestion_lock,
    finish_ingestion_run,
    record_contract_version,
    upsert_attachments,
    upsert_contract,
    upsert_organization,
    upsert_supplier,
)
from app.ingestion.crz.models import ParsedAttachment, ParsedContract


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return compiler.process(JSON(), **kw)


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        Base.metadata.create_all(conn)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def session(engine):
    with Session(engine) as sess:
        yield sess


@pytest.fixture
def sample_contract() -> ParsedContract:
    return ParsedContract(
        crz_contract_id="99999",
        title="Test Contract",
        buyer_name="Ministerstvo financií SR",
        buyer_ico="98765432",
        buyer_address="Bratislava",
        supplier_name="ABC Company s.r.o.",
        supplier_ico="12345678",
        supplier_address="Košice",
        subject="Test subject",
        effective_date="2026-01-15",
        valid_until="2027-01-15",
        price_contract="50 000",
        price_total="50 000",
        publication_date="2026-05-14 10:30:00",
        contract_type="1",
        contract_kind="1",
        department="100",
        contract_date="2026-05-14",
        attachments=[],
        unmapped_fields={"poznamka": "test note"},
    )


class TestUpsertContract:
    def test_insert_new_contract(self, session, sample_contract):
        contract, was_created = upsert_contract(session, sample_contract, date(2026, 5, 14))
        session.flush()

        assert was_created is True
        assert contract.crz_contract_id == "99999"
        assert contract.title == "Test Contract"
        assert contract.buyer_ico == "98765432"
        assert contract.supplier_ico == "12345678"
        assert contract.price_total == Decimal("50000")
        assert contract.currency == "EUR"

    def test_update_existing_contract(self, session, sample_contract):
        c1, created1 = upsert_contract(session, sample_contract, date(2026, 5, 14))
        session.flush()
        assert created1 is True

        modified = sample_contract.model_copy(update={"title": "Updated Title"})
        c2, created2 = upsert_contract(session, modified, date(2026, 5, 15))
        session.flush()

        assert created2 is False
        assert c1.crz_contract_id == c2.crz_contract_id
        assert c2.title == "Updated Title"

    def test_slovak_price_parsed(self, session):
        parsed = ParsedContract(
            crz_contract_id="88888",
            price_contract="1 200,50 EUR",
            price_total="1 500,00 EUR",
        )
        contract, _ = upsert_contract(session, parsed, date(2026, 5, 14))
        session.flush()

        assert contract.price_contract == Decimal("1200.50")
        assert contract.price_total == Decimal("1500.00")

    def test_zero_date_becomes_none(self, session):
        parsed = ParsedContract(
            crz_contract_id="77777",
            effective_date="0000-00-00",
            valid_until="0000-00-00",
        )
        contract, _ = upsert_contract(session, parsed, date(2026, 5, 14))
        session.flush()

        assert contract.effective_date is None
        assert contract.valid_until is None

    def test_empty_fields_become_none(self, session):
        parsed = ParsedContract(crz_contract_id="66666", title="", buyer_name="   ")
        contract, _ = upsert_contract(session, parsed, date(2026, 5, 14))
        session.flush()

        assert contract.title is None
        assert contract.buyer_name is None


class TestRecordContractVersion:
    def test_records_version(self, session, sample_contract):
        upsert_contract(session, sample_contract, date(2026, 5, 14))
        session.flush()

        record_contract_version(session, "99999", date(2026, 5, 14), None, sample_contract)
        session.flush()

        versions = list(session.execute(select(ContractVersion)).scalars())
        assert len(versions) == 1
        assert versions[0].crz_contract_id == "99999"
        assert versions[0].payload_hash is not None

    def test_idempotent_same_version(self, session, sample_contract):
        upsert_contract(session, sample_contract, date(2026, 5, 14))
        session.flush()

        record_contract_version(session, "99999", date(2026, 5, 14), None, sample_contract)
        session.flush()
        record_contract_version(session, "99999", date(2026, 5, 14), None, sample_contract)
        session.flush()

        versions = list(session.execute(select(ContractVersion)).scalars())
        assert len(versions) == 1


class TestUpsertAttachments:
    def test_insert_attachments(self, session, sample_contract):
        upsert_contract(session, sample_contract, date(2026, 5, 14))
        session.flush()

        attachments = [
            ParsedAttachment(
                attachment_id="att001",
                attachment_name="Zmluva.pdf",
                scan_filename="zmluva_99999.pdf",
                scan_size_bytes=102400,
            ),
        ]
        upsert_attachments(session, "99999", attachments, date(2026, 5, 14))
        session.flush()

        atts = list(session.execute(select(ContractAttachmentMetadata)).scalars())
        assert len(atts) == 1
        assert atts[0].scan_source_url == "https://www.crz.gov.sk/data/att/zmluva_99999.pdf"

    def test_replace_attachments(self, session, sample_contract):
        upsert_contract(session, sample_contract, date(2026, 5, 14))
        session.flush()

        upsert_attachments(
            session,
            "99999",
            [ParsedAttachment(attachment_id="att001", scan_filename="old.pdf")],
            date(2026, 5, 14),
        )
        session.flush()

        upsert_attachments(
            session,
            "99999",
            [
                ParsedAttachment(attachment_id="att002", scan_filename="new1.pdf"),
                ParsedAttachment(attachment_id="att003", scan_filename="new2.pdf"),
            ],
            date(2026, 5, 15),
        )
        session.flush()

        atts = list(session.execute(select(ContractAttachmentMetadata)).scalars())
        assert len(atts) == 2
        filenames = [a.scan_filename for a in atts]
        assert "old.pdf" not in filenames


class TestUpsertOrganization:
    def test_create_new_organization(self, session):
        org = upsert_organization(session, "Ministerstvo financií SR", "98765432")
        session.flush()

        assert org is not None
        assert org.display_name == "Ministerstvo financií SR"
        assert org.ico == "98765432"
        assert org.normalized_name == "ministerstvo financií sr"

    def test_find_existing_by_ico(self, session):
        org1 = upsert_organization(session, "Min Fin", "98765432")
        session.flush()

        org2 = upsert_organization(session, "Ministerstvo financií", "98765432")
        session.flush()

        assert org1.id == org2.id
        assert org2.display_name == "Ministerstvo financií"

    def test_returns_none_for_empty(self, session):
        org = upsert_organization(session, None, None)
        assert org is None

    def test_returns_none_for_whitespace(self, session):
        org = upsert_organization(session, "   ", "   ")
        assert org is None


class TestUpsertSupplier:
    def test_create_legal_entity(self, session):
        supplier = upsert_supplier(session, "ABC s.r.o.", "12345678", "Bratislava")
        session.flush()

        assert supplier is not None
        assert supplier.is_probable_natural_person is False
        assert supplier.display_name == "ABC s.r.o."

    def test_create_natural_person(self, session):
        supplier = upsert_supplier(session, "Ján Novák", None, "Košice")
        session.flush()

        assert supplier is not None
        assert supplier.is_probable_natural_person is True

    def test_find_existing_by_ico(self, session):
        s1 = upsert_supplier(session, "ABC s.r.o.", "12345678", "Bratislava")
        session.flush()

        s2 = upsert_supplier(session, "ABC Company s.r.o.", "12345678", "Košice")
        session.flush()

        assert s1.id == s2.id
        assert s2.display_name == "ABC Company s.r.o."

    def test_returns_none_for_empty(self, session):
        supplier = upsert_supplier(session, None, None, None)
        assert supplier is None


class TestIngestionLock:
    def test_acquire_lock(self, session):
        run_id = acquire_ingestion_lock(session, "daily")

        assert run_id is not None
        run = session.execute(select(IngestionRun)).scalar_one()
        assert run.status == "running"
        assert run.run_type == "daily"

    def test_acquire_lock_prevents_concurrent(self, session):
        acquire_ingestion_lock(session, "daily")

        with pytest.raises(RuntimeError, match="already in progress"):
            acquire_ingestion_lock(session, "daily")

    def test_different_run_types_allowed(self, session):
        r1 = acquire_ingestion_lock(session, "daily")
        r2 = acquire_ingestion_lock(session, "backfill")

        assert r1 != r2


class TestFinishIngestionRun:
    def test_finish_completed(self, session):
        run_id = acquire_ingestion_lock(session, "daily")

        finish_ingestion_run(
            session, run_id, "completed", records_seen=100, records_inserted=80, records_updated=20
        )
        session.commit()

        run = session.execute(select(IngestionRun)).scalar_one()
        assert run.status == "completed"
        assert run.records_seen == 100
        assert run.records_inserted == 80
        assert run.records_updated == 20

    def test_finish_failed(self, session):
        run_id = acquire_ingestion_lock(session, "daily")

        finish_ingestion_run(session, run_id, "failed", error_message="Test error")
        session.commit()

        run = session.execute(select(IngestionRun)).scalar_one()
        assert run.status == "failed"
        assert run.error_message == "Test error"
        assert run.finished_at is not None
