"""Tests for data freshness warning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.db.models import Base, IngestionRun
from app.flags.freshness import STALE_THRESHOLD_HOURS, check_data_freshness


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


def _make_run(
    status: str = "completed",
    finished_at: datetime | None = None,
    records_seen: int = 100,
) -> IngestionRun:
    return IngestionRun(
        status=status,
        finished_at=finished_at or datetime.now(UTC),
        records_seen=records_seen,
        started_at=datetime.now(UTC) - timedelta(minutes=5),
    )


class TestCheckDataFreshness:
    def test_no_runs_returns_no_data(self, session):
        result = check_data_freshness(session)
        assert result["status"] == "no_data"
        assert "warning" in result
        assert "last_success" not in result

    def test_recent_run_returns_fresh(self, session):
        recent_time = datetime.now(UTC) - timedelta(hours=2)
        run = _make_run(finished_at=recent_time)
        session.add(run)
        session.flush()

        result = check_data_freshness(session)
        assert result["status"] == "fresh"
        assert "warning" not in result
        assert result["last_success"] == recent_time
        assert result["hours_since"] < STALE_THRESHOLD_HOURS
        assert result["records_seen"] == 100

    def test_stale_run_returns_stale(self, session):
        stale_time = datetime.now(UTC) - timedelta(hours=72)
        run = _make_run(finished_at=stale_time)
        session.add(run)
        session.flush()

        result = check_data_freshness(session)
        assert result["status"] == "stale"
        assert "warning" in result
        assert result["hours_since"] > STALE_THRESHOLD_HOURS

    def test_exactly_48h_is_still_fresh(self, session):
        # Just under 48h should be fresh
        almost_stale = datetime.now(UTC) - timedelta(hours=47, minutes=59)
        run = _make_run(finished_at=almost_stale)
        session.add(run)
        session.flush()

        result = check_data_freshness(session)
        assert result["status"] == "fresh"

    def test_ignores_failed_runs(self, session):
        # Failed run should not count
        failed_run = _make_run(status="failed", finished_at=datetime.now(UTC))
        session.add(failed_run)
        session.flush()

        result = check_data_freshness(session)
        assert result["status"] == "no_data"

    def test_uses_most_recent_completed_run(self, session):
        # Old completed run
        old_run = _make_run(
            finished_at=datetime.now(UTC) - timedelta(hours=72),
            records_seen=50,
        )
        session.add(old_run)

        # Recent completed run
        recent_run = _make_run(
            finished_at=datetime.now(UTC) - timedelta(hours=1),
            records_seen=200,
        )
        session.add(recent_run)
        session.flush()

        result = check_data_freshness(session)
        assert result["status"] == "fresh"
        assert result["records_seen"] == 200

    def test_stale_warning_contains_hours(self, session):
        stale_time = datetime.now(UTC) - timedelta(hours=96)
        run = _make_run(finished_at=stale_time)
        session.add(run)
        session.flush()

        result = check_data_freshness(session)
        assert "96" in result["warning"]
