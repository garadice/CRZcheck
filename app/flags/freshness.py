"""Data freshness warning — check how recent the last successful ingestion is."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IngestionRun

# Threshold in hours after which data is considered stale
STALE_THRESHOLD_HOURS = 48.0


def check_data_freshness(session: Session) -> dict:
    """Check data freshness based on the last successful ingestion run.

    Returns a dict with:
        status: "fresh" | "stale" | "no_data"
        warning: str (only present when status is "stale" or "no_data")
        last_success: datetime (only present when a successful run exists)
        hours_since: float (only present when a successful run exists)
        records_seen: int (only present when a successful run exists)

    Args:
        session: SQLAlchemy session
    """
    stmt = (
        select(IngestionRun)
        .where(IngestionRun.status == "completed")
        .order_by(IngestionRun.finished_at.desc())
        .limit(1)
    )
    last_success = session.execute(stmt).scalar_one_or_none()

    if last_success is None:
        return {
            "status": "no_data",
            "warning": "Zatiaľ nebola zaznamenaná žiadna úspešná ingestia dát.",
        }

    now = datetime.now(UTC)
    finished = last_success.finished_at
    if finished and finished.tzinfo is None:
        finished = finished.replace(tzinfo=UTC)
    hours_since = (now - finished).total_seconds() / 3600

    result: dict = {
        "status": "fresh",
        "last_success": last_success.finished_at,
        "hours_since": round(hours_since, 1),
        "records_seen": last_success.records_seen,
    }

    if hours_since > STALE_THRESHOLD_HOURS:
        result["status"] = "stale"
        result["warning"] = (
            f"Posledná úspešná ingestia bola pred {hours_since:.0f} hodinami "
            f"(> {STALE_THRESHOLD_HOURS:.0f}h). Dáta môžu byť neaktuálne."
        )

    return result
