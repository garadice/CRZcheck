"""Shared database queries for the dashboard."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Contract,
    ContractAttachmentMetadata,
    ContractRiskFlag,
    IngestionRun,
    Organization,
    RiskFlag,
    Supplier,
)
from app.flags.evaluate import compound_severity


def get_overview_stats(session: Session) -> dict[str, Any]:
    """Get overview statistics for the home page."""
    total_contracts = session.execute(select(func.count(Contract.crz_contract_id))).scalar() or 0
    total_flagged = (
        session.execute(
            select(func.count(func.distinct(ContractRiskFlag.crz_contract_id)))
        ).scalar()
        or 0
    )
    total_organizations = session.execute(select(func.count(Organization.id))).scalar() or 0
    total_suppliers = session.execute(select(func.count(Supplier.id))).scalar() or 0

    total_value = session.execute(
        select(func.sum(Contract.price_total)).where(Contract.price_total.isnot(None))
    ).scalar() or Decimal("0")

    return {
        "total_contracts": total_contracts,
        "total_flagged": total_flagged,
        "total_organizations": total_organizations,
        "total_suppliers": total_suppliers,
        "total_value": total_value,
    }


def _escape_ilike(query: str) -> str:
    """Escape SQL LIKE/ILIKE wildcards in user input."""
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_contracts(
    session: Session,
    query: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
) -> list[Contract]:
    """Search contracts by text query and date range."""
    stmt = select(Contract).order_by(Contract.publication_date.desc())
    if query:
        escaped = _escape_ilike(query)
        stmt = stmt.where(
            Contract.title.ilike(f"%{escaped}%", escape="\\")
            | Contract.supplier_name.ilike(f"%{escaped}%", escape="\\")
            | Contract.buyer_name.ilike(f"%{escaped}%", escape="\\")
            | Contract.crz_contract_id.ilike(f"%{escaped}%", escape="\\")
        )
    if date_from:
        stmt = stmt.where(Contract.publication_date >= date_from)
    if date_to:
        stmt = stmt.where(Contract.publication_date <= date_to)
    stmt = stmt.limit(limit)
    return list(session.execute(stmt).scalars().all())


def get_flagged_contracts(
    session: Session,
    severity_filter: str | None = None,
    flag_code_filter: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Get flagged contracts with their flags and compound severity.

    Default filter: medium+ severity OR 2+ flags.
    """
    flag_count_subq = (
        select(
            ContractRiskFlag.crz_contract_id,
            func.count(ContractRiskFlag.id).label("flag_count"),
        )
        .group_by(ContractRiskFlag.crz_contract_id)
        .subquery()
    )

    stmt = (
        select(
            Contract,
            flag_count_subq.c.flag_count,
        )
        .join(ContractRiskFlag, ContractRiskFlag.crz_contract_id == Contract.crz_contract_id)
        .join(RiskFlag, RiskFlag.id == ContractRiskFlag.flag_id)
        .join(flag_count_subq, flag_count_subq.c.crz_contract_id == Contract.crz_contract_id)
    )

    if date_from:
        stmt = stmt.where(Contract.publication_date >= date_from)
    if date_to:
        stmt = stmt.where(Contract.publication_date <= date_to)
    if flag_code_filter:
        stmt = stmt.where(RiskFlag.flag_code == flag_code_filter)

    stmt = stmt.distinct().order_by(Contract.publication_date.desc()).limit(limit)
    rows = session.execute(stmt).all()

    if not rows:
        return []

    contract_ids = [contract.crz_contract_id for contract, _ in rows]
    flag_rows = session.execute(
        select(ContractRiskFlag, RiskFlag)
        .join(RiskFlag, RiskFlag.id == ContractRiskFlag.flag_id)
        .where(ContractRiskFlag.crz_contract_id.in_(contract_ids))
    ).all()

    flags_by_contract: dict[str, list[dict]] = {}
    for crf, risk_flag in flag_rows:
        flags_by_contract.setdefault(crf.crz_contract_id, []).append(
            {
                "flag_code": risk_flag.flag_code,
                "name": risk_flag.name,
                "severity": crf.severity,
                "reason": crf.reason,
            }
        )

    results = []
    for contract, flag_count in rows:
        flags = flags_by_contract.get(contract.crz_contract_id, [])
        sev = compound_severity(flags)

        if severity_filter and sev != "none":
            severity_order = {"low": 1, "medium": 2, "high": 3}
            if (
                severity_order.get(sev, 0) < severity_order.get(severity_filter, 0)
                and flag_count < 2
            ):
                continue

        results.append(
            {
                "contract": contract,
                "flags": flags,
                "flag_count": flag_count,
                "compound_severity": sev,
            }
        )

    return results


def get_contract_flags(session: Session, contract_id: str) -> list[dict]:
    """Get flags for a specific contract as list of dicts."""
    stmt = (
        select(ContractRiskFlag, RiskFlag)
        .join(RiskFlag, RiskFlag.id == ContractRiskFlag.flag_id)
        .where(ContractRiskFlag.crz_contract_id == contract_id)
    )
    rows = session.execute(stmt).all()
    return [
        {
            "flag_code": risk_flag.flag_code,
            "name": risk_flag.name,
            "severity": crf.severity,
            "reason": crf.reason,
        }
        for crf, risk_flag in rows
    ]


def get_contract_detail(session: Session, contract_id: str) -> Contract | None:
    """Get a single contract with all details."""
    stmt = select(Contract).where(Contract.crz_contract_id == contract_id)
    return session.execute(stmt).scalar_one_or_none()


def get_contract_attachments(
    session: Session, contract_id: str
) -> list[ContractAttachmentMetadata]:
    """Get attachments for a contract."""
    stmt = select(ContractAttachmentMetadata).where(
        ContractAttachmentMetadata.crz_contract_id == contract_id
    )
    return list(session.execute(stmt).scalars().all())


def get_organizations(
    session: Session,
    search: str | None = None,
    limit: int = 100,
) -> list[Organization]:
    """List organizations with optional search."""
    stmt = select(Organization).order_by(Organization.last_seen_at.desc())
    if search:
        escaped = _escape_ilike(search)
        stmt = stmt.where(Organization.display_name.ilike(f"%{escaped}%", escape="\\"))
    stmt = stmt.limit(limit)
    return list(session.execute(stmt).scalars().all())


def get_organization_contracts(
    session: Session,
    buyer_ico: str,
    limit: int = 50,
) -> list[Contract]:
    """Get contracts for an organization (by buyer IČO)."""
    stmt = (
        select(Contract)
        .where(Contract.buyer_ico == buyer_ico)
        .order_by(Contract.publication_date.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())


def get_suppliers(
    session: Session,
    search: str | None = None,
    show_natural_persons: bool = False,
    limit: int = 100,
) -> list[Supplier]:
    """List suppliers with optional search, hiding natural persons by default."""
    stmt = select(Supplier).order_by(Supplier.last_seen_at.desc())
    if not show_natural_persons:
        stmt = stmt.where(Supplier.is_probable_natural_person == False)  # noqa: E712
    if search:
        escaped = _escape_ilike(search)
        stmt = stmt.where(Supplier.display_name.ilike(f"%{escaped}%", escape="\\"))
    stmt = stmt.limit(limit)
    return list(session.execute(stmt).scalars().all())


def get_supplier_contracts(
    session: Session,
    supplier_ico: str,
    limit: int = 50,
) -> list[Contract]:
    """Get contracts for a supplier (by supplier IČO)."""
    stmt = (
        select(Contract)
        .where(Contract.supplier_ico == supplier_ico)
        .order_by(Contract.publication_date.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())


def get_ingestion_history(session: Session, limit: int = 20) -> list[IngestionRun]:
    """Get recent ingestion runs."""
    stmt = select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit)
    return list(session.execute(stmt).scalars().all())


def get_flag_definitions(session: Session) -> list[RiskFlag]:
    """Get all active flag definitions."""
    stmt = select(RiskFlag).where(RiskFlag.is_active.is_(True)).order_by(RiskFlag.id)
    return list(session.execute(stmt).scalars().all())
