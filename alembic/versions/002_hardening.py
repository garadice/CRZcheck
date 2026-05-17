from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite index for contract_risk_flags (optimizes re-flagging DELETE)
    op.create_index(
        "ix_crf_contract_run",
        "contract_risk_flags",
        ["crz_contract_id", "source_run_id"],
    )

    # FK indexes for metric tables
    op.create_index(
        "ix_org_metrics_org_id",
        "organization_metrics_monthly",
        ["organization_id"],
    )
    op.create_index(
        "ix_supplier_metrics_supplier_id",
        "supplier_metrics_monthly",
        ["supplier_id"],
    )

    # Fix DateTime(timezone=True) for ingestion_runs
    op.alter_column(
        "ingestion_runs",
        "started_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="started_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "ingestion_runs",
        "finished_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="finished_at AT TIME ZONE 'UTC'",
    )

    # Fix DateTime(timezone=True) for contracts timestamps
    op.alter_column(
        "contracts",
        "created_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "contracts",
        "updated_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    # Revert contracts timestamps
    op.alter_column(
        "contracts",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
    )
    op.alter_column(
        "contracts",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
    )

    # Revert ingestion_runs timestamps
    op.alter_column(
        "ingestion_runs",
        "finished_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
    )
    op.alter_column(
        "ingestion_runs",
        "started_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
    )

    # Drop FK indexes
    op.drop_index("ix_supplier_metrics_supplier_id", table_name="supplier_metrics_monthly")
    op.drop_index("ix_org_metrics_org_id", table_name="organization_metrics_monthly")

    # Drop composite index
    op.drop_index("ix_crf_contract_run", table_name="contract_risk_flags")
