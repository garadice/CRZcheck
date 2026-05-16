"""Tests for flag evaluation engine."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import JSON, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.db.models import Base, Contract, ContractRiskFlag, IngestionRun, RiskFlag
from app.flags.evaluate import (
    FlagMatch,
    check_invalid_ico_format,
    check_missing_buyer_ico,
    check_missing_price,
    check_missing_supplier,
    check_missing_supplier_ico,
    check_zero_price,
    compound_severity,
    evaluate_contract,
    run_flag_evaluation,
)


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return compiler.process(JSON(), **kw)


# ── Fixtures ──────────────────────────────────────────────────────────────────


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


def _make_contract(**overrides) -> Contract:
    """Create a fully-populated Contract with sensible defaults.

    Any field can be overridden via kwargs.
    """
    defaults = dict(
        crz_contract_id="CRZ-001",
        title="Testovacia zmluva",
        subject="Predmet zmluvy",
        buyer_name="Ministerstvo financií SR",
        buyer_ico="00123456",
        buyer_address="Štefánikova 1, Bratislava",
        supplier_name="ABC Company s.r.o.",
        supplier_ico="12345678",
        supplier_address="Hlavná 5, Košice",
        contract_date=date(2025, 1, 15),
        publication_date=datetime(2025, 1, 20, 10, 0, 0),
        price_contract=Decimal("10000.00"),
        price_total=Decimal("12000.00"),
        currency="EUR",
        source_export_date=date(2025, 1, 20),
        crz_detail_url="https://www.crz.gov.sk/index.php?ID=CRZ-001",
    )
    defaults.update(overrides)
    return Contract(**defaults)


# ── check_missing_price ───────────────────────────────────────────────────────


class TestCheckMissingPrice:
    def test_fires_when_both_prices_null(self):
        c = _make_contract(price_total=None, price_contract=None)
        result = check_missing_price(c)
        assert result is not None
        assert result.flag_code == "MISSING_PRICE"
        assert result.severity == "medium"

    def test_does_not_fire_when_price_total_set(self):
        c = _make_contract(price_total=Decimal("100"), price_contract=None)
        assert check_missing_price(c) is None

    def test_does_not_fire_when_price_contract_set(self):
        c = _make_contract(price_total=None, price_contract=Decimal("100"))
        assert check_missing_price(c) is None

    def test_does_not_fire_when_both_set(self):
        c = _make_contract(price_total=Decimal("100"), price_contract=Decimal("80"))
        assert check_missing_price(c) is None


# ── check_zero_price ──────────────────────────────────────────────────────────


class TestCheckZeroPrice:
    def test_fires_when_price_total_zero(self):
        c = _make_contract(price_total=Decimal("0"), price_contract=None)
        result = check_zero_price(c)
        assert result is not None
        assert result.flag_code == "ZERO_PRICE"
        assert result.severity == "low"

    def test_fires_when_price_contract_zero(self):
        c = _make_contract(price_total=None, price_contract=Decimal("0"))
        result = check_zero_price(c)
        assert result is not None
        assert result.flag_code == "ZERO_PRICE"

    def test_does_not_fire_when_price_positive(self):
        c = _make_contract(price_total=Decimal("100"), price_contract=Decimal("80"))
        assert check_zero_price(c) is None

    def test_does_not_fire_when_prices_null(self):
        c = _make_contract(price_total=None, price_contract=None)
        # Zero price should NOT fire when both are None (that's MISSING_PRICE)
        assert check_zero_price(c) is None


# ── check_missing_supplier ────────────────────────────────────────────────────


class TestCheckMissingSupplier:
    def test_fires_when_supplier_name_none(self):
        c = _make_contract(supplier_name=None)
        result = check_missing_supplier(c)
        assert result is not None
        assert result.flag_code == "MISSING_SUPPLIER"
        assert result.severity == "medium"

    def test_fires_when_supplier_name_empty(self):
        c = _make_contract(supplier_name="")
        assert check_missing_supplier(c) is not None

    def test_fires_when_supplier_name_whitespace(self):
        c = _make_contract(supplier_name="   ")
        assert check_missing_supplier(c) is not None

    def test_does_not_fire_when_supplier_name_present(self):
        c = _make_contract(supplier_name="ABC s.r.o.")
        assert check_missing_supplier(c) is None


# ── check_missing_supplier_ico ────────────────────────────────────────────────


class TestCheckMissingSupplierIco:
    def test_fires_when_supplier_ico_none(self):
        c = _make_contract(supplier_ico=None)
        result = check_missing_supplier_ico(c)
        assert result is not None
        assert result.flag_code == "MISSING_SUPPLIER_ICO"
        assert result.severity == "medium"

    def test_fires_when_supplier_ico_empty(self):
        c = _make_contract(supplier_ico="")
        assert check_missing_supplier_ico(c) is not None

    def test_fires_when_supplier_ico_whitespace(self):
        c = _make_contract(supplier_ico="  ")
        assert check_missing_supplier_ico(c) is not None

    def test_does_not_fire_when_supplier_ico_present(self):
        c = _make_contract(supplier_ico="12345678")
        assert check_missing_supplier_ico(c) is None


# ── check_invalid_ico_format ──────────────────────────────────────────────────


class TestCheckInvalidIcoFormat:
    def test_fires_when_supplier_ico_too_short(self):
        c = _make_contract(supplier_ico="1234567")  # 7 digits, not 8
        result = check_invalid_ico_format(c)
        assert result is not None
        assert result.flag_code == "INVALID_ICO_FORMAT"
        assert result.severity == "low"
        assert "supplier_ico" in result.evidence

    def test_fires_when_buyer_ico_too_long(self):
        c = _make_contract(buyer_ico="123456789")  # 9 digits, not 8
        result = check_invalid_ico_format(c)
        assert result is not None
        assert "buyer_ico" in result.evidence

    def test_fires_when_both_ico_invalid(self):
        c = _make_contract(supplier_ico="12", buyer_ico="12345")
        result = check_invalid_ico_format(c)
        assert result is not None
        assert "supplier_ico" in result.evidence
        assert "buyer_ico" in result.evidence

    def test_does_not_fire_when_both_valid(self):
        c = _make_contract(supplier_ico="12345678", buyer_ico="87654321")
        assert check_invalid_ico_format(c) is None

    def test_does_not_fire_when_ico_none(self):
        c = _make_contract(supplier_ico=None, buyer_ico=None)
        # None IČO is handled by MISSING_*_ICO flags, not this one
        assert check_invalid_ico_format(c) is None

    def test_does_not_fire_when_ico_empty(self):
        c = _make_contract(supplier_ico="", buyer_ico="")
        assert check_invalid_ico_format(c) is None


# ── check_missing_buyer_ico ───────────────────────────────────────────────────


class TestCheckMissingBuyerIco:
    def test_fires_when_buyer_ico_none(self):
        c = _make_contract(buyer_ico=None)
        result = check_missing_buyer_ico(c)
        assert result is not None
        assert result.flag_code == "MISSING_BUYER_ICO"
        assert result.severity == "medium"

    def test_fires_when_buyer_ico_empty(self):
        c = _make_contract(buyer_ico="")
        assert check_missing_buyer_ico(c) is not None

    def test_fires_when_buyer_ico_whitespace(self):
        c = _make_contract(buyer_ico="  ")
        assert check_missing_buyer_ico(c) is not None

    def test_does_not_fire_when_buyer_ico_present(self):
        c = _make_contract(buyer_ico="87654321")
        assert check_missing_buyer_ico(c) is None


# ── evaluate_contract ─────────────────────────────────────────────────────────


class TestEvaluateContract:
    def test_clean_contract_no_flags(self):
        c = _make_contract()
        matches = evaluate_contract(c)
        assert len(matches) == 0

    def test_all_fields_missing_triggers_many_flags(self):
        c = _make_contract(
            price_total=None,
            price_contract=None,
            supplier_name=None,
            supplier_ico=None,
            buyer_ico=None,
        )
        matches = evaluate_contract(c)
        flag_codes = {m.flag_code for m in matches}
        assert "MISSING_PRICE" in flag_codes
        assert "MISSING_SUPPLIER" in flag_codes
        assert "MISSING_SUPPLIER_ICO" in flag_codes
        assert "MISSING_BUYER_ICO" in flag_codes
        # INVALID_ICO_FORMAT should NOT fire (no ICO to validate)
        assert "INVALID_ICO_FORMAT" not in flag_codes

    def test_zero_price_and_missing_ico(self):
        c = _make_contract(
            price_total=Decimal("0"),
            supplier_ico=None,
            buyer_ico=None,
        )
        matches = evaluate_contract(c)
        flag_codes = {m.flag_code for m in matches}
        assert "ZERO_PRICE" in flag_codes
        assert "MISSING_SUPPLIER_ICO" in flag_codes
        assert "MISSING_BUYER_ICO" in flag_codes


# ── compound_severity ─────────────────────────────────────────────────────────


class TestCompoundSeverity:
    def test_empty_list_returns_none(self):
        assert compound_severity([]) == "none"

    def test_single_low_flag(self):
        flags = [FlagMatch("X", "low", "test")]
        assert compound_severity(flags) == "low"

    def test_single_medium_flag(self):
        flags = [FlagMatch("X", "medium", "test")]
        assert compound_severity(flags) == "medium"

    def test_two_medium_flags(self):
        flags = [FlagMatch("A", "medium", "t1"), FlagMatch("B", "medium", "t2")]
        assert compound_severity(flags) == "medium"

    def test_three_mixed_flags_elevates_to_high(self):
        flags = [
            FlagMatch("A", "low", "t1"),
            FlagMatch("B", "low", "t2"),
            FlagMatch("C", "low", "t3"),
        ]
        assert compound_severity(flags) == "high"

    def test_four_flags_always_high(self):
        flags = [
            FlagMatch("A", "low", "t1"),
            FlagMatch("B", "medium", "t2"),
            FlagMatch("C", "low", "t3"),
            FlagMatch("D", "low", "t4"),
        ]
        assert compound_severity(flags) == "high"

    def test_dict_input_two_flags(self):
        flags = [{"severity": "low"}, {"severity": "medium"}]
        assert compound_severity(flags) == "medium"

    def test_dict_input_three_flags_elevates(self):
        flags = [
            {"severity": "low"},
            {"severity": "low"},
            {"severity": "low"},
        ]
        assert compound_severity(flags) == "high"

    def test_mixed_flag_match_and_dict(self):
        flags = [
            FlagMatch("A", "low", "t1"),
            {"severity": "medium"},
            FlagMatch("C", "low", "t3"),
        ]
        assert compound_severity(flags) == "high"


# ── run_flag_evaluation (integration) ─────────────────────────────────────────


class TestRunFlagEvaluation:
    def test_creates_flags_for_problematic_contract(self, session):
        # Create a contract with missing data
        contract = _make_contract(
            price_total=None,
            price_contract=None,
            supplier_ico=None,
            buyer_ico=None,
        )
        session.add(contract)

        # Create ingestion run
        run = IngestionRun(status="completed")
        session.add(run)
        session.flush()
        run_id = run.id

        checked, created = run_flag_evaluation(session, run_id)
        assert checked == 1
        assert created >= 3  # MISSING_PRICE, MISSING_SUPPLIER_ICO, MISSING_BUYER_ICO

        # Verify flags in DB
        stmt = select(ContractRiskFlag).where(ContractRiskFlag.source_run_id == run_id)
        flags = session.execute(stmt).scalars().all()
        assert len(flags) >= 3

    def test_clean_contract_gets_no_flags(self, session):
        contract = _make_contract()
        session.add(contract)

        run = IngestionRun(status="completed")
        session.add(run)
        session.flush()

        checked, created = run_flag_evaluation(session, run.id)
        assert checked == 1
        assert created == 0

    def test_reflag_replaces_old_flags(self, session):
        contract = _make_contract(
            price_total=None,
            price_contract=None,
            supplier_ico=None,
        )
        session.add(contract)

        # First run
        run1 = IngestionRun(status="completed")
        session.add(run1)
        session.flush()
        run_flag_evaluation(session, run1.id)

        old_flags = (
            session.execute(
                select(ContractRiskFlag).where(ContractRiskFlag.source_run_id == run1.id)
            )
            .scalars()
            .all()
        )
        assert len(old_flags) >= 2

        # Second run — should replace old flags
        run2 = IngestionRun(status="completed")
        session.add(run2)
        session.flush()
        run_flag_evaluation(session, run2.id)

        # Old flags should be gone (source_run_id != run2.id → deleted)
        old_flags_after = (
            session.execute(
                select(ContractRiskFlag).where(ContractRiskFlag.source_run_id == run1.id)
            )
            .scalars()
            .all()
        )
        assert len(old_flags_after) == 0

        # New flags should exist
        new_flags = (
            session.execute(
                select(ContractRiskFlag).where(ContractRiskFlag.source_run_id == run2.id)
            )
            .scalars()
            .all()
        )
        assert len(new_flags) >= 2

    def test_flag_removed_when_data_fixed(self, session):
        contract = _make_contract(
            price_total=None,
            price_contract=None,
        )
        session.add(contract)

        # First run — flags MISSING_PRICE
        run1 = IngestionRun(status="completed")
        session.add(run1)
        session.flush()
        _, created1 = run_flag_evaluation(session, run1.id)
        assert created1 >= 1

        # Fix the data
        contract.price_total = Decimal("1000")
        session.flush()

        # Second run — MISSING_PRICE should not appear
        run2 = IngestionRun(status="completed")
        session.add(run2)
        session.flush()
        _, created2 = run_flag_evaluation(session, run2.id)
        assert created2 == 0

    def test_seeds_flag_definitions(self, session):
        """run_flag_evaluation should auto-create RiskFlag definitions in DB."""
        contract = _make_contract(price_total=None, price_contract=None)
        session.add(contract)

        run = IngestionRun(status="completed")
        session.add(run)
        session.flush()

        run_flag_evaluation(session, run.id)

        flag_defs = session.execute(select(RiskFlag)).scalars().all()
        assert len(flag_defs) >= 6
        flag_codes = {f.flag_code for f in flag_defs}
        assert "MISSING_PRICE" in flag_codes
        assert "ZERO_PRICE" in flag_codes
        assert "MISSING_SUPPLIER" in flag_codes
        assert "MISSING_SUPPLIER_ICO" in flag_codes
        assert "INVALID_ICO_FORMAT" in flag_codes
        assert "MISSING_BUYER_ICO" in flag_codes
