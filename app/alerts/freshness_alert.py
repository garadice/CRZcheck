"""Freshness alerting — detect when ingestion stops running.

Standalone CLI that checks data freshness and exits non-zero if stale.
Designed to be called from cron for lightweight monitoring.

Usage:
    python -m app.alerts.freshness_alert

Exit codes:
    0 — data is fresh
    1 — data is stale or no successful ingestion found
    2 — unexpected error (DB unreachable, etc.)
"""

from __future__ import annotations

import logging
import sys

from app.db.session import get_session_factory
from app.flags.freshness import check_data_freshness

logger = logging.getLogger(__name__)


def check_and_alert() -> bool:
    """Check data freshness and log the result.

    Returns:
        True if stale/no_data (should alert), False if fresh (OK).
    """
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        result = check_data_freshness(session)
        status = result["status"]

        if status == "fresh":
            logger.info(
                "Data fresh: last success %.1fh ago, %d records.",
                result["hours_since"],
                result["records_seen"],
            )
            return False

        # stale or no_data
        warning = result.get("warning", f"Status: {status}")
        logger.error("FRESHNESS ALERT: %s", warning)
        return True
    finally:
        session.close()


def main() -> None:
    """Entry point for CLI usage."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        is_stale = check_and_alert()
    except Exception:
        logger.exception("Freshness check failed with unexpected error")
        sys.exit(2)

    sys.exit(1 if is_stale else 0)


if __name__ == "__main__":
    main()
