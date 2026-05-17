from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import JSON, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.dashboard.components.queries import (
    _escape_ilike,
    get_contract_attachments,
    get_contract_detail,
    get_contract_flags,
    get_flag_definitions,
    get_flagged_contracts,
    get_ingestion_history,
    get_organization_contracts,
    get_organizations,
    get_overview_stats,
    get_supplier_contracts,
    get_suppliers,
    search_contracts,
)
from app.db.models import (
    Base,
    Contract,
    ContractAttachmentMetadata,
    ContractRiskFlag,
    IngestionRun,
    Organization,
    RiskFlag,
    Supplier,
)
from app.flags.flags_catalog import seed_flags


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


def _make_contract(
    crz_id: str,
    title: str = "Test Contract",
    buyer_name: str = "Buyer A",
    buyer_ico: str = "11111111",
    supplier_name: str = "Supplier X",
    supplier_ico: str = "22222222",
    price_total: Decimal | None = Decimal("10000"),
    publication_date: datetime | None = datetime(2026, 1, 15),
) -> Contract:
    return Contract(
        crz_contract_id=crz_id,
        title=title,
        buyer_name=buyer_name,
        buyer_ico=buyer_ico,
        supplier_name=supplier_name,
        supplier_ico=supplier_ico,
        price_total=price_total,
        publication_date=publication_date,
    )


@pytest.fixture()
def seeded_session(session):
    c1 = _make_contract(
        "C001",
        title="Road construction",
        buyer_name="Ministry of Transport",
        buyer_ico="11111111",
        supplier_name="BuildCo s.r.o.",
        supplier_ico="33333333",
        price_total=Decimal("50000"),
        publication_date=datetime(2026, 3, 1),
    )
    c2 = _make_contract(
        "C002",
        title="IT services delivery",
        buyer_name="City Hall Bratislava",
        buyer_ico="44444444",
        supplier_name="TechCorp a.s.",
        supplier_ico="55555555",
        price_total=Decimal("120000"),
        publication_date=datetime(2026, 2, 15),
    )
    c3 = _make_contract(
        "C003",
        title="Office supplies",
        buyer_name="Ministry of Transport",
        buyer_ico="11111111",
        supplier_name="Paper Ltd.",
        supplier_ico="66666666",
        price_total=None,
        publication_date=datetime(2026, 1, 10),
    )
    session.add_all([c1, c2, c3])

    org1 = Organization(
        ico="11111111",
        display_name="Ministry of Transport",
        normalized_name="ministry of transport",
        last_seen_at=datetime(2026, 3, 1),
    )
    org2 = Organization(
        ico="44444444",
        display_name="City Hall Bratislava",
        normalized_name="city hall bratislava",
        last_seen_at=datetime(2026, 2, 15),
    )
    session.add_all([org1, org2])

    sup1 = Supplier(
        ico="33333333",
        display_name="BuildCo s.r.o.",
        normalized_name="buildco s.r.o.",
        is_probable_natural_person=False,
        last_seen_at=datetime(2026, 3, 1),
    )
    sup2 = Supplier(
        ico="55555555",
        display_name="TechCorp a.s.",
        normalized_name="techcorp a.s.",
        is_probable_natural_person=False,
        last_seen_at=datetime(2026, 2, 15),
    )
    sup3 = Supplier(
        ico=None,
        display_name="Ján Novák",
        normalized_name="ján novák",
        is_probable_natural_person=True,
        last_seen_at=datetime(2026, 1, 1),
    )
    session.add_all([sup1, sup2, sup3])

    run1 = IngestionRun(
        run_type="daily",
        started_at=datetime(2026, 3, 1, 10, 0),
        finished_at=datetime(2026, 3, 1, 11, 0),
        status="completed",
        records_seen=100,
        records_inserted=50,
        records_updated=50,
    )
    run2 = IngestionRun(
        run_type="daily",
        started_at=datetime(2026, 2, 1, 10, 0),
        finished_at=datetime(2026, 2, 1, 10, 30),
        status="completed",
        records_seen=80,
        records_inserted=30,
        records_updated=50,
    )
    session.add_all([run1, run2])
    session.flush()
    return session


@pytest.fixture()
def flagged_session(seeded_session):
    session = seeded_session
    seed_flags(session)
    session.flush()

    flags = {rf.flag_code: rf for rf in session.execute(select(RiskFlag)).scalars().all()}

    crf1 = ContractRiskFlag(
        crz_contract_id="C001",
        flag_id=flags["MISSING_PRICE"].id,
        severity="medium",
        reason="No price",
    )
    crf2 = ContractRiskFlag(
        crz_contract_id="C001",
        flag_id=flags["MISSING_SUPPLIER_ICO"].id,
        severity="medium",
        reason="No supplier ICO",
    )
    crf3 = ContractRiskFlag(
        crz_contract_id="C001",
        flag_id=flags["MISSING_BUYER_ICO"].id,
        severity="high",
        reason="No buyer ICO",
    )
    crf4 = ContractRiskFlag(
        crz_contract_id="C002",
        flag_id=flags["ZERO_PRICE"].id,
        severity="low",
        reason="Zero price",
    )
    session.add_all([crf1, crf2, crf3, crf4])
    session.flush()
    return session


class TestEscapeIlike:
    def test_escape_percent(self):
        assert _escape_ilike("100%") == "100\\%"

    def test_escape_underscore(self):
        assert _escape_ilike("test_value") == "test\\_value"

    def test_escape_backslash(self):
        assert _escape_ilike("a\\b") == "a\\\\b"

    def test_combination(self):
        assert _escape_ilike("100%_test\\") == "100\\%\\_test\\\\"

    def test_empty_string(self):
        assert _escape_ilike("") == ""

    def test_no_special_chars(self):
        assert _escape_ilike("hello") == "hello"

    def test_multiple_special(self):
        assert _escape_ilike("%_%") == "\\%\\_\\%"


class TestGetOverviewStats:
    def test_empty_db(self, session):
        stats = get_overview_stats(session)
        assert stats["total_contracts"] == 0
        assert stats["total_flagged"] == 0
        assert stats["total_organizations"] == 0
        assert stats["total_suppliers"] == 0
        assert stats["total_value"] == Decimal("0")

    def test_populated_db(self, seeded_session):
        stats = get_overview_stats(seeded_session)
        assert stats["total_contracts"] == 3
        assert stats["total_organizations"] == 2
        assert stats["total_suppliers"] == 3

    def test_total_value_sums_non_null(self, seeded_session):
        stats = get_overview_stats(seeded_session)
        assert stats["total_value"] == Decimal("50000") + Decimal("120000")

    def test_total_value_with_all_null_prices(self, session):
        c1 = _make_contract("C099", price_total=None)
        c2 = _make_contract("C098", price_total=None)
        session.add_all([c1, c2])
        session.flush()
        stats = get_overview_stats(session)
        assert stats["total_value"] == Decimal("0")

    def test_total_flagged(self, flagged_session):
        stats = get_overview_stats(flagged_session)
        assert stats["total_flagged"] == 2


class TestSearchContracts:
    def test_no_filters_returns_all(self, seeded_session):
        results = search_contracts(seeded_session)
        assert len(results) == 3
        assert results[0].crz_contract_id == "C001"
        assert results[1].crz_contract_id == "C002"
        assert results[2].crz_contract_id == "C003"

    def test_text_query_matches_title(self, seeded_session):
        results = search_contracts(seeded_session, query="Road")
        assert len(results) == 1
        assert results[0].title == "Road construction"

    def test_text_query_matches_supplier_name(self, seeded_session):
        results = search_contracts(seeded_session, query="TechCorp")
        assert len(results) == 1
        assert results[0].supplier_name == "TechCorp a.s."

    def test_text_query_matches_buyer_name(self, seeded_session):
        results = search_contracts(seeded_session, query="City Hall")
        assert len(results) == 1
        assert results[0].buyer_name == "City Hall Bratislava"

    def test_text_query_matches_crz_contract_id(self, seeded_session):
        results = search_contracts(seeded_session, query="C002")
        assert len(results) == 1
        assert results[0].crz_contract_id == "C002"

    def test_date_from_filter(self, seeded_session):
        results = search_contracts(seeded_session, date_from=date(2026, 2, 1))
        assert len(results) == 2
        ids = [r.crz_contract_id for r in results]
        assert "C001" in ids
        assert "C002" in ids

    def test_date_to_filter(self, seeded_session):
        results = search_contracts(seeded_session, date_to=date(2026, 2, 28))
        assert len(results) == 2
        ids = [r.crz_contract_id for r in results]
        assert "C002" in ids
        assert "C003" in ids

    def test_date_range_filter(self, seeded_session):
        results = search_contracts(
            seeded_session,
            date_from=date(2026, 2, 1),
            date_to=date(2026, 2, 28),
        )
        assert len(results) == 1
        assert results[0].crz_contract_id == "C002"

    def test_combined_text_and_date(self, seeded_session):
        results = search_contracts(
            seeded_session,
            query="Transport",
            date_from=date(2026, 2, 1),
        )
        assert len(results) == 1
        assert results[0].crz_contract_id == "C001"

    def test_limit(self, seeded_session):
        results = search_contracts(seeded_session, limit=2)
        assert len(results) == 2

    def test_no_results(self, seeded_session):
        results = search_contracts(seeded_session, query="nonexistent_xyz")
        assert results == []

    def test_case_insensitive(self, seeded_session):
        results = search_contracts(seeded_session, query="road")
        assert len(results) == 1


class TestGetFlaggedContracts:
    def test_returns_flagged_contracts(self, flagged_session):
        results = get_flagged_contracts(flagged_session)
        assert len(results) == 2
        ids = [r["contract"].crz_contract_id for r in results]
        assert "C001" in ids
        assert "C002" in ids

    def test_includes_compound_severity(self, flagged_session):
        results = get_flagged_contracts(flagged_session)
        by_id = {r["contract"].crz_contract_id: r for r in results}
        assert by_id["C001"]["compound_severity"] == "high"
        assert by_id["C002"]["compound_severity"] == "low"

    def test_c001_has_three_flags(self, flagged_session):
        results = get_flagged_contracts(flagged_session)
        by_id = {r["contract"].crz_contract_id: r for r in results}
        assert by_id["C001"]["flag_count"] == 3

    def test_severity_filter_high(self, flagged_session):
        results = get_flagged_contracts(flagged_session, severity_filter="high")
        ids = [r["contract"].crz_contract_id for r in results]
        assert "C001" in ids

    def test_severity_filter_medium(self, flagged_session):
        results = get_flagged_contracts(flagged_session, severity_filter="medium")
        ids = [r["contract"].crz_contract_id for r in results]
        assert "C001" in ids
        assert "C002" not in ids

    def test_flag_code_filter(self, flagged_session):
        results = get_flagged_contracts(flagged_session, flag_code_filter="ZERO_PRICE")
        assert len(results) == 1
        assert results[0]["contract"].crz_contract_id == "C002"

    def test_date_from_filter(self, flagged_session):
        results = get_flagged_contracts(flagged_session, date_from=date(2026, 2, 15))
        ids = [r["contract"].crz_contract_id for r in results]
        assert "C001" in ids

    def test_date_to_filter(self, flagged_session):
        results = get_flagged_contracts(flagged_session, date_to=date(2026, 2, 28))
        ids = [r["contract"].crz_contract_id for r in results]
        assert "C002" in ids

    def test_empty_result(self, session):
        results = get_flagged_contracts(session)
        assert results == []

    def test_includes_flags_list(self, flagged_session):
        results = get_flagged_contracts(flagged_session)
        by_id = {r["contract"].crz_contract_id: r for r in results}
        c001_flags = by_id["C001"]["flags"]
        assert len(c001_flags) == 3
        codes = {f["flag_code"] for f in c001_flags}
        assert "MISSING_PRICE" in codes
        assert "MISSING_SUPPLIER_ICO" in codes
        assert "MISSING_BUYER_ICO" in codes

    def test_three_flags_override_to_high(self, flagged_session):
        flags = {
            rf.flag_code: rf for rf in flagged_session.execute(select(RiskFlag)).scalars().all()
        }
        extra1 = ContractRiskFlag(
            crz_contract_id="C002",
            flag_id=flags["MISSING_PRICE"].id,
            severity="low",
            reason="Also missing price",
        )
        extra2 = ContractRiskFlag(
            crz_contract_id="C002",
            flag_id=flags["MISSING_SUPPLIER_ICO"].id,
            severity="low",
            reason="Also missing supplier ICO",
        )
        flagged_session.add_all([extra1, extra2])
        flagged_session.flush()

        results = get_flagged_contracts(flagged_session, severity_filter="high")
        ids = [r["contract"].crz_contract_id for r in results]
        assert "C002" in ids
        by_id = {r["contract"].crz_contract_id: r for r in results}
        assert by_id["C002"]["compound_severity"] == "high"

    def test_limit(self, flagged_session):
        results = get_flagged_contracts(flagged_session, limit=1)
        assert len(results) <= 1


class TestGetContractFlags:
    def test_with_flags(self, flagged_session):
        flags = get_contract_flags(flagged_session, "C001")
        assert len(flags) == 3
        assert all("flag_code" in f for f in flags)
        assert all("name" in f for f in flags)
        assert all("severity" in f for f in flags)
        assert all("reason" in f for f in flags)

    def test_without_flags(self, seeded_session):
        flags = get_contract_flags(seeded_session, "C003")
        assert flags == []

    def test_nonexistent_contract(self, session):
        flags = get_contract_flags(session, "NONEXIST")
        assert flags == []

    def test_flag_severity_values(self, flagged_session):
        flags = get_contract_flags(flagged_session, "C001")
        severities = {f["severity"] for f in flags}
        assert severities == {"medium", "high"}


class TestGetContractDetail:
    def test_existing_contract(self, seeded_session):
        contract = get_contract_detail(seeded_session, "C001")
        assert contract is not None
        assert contract.crz_contract_id == "C001"
        assert contract.title == "Road construction"

    def test_nonexistent_contract(self, session):
        contract = get_contract_detail(session, "NONEXIST")
        assert contract is None

    def test_returns_contract_fields(self, seeded_session):
        contract = get_contract_detail(seeded_session, "C002")
        assert contract.supplier_name == "TechCorp a.s."
        assert contract.price_total == Decimal("120000")


class TestGetContractAttachments:
    def test_with_attachments(self, seeded_session):
        att = ContractAttachmentMetadata(
            crz_contract_id="C001",
            attachment_id="att001",
            attachment_name="contract.pdf",
        )
        seeded_session.add(att)
        seeded_session.flush()

        result = get_contract_attachments(seeded_session, "C001")
        assert len(result) == 1
        assert result[0].attachment_name == "contract.pdf"

    def test_without_attachments(self, seeded_session):
        result = get_contract_attachments(seeded_session, "C001")
        assert result == []

    def test_nonexistent_contract(self, session):
        result = get_contract_attachments(session, "NONEXIST")
        assert result == []

    def test_multiple_attachments(self, seeded_session):
        atts = [
            ContractAttachmentMetadata(
                crz_contract_id="C001",
                attachment_id=f"att00{i}",
                attachment_name=f"file{i}.pdf",
            )
            for i in range(1, 4)
        ]
        seeded_session.add_all(atts)
        seeded_session.flush()

        result = get_contract_attachments(seeded_session, "C001")
        assert len(result) == 3


class TestGetOrganizations:
    def test_returns_all_sorted_by_last_seen(self, seeded_session):
        results = get_organizations(seeded_session)
        assert len(results) == 2
        assert results[0].display_name == "Ministry of Transport"
        assert results[1].display_name == "City Hall Bratislava"

    def test_search_by_name(self, seeded_session):
        results = get_organizations(seeded_session, search="Transport")
        assert len(results) == 1
        assert results[0].display_name == "Ministry of Transport"

    def test_search_case_insensitive(self, seeded_session):
        results = get_organizations(seeded_session, search="city hall")
        assert len(results) == 1
        assert results[0].display_name == "City Hall Bratislava"

    def test_limit(self, seeded_session):
        results = get_organizations(seeded_session, limit=1)
        assert len(results) == 1

    def test_no_results_search(self, seeded_session):
        results = get_organizations(seeded_session, search="nonexistent_xyz")
        assert results == []

    def test_empty_db(self, session):
        results = get_organizations(session)
        assert results == []


class TestGetOrganizationContracts:
    def test_returns_matching_contracts(self, seeded_session):
        results = get_organization_contracts(seeded_session, "11111111")
        assert len(results) == 2
        ids = [r.crz_contract_id for r in results]
        assert "C001" in ids
        assert "C003" in ids

    def test_sorted_by_publication_date_desc(self, seeded_session):
        results = get_organization_contracts(seeded_session, "11111111")
        assert results[0].publication_date > results[1].publication_date

    def test_no_matching_contracts(self, seeded_session):
        results = get_organization_contracts(seeded_session, "99999999")
        assert results == []

    def test_limit(self, seeded_session):
        results = get_organization_contracts(seeded_session, "11111111", limit=1)
        assert len(results) == 1


class TestGetSuppliers:
    def test_hides_natural_persons_by_default(self, seeded_session):
        results = get_suppliers(seeded_session)
        names = [s.display_name for s in results]
        assert "Ján Novák" not in names
        assert len(results) == 2

    def test_show_natural_persons(self, seeded_session):
        results = get_suppliers(seeded_session, show_natural_persons=True)
        assert len(results) == 3
        names = [s.display_name for s in results]
        assert "Ján Novák" in names

    def test_search_by_name(self, seeded_session):
        results = get_suppliers(seeded_session, search="BuildCo")
        assert len(results) == 1
        assert results[0].display_name == "BuildCo s.r.o."

    def test_search_case_insensitive(self, seeded_session):
        results = get_suppliers(seeded_session, search="techcorp")
        assert len(results) == 1
        assert results[0].display_name == "TechCorp a.s."

    def test_limit(self, seeded_session):
        results = get_suppliers(seeded_session, show_natural_persons=True, limit=2)
        assert len(results) == 2

    def test_empty_db(self, session):
        results = get_suppliers(session)
        assert results == []

    def test_search_no_results(self, seeded_session):
        results = get_suppliers(seeded_session, search="nonexistent_xyz")
        assert results == []


class TestGetSupplierContracts:
    def test_returns_matching_contracts(self, seeded_session):
        results = get_supplier_contracts(seeded_session, "33333333")
        assert len(results) == 1
        assert results[0].crz_contract_id == "C001"

    def test_no_matching(self, seeded_session):
        results = get_supplier_contracts(seeded_session, "99999999")
        assert results == []

    def test_limit(self, seeded_session):
        results = get_supplier_contracts(seeded_session, "33333333", limit=0)
        assert len(results) == 0

    def test_sorted_by_publication_date_desc(self, seeded_session):
        extra = _make_contract(
            "C004",
            supplier_ico="33333333",
            publication_date=datetime(2026, 4, 1),
        )
        seeded_session.add(extra)
        seeded_session.flush()

        results = get_supplier_contracts(seeded_session, "33333333")
        assert len(results) == 2
        assert results[0].crz_contract_id == "C004"


class TestGetIngestionHistory:
    def test_returns_runs_sorted_desc(self, seeded_session):
        results = get_ingestion_history(seeded_session)
        assert len(results) == 2
        assert results[0].started_at > results[1].started_at

    def test_empty_db(self, session):
        results = get_ingestion_history(session)
        assert results == []

    def test_limit(self, seeded_session):
        results = get_ingestion_history(seeded_session, limit=1)
        assert len(results) == 1

    def test_includes_status(self, seeded_session):
        results = get_ingestion_history(seeded_session)
        assert all(r.status == "completed" for r in results)


class TestGetFlagDefinitions:
    def test_returns_active_flags(self, session):
        seed_flags(session)
        session.flush()

        results = get_flag_definitions(session)
        assert len(results) == 6
        assert all(f.is_active for f in results)

    def test_ordered_by_id(self, session):
        seed_flags(session)
        session.flush()

        results = get_flag_definitions(session)
        ids = [f.id for f in results]
        assert ids == sorted(ids)

    def test_empty_db(self, session):
        results = get_flag_definitions(session)
        assert results == []

    def test_excludes_inactive(self, session):
        seed_flags(session)
        session.flush()

        flag = session.execute(select(RiskFlag)).scalars().first()
        flag.is_active = False
        session.flush()

        results = get_flag_definitions(session)
        assert len(results) == 5

    def test_includes_all_flag_codes(self, session):
        seed_flags(session)
        session.flush()

        results = get_flag_definitions(session)
        codes = {f.flag_code for f in results}
        expected = {
            "MISSING_PRICE",
            "ZERO_PRICE",
            "MISSING_SUPPLIER",
            "MISSING_SUPPLIER_ICO",
            "INVALID_ICO_FORMAT",
            "MISSING_BUYER_ICO",
        }
        assert codes == expected
