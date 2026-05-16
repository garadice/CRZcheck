"""Seed flag definitions into the database (idempotent)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RiskFlag
from app.flags.definitions import FLAG_CATALOG

logger = logging.getLogger(__name__)


def seed_flags(session: Session) -> int:
    """Seed all flag definitions from FLAG_CATALOG into the risk_flags table.

    Uses a dialect-agnostic select + update/insert pattern for idempotency.
    Updates name, description, severity_default, methodology, is_active, phase
    on conflict, but never changes flag_code (the unique key).

    Args:
        session: SQLAlchemy session

    Returns:
        Number of flags seeded/upserted.
    """
    count = 0
    for defn in FLAG_CATALOG.values():
        existing = session.execute(
            select(RiskFlag).where(RiskFlag.flag_code == defn.flag_code)
        ).scalar_one_or_none()
        if existing:
            existing.name = defn.name
            existing.description = defn.description
            existing.severity_default = defn.severity_default
            existing.methodology = defn.methodology
            existing.is_active = defn.is_active
            existing.phase = defn.phase
        else:
            session.add(
                RiskFlag(
                    flag_code=defn.flag_code,
                    name=defn.name,
                    description=defn.description,
                    severity_default=defn.severity_default,
                    methodology=defn.methodology,
                    is_active=defn.is_active,
                    phase=defn.phase,
                )
            )
        count += 1

    session.flush()
    logger.info(f"Seeded {count} flag definitions")
    return count


def get_flag_map(session: Session) -> dict[str, RiskFlag]:
    """Load all active RiskFlag ORM objects as a dict keyed by flag_code.

    Args:
        session: SQLAlchemy session

    Returns:
        Dict mapping flag_code → RiskFlag ORM object.
    """
    stmt = select(RiskFlag).where(RiskFlag.is_active.is_(True))
    flags = session.execute(stmt).scalars().all()
    return {f.flag_code: f for f in flags}
