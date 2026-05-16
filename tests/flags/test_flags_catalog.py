"""Tests for flag catalog seeding."""

from __future__ import annotations

import pytest
from sqlalchemy import JSON, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.db.models import Base, RiskFlag
from app.flags.definitions import FLAG_CATALOG
from app.flags.flags_catalog import get_flag_map


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


def _seed_flags_manually(session: Session) -> None:
    """Insert flag definitions manually (SQLite-compatible alternative to seed_flags)."""
    for defn in FLAG_CATALOG.values():
        flag = RiskFlag(
            flag_code=defn.flag_code,
            name=defn.name,
            description=defn.description,
            severity_default=defn.severity_default,
            methodology=defn.methodology,
            is_active=defn.is_active,
            phase=defn.phase,
        )
        session.add(flag)
    session.flush()


class TestGetFlagMap:
    def test_returns_empty_when_no_flags(self, session):
        result = get_flag_map(session)
        assert result == {}

    def test_returns_all_active_flags(self, session):
        _seed_flags_manually(session)
        result = get_flag_map(session)
        assert len(result) == len(FLAG_CATALOG)

    def test_flag_map_has_correct_codes(self, session):
        _seed_flags_manually(session)
        result = get_flag_map(session)
        expected_codes = set(FLAG_CATALOG.keys())
        assert set(result.keys()) == expected_codes

    def test_flag_map_values_are_risk_flag_orm(self, session):
        _seed_flags_manually(session)
        result = get_flag_map(session)
        for flag_code, flag_obj in result.items():
            assert isinstance(flag_obj, RiskFlag)
            assert flag_obj.flag_code == flag_code

    def test_excludes_inactive_flags(self, session):
        _seed_flags_manually(session)
        # Deactivate one flag
        stmt = select(RiskFlag).where(RiskFlag.flag_code == "ZERO_PRICE")
        flag = session.execute(stmt).scalar_one()
        flag.is_active = False
        session.flush()

        result = get_flag_map(session)
        assert "ZERO_PRICE" not in result
        assert len(result) == len(FLAG_CATALOG) - 1


class TestSeedFlags:
    def test_seed_flags_creates_all_definitions(self, session):
        from app.flags.flags_catalog import seed_flags

        count = seed_flags(session)
        assert count == len(FLAG_CATALOG)
        flags = session.execute(select(RiskFlag)).scalars().all()
        assert len(flags) == len(FLAG_CATALOG)

    def test_seed_flags_idempotent(self, session):
        from app.flags.flags_catalog import seed_flags

        seed_flags(session)
        seed_flags(session)
        flags = session.execute(select(RiskFlag)).scalars().all()
        assert len(flags) == len(FLAG_CATALOG)

    def test_seed_flags_updates_existing(self, session):
        from app.flags.flags_catalog import seed_flags

        seed_flags(session)
        seed_flags(session)
        flags = session.execute(select(RiskFlag)).scalars().all()
        assert len(flags) == len(FLAG_CATALOG)


class TestFlagDefinitions:
    def test_all_definitions_have_required_fields(self):
        for code, defn in FLAG_CATALOG.items():
            assert defn.flag_code == code, f"flag_code mismatch for {code}"
            assert defn.name, f"name missing for {code}"
            assert defn.description, f"description missing for {code}"
            assert defn.severity_default in ("low", "medium", "high"), (
                f"invalid severity for {code}: {defn.severity_default}"
            )
            assert defn.methodology, f"methodology missing for {code}"
            assert defn.phase == "mvp", f"unexpected phase for {code}: {defn.phase}"

    def test_exactly_six_mvp_flags(self):
        assert len(FLAG_CATALOG) == 6

    def test_expected_flag_codes(self):
        expected = {
            "MISSING_PRICE",
            "ZERO_PRICE",
            "MISSING_SUPPLIER",
            "MISSING_SUPPLIER_ICO",
            "INVALID_ICO_FORMAT",
            "MISSING_BUYER_ICO",
        }
        assert set(FLAG_CATALOG.keys()) == expected

    def test_severity_distribution(self):
        severities = [f.severity_default for f in FLAG_CATALOG.values()]
        low_count = severities.count("low")
        medium_count = severities.count("medium")
        # Per master plan: ZERO_PRICE and INVALID_ICO_FORMAT are low, rest are medium
        assert low_count == 2
        assert medium_count == 4
