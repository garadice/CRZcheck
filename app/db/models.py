from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.session import Base


class RawCrzExport(Base):
    __tablename__ = "raw_crz_exports"

    id: Mapped[int] = mapped_column(primary_key=True)
    export_date: Mapped[date]
    source_url: Mapped[str | None] = mapped_column(String(512))
    downloaded_at: Mapped[datetime | None]
    http_status: Mapped[int | None]
    zip_sha256: Mapped[str | None] = mapped_column(String(64))
    zip_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    xml_filename: Mapped[str | None] = mapped_column(String(255))
    xml_sha256: Mapped[str | None] = mapped_column(String(64))
    xml_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    storage_path: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("export_date"),
        Index("ix_raw_crz_exports_status", "status"),
    )


class CrzExportFile(Base):
    __tablename__ = "crz_export_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_export_id: Mapped[int] = mapped_column(ForeignKey("raw_crz_exports.id", ondelete="CASCADE"))
    parser_version: Mapped[str | None] = mapped_column(String(20))
    record_count: Mapped[int | None]
    attachment_count: Mapped[int | None]
    parsed_at: Mapped[datetime | None]
    parse_status: Mapped[str | None] = mapped_column(String(20))
    schema_fingerprint: Mapped[str | None] = mapped_column(String(64))


class Contract(Base):
    __tablename__ = "contracts"

    crz_contract_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    buyer_name: Mapped[str | None] = mapped_column(Text)
    buyer_ico: Mapped[str | None] = mapped_column(String(20))
    buyer_address: Mapped[str | None] = mapped_column(Text)
    supplier_name: Mapped[str | None] = mapped_column(Text)
    supplier_ico: Mapped[str | None] = mapped_column(String(20))
    supplier_address: Mapped[str | None] = mapped_column(Text)
    department: Mapped[str | None] = mapped_column(String(20))
    contract_type: Mapped[int | None] = mapped_column(SmallInteger)
    contract_kind: Mapped[int | None] = mapped_column(SmallInteger)
    contract_date: Mapped[date | None]
    publication_date: Mapped[datetime | None]
    effective_date: Mapped[date | None]
    valid_until: Mapped[date | None]
    price_contract: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    price_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    status: Mapped[str | None] = mapped_column(String(20))
    source_export_date: Mapped[date | None]
    crz_detail_url: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_contracts_publication_date", "publication_date"),
        Index("ix_contracts_buyer_ico", "buyer_ico"),
        Index("ix_contracts_supplier_ico", "supplier_ico"),
        Index("ix_contracts_price_total", "price_total"),
    )


class ContractVersion(Base):
    __tablename__ = "contract_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    crz_contract_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("contracts.crz_contract_id", ondelete="CASCADE")
    )
    export_date: Mapped[date]
    raw_export_id: Mapped[int | None] = mapped_column(
        ForeignKey("raw_crz_exports.id", ondelete="SET NULL")
    )
    payload_hash: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    change_note: Mapped[str | None] = mapped_column(Text)
    seen_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        UniqueConstraint("crz_contract_id", "export_date", "payload_hash"),
        Index("ix_contract_versions_cid_date", "crz_contract_id", "export_date"),
    )


class ContractAttachmentMetadata(Base):
    __tablename__ = "contract_attachments_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    crz_contract_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("contracts.crz_contract_id", ondelete="CASCADE")
    )
    attachment_id: Mapped[str | None] = mapped_column(String(50))
    attachment_name: Mapped[str | None] = mapped_column(Text)
    scan_filename: Mapped[str | None] = mapped_column(String(255))
    scan_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    scan_source_url: Mapped[str | None] = mapped_column(String(512))
    text_filename: Mapped[str | None] = mapped_column(String(255))
    text_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    text_source_url: Mapped[str | None] = mapped_column(String(512))
    channel: Mapped[str | None] = mapped_column(String(50))
    source_export_date: Mapped[date | None]

    __table_args__ = (
        Index("ix_cam_contract_id", "crz_contract_id"),
        Index("ix_cam_attachment_id", "attachment_id"),
        Index("ix_cam_scan_filename", "scan_filename"),
        Index("ix_cam_text_filename", "text_filename"),
    )


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    ico: Mapped[str | None] = mapped_column(String(20))
    normalized_name: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    rpo_entity_id: Mapped[int | None]
    first_seen_at: Mapped[datetime] = mapped_column(default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        Index(
            "idx_organizations_ico",
            "ico",
            unique=True,
            postgresql_where=text("ico IS NOT NULL"),
        ),
        Index("ix_organizations_normalized_name", "normalized_name"),
    )


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    ico: Mapped[str | None] = mapped_column(String(20))
    normalized_name: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    is_probable_natural_person: Mapped[bool] = mapped_column(default=False)
    rpo_entity_id: Mapped[int | None]
    first_seen_at: Mapped[datetime] = mapped_column(default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        Index(
            "idx_suppliers_ico",
            "ico",
            unique=True,
            postgresql_where=text("ico IS NOT NULL"),
        ),
        Index("ix_suppliers_normalized_name", "normalized_name"),
        Index("ix_suppliers_natural_person", "is_probable_natural_person"),
    )


class RiskFlag(Base):
    __tablename__ = "risk_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    flag_code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    severity_default: Mapped[str] = mapped_column(String(20))
    methodology: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    phase: Mapped[str] = mapped_column(String(20), default="mvp")

    __table_args__ = (UniqueConstraint("flag_code"),)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_type: Mapped[str] = mapped_column(String(20), default="daily")
    started_at: Mapped[datetime] = mapped_column(default=func.now())
    finished_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(String(20), default="running")
    records_seen: Mapped[int] = mapped_column(default=0)
    records_inserted: Mapped[int] = mapped_column(default=0)
    records_updated: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_ingestion_runs_status", "status"),
        Index("ix_ingestion_runs_started_at", "started_at"),
    )


class ContractRiskFlag(Base):
    __tablename__ = "contract_risk_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    crz_contract_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("contracts.crz_contract_id", ondelete="CASCADE")
    )
    flag_id: Mapped[int] = mapped_column(ForeignKey("risk_flags.id", ondelete="RESTRICT"))
    source_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="SET NULL")
    )
    severity: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(Text)
    evidence_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        Index("ix_crf_contract_id", "crz_contract_id"),
        Index("ix_crf_flag_id", "flag_id"),
        Index("ix_crf_severity", "severity"),
        Index("ix_crf_created_at", "created_at"),
        Index("ix_crf_source_run_id", "source_run_id"),
    )


class DataQualityCheck(Base):
    __tablename__ = "data_quality_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.id", ondelete="CASCADE"))
    check_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str | None] = mapped_column(String(20))
    observed_value: Mapped[str | None] = mapped_column(Text)
    threshold: Mapped[str | None] = mapped_column(Text)
    details_json: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("ix_dqc_run_id", "run_id"),
        Index("ix_dqc_check_name", "check_name"),
    )


class OrganizationMetricsMonthly(Base):
    __tablename__ = "organization_metrics_monthly"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    month: Mapped[date]
    contract_count: Mapped[int] = mapped_column(default=0)
    total_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    flagged_contract_count: Mapped[int] = mapped_column(default=0)
    top_supplier_share: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    __table_args__ = (UniqueConstraint("organization_id", "month"),)


class SupplierMetricsMonthly(Base):
    __tablename__ = "supplier_metrics_monthly"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"))
    month: Mapped[date]
    contract_count: Mapped[int] = mapped_column(default=0)
    total_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    buyer_count: Mapped[int] = mapped_column(default=0)
    growth_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    __table_args__ = (UniqueConstraint("supplier_id", "month"),)
