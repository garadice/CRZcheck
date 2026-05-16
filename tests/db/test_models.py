from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import JSON, create_engine, inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.db.models import (
    Contract,
    ContractAttachmentMetadata,
    ContractRiskFlag,
    ContractVersion,
    DataQualityCheck,
    IngestionRun,
    Organization,
    RawCrzExport,
    RiskFlag,
    Supplier,
)
from app.db.session import Base


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


EXPECTED_TABLES = [
    "raw_crz_exports",
    "crz_export_files",
    "contracts",
    "contract_versions",
    "contract_attachments_metadata",
    "organizations",
    "suppliers",
    "risk_flags",
    "contract_risk_flags",
    "ingestion_runs",
    "data_quality_checks",
    "organization_metrics_monthly",
    "supplier_metrics_monthly",
]


def test_all_13_tables_registered():
    table_names = set(Base.metadata.tables.keys())
    for t in EXPECTED_TABLES:
        assert t in table_names, f"Table '{t}' not found in Base.metadata"
    assert len(EXPECTED_TABLES) == len(table_names)


def test_can_insert_and_query_raw_export(session):
    row = RawCrzExport(
        export_date=date(2025, 1, 15),
        source_url="https://example.com/export.zip",
        downloaded_at=datetime(2025, 1, 15, 10, 0),
        http_status=200,
        zip_sha256="abc123",
        zip_size_bytes=1024,
        status="downloaded",
    )
    session.add(row)
    session.flush()
    result = session.query(RawCrzExport).one()
    assert result.export_date == date(2025, 1, 15)
    assert result.http_status == 200
    assert result.status == "downloaded"


def test_can_insert_and_query_contract(session):
    contract = Contract(
        crz_contract_id="CRZ-2025-001",
        title="Test Contract",
        buyer_name="Ministry of Testing",
        buyer_ico="12345678",
        supplier_name="Test Corp",
        supplier_ico="87654321",
        contract_date=date(2025, 1, 1),
        publication_date=datetime(2025, 1, 2, 12, 0),
        price_total=Decimal("100000.00"),
        currency="EUR",
    )
    session.add(contract)
    session.flush()
    result = session.query(Contract).one()
    assert result.crz_contract_id == "CRZ-2025-001"
    assert result.title == "Test Contract"
    assert result.currency == "EUR"
    assert result.price_total == Decimal("100000.00")


def test_can_insert_contract_version(session):
    contract = Contract(crz_contract_id="CRZ-2025-002")
    session.add(contract)
    session.flush()
    version = ContractVersion(
        crz_contract_id="CRZ-2025-002",
        export_date=date(2025, 1, 15),
        payload_hash="deadbeef",
        change_note="Initial import",
    )
    session.add(version)
    session.flush()
    result = session.query(ContractVersion).one()
    assert result.crz_contract_id == "CRZ-2025-002"
    assert result.payload_hash == "deadbeef"


def test_can_insert_contract_attachment(session):
    contract = Contract(crz_contract_id="CRZ-2025-003")
    session.add(contract)
    session.flush()
    attachment = ContractAttachmentMetadata(
        crz_contract_id="CRZ-2025-003",
        attachment_id="ATT-001",
        attachment_name="contract_scan.pdf",
        scan_filename="scan_001.pdf",
        scan_size_bytes=2048,
    )
    session.add(attachment)
    session.flush()
    result = session.query(ContractAttachmentMetadata).one()
    assert result.crz_contract_id == "CRZ-2025-003"
    assert result.attachment_id == "ATT-001"
    assert result.scan_filename == "scan_001.pdf"


def test_can_insert_organization(session):
    org = Organization(
        ico="12345678",
        normalized_name="ministry of testing",
        display_name="Ministry of Testing",
        address="Bratislava",
        entity_type="government",
    )
    session.add(org)
    session.flush()
    result = session.query(Organization).one()
    assert result.ico == "12345678"
    assert result.display_name == "Ministry of Testing"


def test_can_insert_supplier(session):
    supplier = Supplier(
        ico="87654321",
        normalized_name="test corp sro",
        display_name="Test Corp s.r.o.",
        is_probable_natural_person=False,
    )
    session.add(supplier)
    session.flush()
    result = session.query(Supplier).one()
    assert result.ico == "87654321"
    assert result.is_probable_natural_person is False


def test_can_insert_risk_flag(session):
    flag = RiskFlag(
        flag_code="SINGLE_BIDDER",
        name="Single Bidder",
        severity_default="medium",
        phase="mvp",
    )
    session.add(flag)
    session.flush()
    result = session.query(RiskFlag).one()
    assert result.flag_code == "SINGLE_BIDDER"
    assert result.severity_default == "medium"
    assert result.is_active is True


def test_can_insert_ingestion_run(session):
    run = IngestionRun(run_type="daily", status="running")
    session.add(run)
    session.flush()
    result = session.query(IngestionRun).one()
    assert result.run_type == "daily"
    assert result.status == "running"
    assert result.records_seen == 0


def test_can_insert_contract_risk_flag(session):
    contract = Contract(crz_contract_id="CRZ-2025-010")
    session.add(contract)
    flag = RiskFlag(flag_code="HIGH_VALUE", name="High Value", severity_default="info")
    session.add(flag)
    run = IngestionRun(run_type="daily")
    session.add(run)
    session.flush()
    crf = ContractRiskFlag(
        crz_contract_id="CRZ-2025-010",
        flag_id=flag.id,
        source_run_id=run.id,
        severity="high",
        reason="Unusually large contract",
    )
    session.add(crf)
    session.flush()
    result = session.query(ContractRiskFlag).one()
    assert result.crz_contract_id == "CRZ-2025-010"
    assert result.flag_id == flag.id
    assert result.source_run_id == run.id
    assert result.severity == "high"


def test_can_insert_data_quality_check(session):
    run = IngestionRun(run_type="daily")
    session.add(run)
    session.flush()
    dqc = DataQualityCheck(
        run_id=run.id,
        check_name="null_buyer_check",
        status="pass",
        observed_value="0",
        threshold="5",
    )
    session.add(dqc)
    session.flush()
    result = session.query(DataQualityCheck).one()
    assert result.check_name == "null_buyer_check"
    assert result.run_id == run.id


def test_organization_table_name():
    assert Organization.__tablename__ == "organizations"


def test_supplier_table_name():
    assert Supplier.__tablename__ == "suppliers"


def test_contract_primary_key():
    pk_cols = [c.name for c in inspect(Contract).primary_key]
    assert pk_cols == ["crz_contract_id"]


def test_contract_default_currency(session):
    contract = Contract(crz_contract_id="CRZ-DEFAULT-CUR")
    session.add(contract)
    session.flush()
    result = session.query(Contract).filter_by(crz_contract_id="CRZ-DEFAULT-CUR").one()
    assert result.currency == "EUR"
