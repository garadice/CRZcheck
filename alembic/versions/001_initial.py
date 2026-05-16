from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_crz_exports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("export_date", sa.Date(), nullable=False),
        sa.Column("source_url", sa.String(512)),
        sa.Column("downloaded_at", sa.DateTime()),
        sa.Column("http_status", sa.Integer()),
        sa.Column("zip_sha256", sa.String(64)),
        sa.Column("zip_size_bytes", sa.BigInteger()),
        sa.Column("xml_filename", sa.String(255)),
        sa.Column("xml_sha256", sa.String(64)),
        sa.Column("xml_size_bytes", sa.BigInteger()),
        sa.Column("storage_path", sa.String(512)),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("error_message", sa.Text()),
        sa.UniqueConstraint("export_date"),
    )
    op.create_index("ix_raw_crz_exports_status", "raw_crz_exports", ["status"])

    op.create_table(
        "crz_export_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "raw_export_id",
            sa.Integer(),
            sa.ForeignKey("raw_crz_exports.id", ondelete="CASCADE"),
        ),
        sa.Column("parser_version", sa.String(20)),
        sa.Column("record_count", sa.Integer()),
        sa.Column("attachment_count", sa.Integer()),
        sa.Column("parsed_at", sa.DateTime()),
        sa.Column("parse_status", sa.String(20)),
        sa.Column("schema_fingerprint", sa.String(64)),
    )

    op.create_table(
        "contracts",
        sa.Column("crz_contract_id", sa.String(50), primary_key=True),
        sa.Column("title", sa.Text()),
        sa.Column("subject", sa.Text()),
        sa.Column("buyer_name", sa.Text()),
        sa.Column("buyer_ico", sa.String(20)),
        sa.Column("buyer_address", sa.Text()),
        sa.Column("supplier_name", sa.Text()),
        sa.Column("supplier_ico", sa.String(20)),
        sa.Column("supplier_address", sa.Text()),
        sa.Column("department", sa.String(20)),
        sa.Column("contract_type", sa.SmallInteger()),
        sa.Column("contract_kind", sa.SmallInteger()),
        sa.Column("contract_date", sa.Date()),
        sa.Column("publication_date", sa.DateTime()),
        sa.Column("effective_date", sa.Date()),
        sa.Column("valid_until", sa.Date()),
        sa.Column("price_contract", sa.Numeric(18, 2)),
        sa.Column("price_total", sa.Numeric(18, 2)),
        sa.Column("currency", sa.String(3), server_default="EUR"),
        sa.Column("status", sa.String(20)),
        sa.Column("source_export_date", sa.Date()),
        sa.Column("crz_detail_url", sa.String(512)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_contracts_publication_date", "contracts", ["publication_date"])
    op.create_index("ix_contracts_buyer_ico", "contracts", ["buyer_ico"])
    op.create_index("ix_contracts_supplier_ico", "contracts", ["supplier_ico"])
    op.create_index("ix_contracts_price_total", "contracts", ["price_total"])

    op.create_table(
        "contract_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "crz_contract_id",
            sa.String(50),
            sa.ForeignKey("contracts.crz_contract_id", ondelete="CASCADE"),
        ),
        sa.Column("export_date", sa.Date(), nullable=False),
        sa.Column(
            "raw_export_id",
            sa.Integer(),
            sa.ForeignKey("raw_crz_exports.id", ondelete="SET NULL"),
        ),
        sa.Column("payload_hash", sa.String(64)),
        sa.Column("metadata_json", sa.dialects.postgresql.JSONB()),
        sa.Column("change_note", sa.Text()),
        sa.Column("seen_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("crz_contract_id", "export_date", "payload_hash"),
    )
    op.create_index(
        "ix_contract_versions_cid_date", "contract_versions", ["crz_contract_id", "export_date"]
    )

    op.create_table(
        "contract_attachments_metadata",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "crz_contract_id",
            sa.String(50),
            sa.ForeignKey("contracts.crz_contract_id", ondelete="CASCADE"),
        ),
        sa.Column("attachment_id", sa.String(50)),
        sa.Column("attachment_name", sa.Text()),
        sa.Column("scan_filename", sa.String(255)),
        sa.Column("scan_size_bytes", sa.BigInteger()),
        sa.Column("scan_source_url", sa.String(512)),
        sa.Column("text_filename", sa.String(255)),
        sa.Column("text_size_bytes", sa.BigInteger()),
        sa.Column("text_source_url", sa.String(512)),
        sa.Column("channel", sa.String(50)),
        sa.Column("source_export_date", sa.Date()),
    )
    op.create_index("ix_cam_contract_id", "contract_attachments_metadata", ["crz_contract_id"])
    op.create_index("ix_cam_attachment_id", "contract_attachments_metadata", ["attachment_id"])
    op.create_index("ix_cam_scan_filename", "contract_attachments_metadata", ["scan_filename"])
    op.create_index("ix_cam_text_filename", "contract_attachments_metadata", ["text_filename"])

    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ico", sa.String(20)),
        sa.Column("normalized_name", sa.Text()),
        sa.Column("display_name", sa.Text()),
        sa.Column("address", sa.Text()),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("rpo_entity_id", sa.Integer()),
        sa.Column("first_seen_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_organizations_ico",
        "organizations",
        ["ico"],
        unique=True,
        postgresql_where=text("ico IS NOT NULL"),
    )
    op.create_index("ix_organizations_normalized_name", "organizations", ["normalized_name"])

    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ico", sa.String(20)),
        sa.Column("normalized_name", sa.Text()),
        sa.Column("display_name", sa.Text()),
        sa.Column("address", sa.Text()),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("is_probable_natural_person", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("rpo_entity_id", sa.Integer()),
        sa.Column("first_seen_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_suppliers_ico",
        "suppliers",
        ["ico"],
        unique=True,
        postgresql_where=text("ico IS NOT NULL"),
    )
    op.create_index("ix_suppliers_normalized_name", "suppliers", ["normalized_name"])
    op.create_index("ix_suppliers_natural_person", "suppliers", ["is_probable_natural_person"])

    op.create_table(
        "risk_flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("flag_code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("severity_default", sa.String(20), nullable=False),
        sa.Column("methodology", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("phase", sa.String(20), server_default="mvp"),
        sa.UniqueConstraint("flag_code"),
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_type", sa.String(20), server_default="daily"),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("status", sa.String(20), server_default="running"),
        sa.Column("records_seen", sa.Integer(), server_default=sa.text("0")),
        sa.Column("records_inserted", sa.Integer(), server_default=sa.text("0")),
        sa.Column("records_updated", sa.Integer(), server_default=sa.text("0")),
        sa.Column("error_message", sa.Text()),
    )
    op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"])
    op.create_index("ix_ingestion_runs_started_at", "ingestion_runs", ["started_at"])

    op.create_table(
        "contract_risk_flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "crz_contract_id",
            sa.String(50),
            sa.ForeignKey("contracts.crz_contract_id", ondelete="CASCADE"),
        ),
        sa.Column(
            "flag_id",
            sa.Integer(),
            sa.ForeignKey("risk_flags.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "source_run_id",
            sa.Integer(),
            sa.ForeignKey("ingestion_runs.id", ondelete="SET NULL"),
        ),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("evidence_json", sa.dialects.postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_crf_contract_id", "contract_risk_flags", ["crz_contract_id"])
    op.create_index("ix_crf_flag_id", "contract_risk_flags", ["flag_id"])
    op.create_index("ix_crf_severity", "contract_risk_flags", ["severity"])
    op.create_index("ix_crf_created_at", "contract_risk_flags", ["created_at"])
    op.create_index("ix_crf_source_run_id", "contract_risk_flags", ["source_run_id"])

    op.create_table(
        "data_quality_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("ingestion_runs.id", ondelete="CASCADE"),
        ),
        sa.Column("check_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20)),
        sa.Column("observed_value", sa.Text()),
        sa.Column("threshold", sa.Text()),
        sa.Column("details_json", sa.dialects.postgresql.JSONB()),
    )
    op.create_index("ix_dqc_run_id", "data_quality_checks", ["run_id"])
    op.create_index("ix_dqc_check_name", "data_quality_checks", ["check_name"])

    op.create_table(
        "organization_metrics_monthly",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        ),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("contract_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("total_value", sa.Numeric(18, 2), server_default=sa.text("0")),
        sa.Column("flagged_contract_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("top_supplier_share", sa.Numeric(5, 4)),
        sa.UniqueConstraint("organization_id", "month"),
    )

    op.create_table(
        "supplier_metrics_monthly",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "supplier_id",
            sa.Integer(),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
        ),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("contract_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("total_value", sa.Numeric(18, 2), server_default=sa.text("0")),
        sa.Column("buyer_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("growth_ratio", sa.Numeric(10, 4)),
        sa.UniqueConstraint("supplier_id", "month"),
    )


def downgrade() -> None:
    op.drop_table("supplier_metrics_monthly")
    op.drop_table("organization_metrics_monthly")
    op.drop_table("data_quality_checks")
    op.drop_table("contract_risk_flags")
    op.drop_table("ingestion_runs")
    op.drop_table("risk_flags")
    op.drop_table("suppliers")
    op.drop_table("organizations")
    op.drop_table("contract_attachments_metadata")
    op.drop_table("contract_versions")
    op.drop_table("contracts")
    op.drop_table("crz_export_files")
    op.drop_table("raw_crz_exports")
