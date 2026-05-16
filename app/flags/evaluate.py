"""Flag evaluation engine — evaluates risk flags against contract data."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Contract, ContractRiskFlag, RiskFlag
from app.flags.definitions import FLAG_CATALOG, get_flag_by_code

logger = logging.getLogger(__name__)


@dataclass
class FlagMatch:
    """Result of a single flag evaluation against a contract."""

    flag_code: str
    severity: str
    reason: str
    evidence: dict = field(default_factory=dict)


def _is_empty(value: str | None) -> bool:
    """Check if a string value is None or whitespace-only."""
    return value is None or not value.strip()


def check_missing_price(contract: Contract) -> FlagMatch | None:
    """Flag contracts with no price information at all."""
    if contract.price_total is None and contract.price_contract is None:
        return FlagMatch(
            flag_code="MISSING_PRICE",
            severity="medium",
            reason="Zmluva neobsahuje žiadnu informáciu o cene.",
            evidence={"price_total": None, "price_contract": None},
        )
    return None


def check_zero_price(contract: Contract) -> FlagMatch | None:
    """Flag contracts with zero price."""
    price = contract.price_total if contract.price_total is not None else contract.price_contract
    if price is not None and price == Decimal("0"):
        return FlagMatch(
            flag_code="ZERO_PRICE",
            severity="low",
            reason="Uvedená cena je nulová.",
            evidence={
                "price_total": str(contract.price_total)
                if contract.price_total is not None
                else None,
                "price_contract": str(contract.price_contract)
                if contract.price_contract is not None
                else None,
            },
        )
    return None


def check_missing_supplier(contract: Contract) -> FlagMatch | None:
    """Flag contracts with no supplier name."""
    if _is_empty(contract.supplier_name):
        return FlagMatch(
            flag_code="MISSING_SUPPLIER",
            severity="medium",
            reason="Zmluva neobsahuje názov dodávateľa.",
            evidence={"supplier_name": contract.supplier_name},
        )
    return None


def check_missing_supplier_ico(contract: Contract) -> FlagMatch | None:
    """Flag contracts with no supplier IČO."""
    if _is_empty(contract.supplier_ico):
        return FlagMatch(
            flag_code="MISSING_SUPPLIER_ICO",
            severity="medium",
            reason="Zmluva neobsahuje IČO dodávateľa.",
            evidence={"supplier_ico": contract.supplier_ico},
        )
    return None


def check_invalid_ico_format(contract: Contract) -> FlagMatch | None:
    """Flag contracts where IČO is present but not in expected 8-digit format."""
    invalid_fields = {}
    for label, ico_value in [
        ("supplier_ico", contract.supplier_ico),
        ("buyer_ico", contract.buyer_ico),
    ]:
        if ico_value and ico_value.strip():
            digits = "".join(c for c in ico_value if c.isdigit())
            if len(digits) != 8:
                invalid_fields[label] = ico_value

    if invalid_fields:
        field_names = " a ".join(invalid_fields.keys())
        return FlagMatch(
            flag_code="INVALID_ICO_FORMAT",
            severity="low",
            reason=f"Neplatný formát IČO: {field_names}.",
            evidence=invalid_fields,
        )
    return None


def check_missing_buyer_ico(contract: Contract) -> FlagMatch | None:
    """Flag contracts with no buyer IČO."""
    if _is_empty(contract.buyer_ico):
        return FlagMatch(
            flag_code="MISSING_BUYER_ICO",
            severity="medium",
            reason="Zmluva neobsahuje IČO obstarávateľa.",
            evidence={"buyer_ico": contract.buyer_ico},
        )
    return None


# Ordered list of all flag checkers
FLAG_CHECKERS = [
    check_missing_price,
    check_zero_price,
    check_missing_supplier,
    check_missing_supplier_ico,
    check_invalid_ico_format,
    check_missing_buyer_ico,
]


def evaluate_contract(contract: Contract) -> list[FlagMatch]:
    """Evaluate all active flags against a single contract.

    Returns a list of FlagMatch objects for flags that fired.
    """
    matches = []
    for checker in FLAG_CHECKERS:
        result = checker(contract)
        if result is not None:
            matches.append(result)
    return matches


def compound_severity(flags: list[FlagMatch | dict]) -> str:
    """Compute compound severity from a list of flag matches.

    Rules:
    - 3+ flags → "high" (regardless of individual severities)
    - Otherwise → max individual severity
    - Empty list → "none"
    """
    if not flags:
        return "none"

    if len(flags) >= 3:
        return "high"

    severity_order = {"low": 1, "medium": 2, "high": 3}
    severities = []
    for f in flags:
        if isinstance(f, dict):
            severities.append(f.get("severity", "low"))
        else:
            severities.append(f.severity)

    return max(severities, key=lambda s: severity_order.get(s, 0))


def _get_or_create_flag_def(session: Session, flag_code: str) -> RiskFlag:
    """Get the RiskFlag ORM object for a flag code, creating it if needed."""
    stmt = select(RiskFlag).where(RiskFlag.flag_code == flag_code)
    existing = session.execute(stmt).scalar_one_or_none()
    if existing:
        return existing

    defn = get_flag_by_code(flag_code)
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
    return flag


def run_flag_evaluation(
    session: Session,
    run_id: int,
    batch_size: int = 500,
) -> tuple[int, int]:
    """Evaluate flags for all contracts and persist results.

    Implements the re-flagging lifecycle:
    1. For each contract, delete old flags (source_run_id != run_id)
    2. Evaluate all flags against current contract data
    3. Insert new ContractRiskFlag rows with current run_id

    Args:
        session: SQLAlchemy session
        run_id: Current ingestion run ID
        batch_size: How often to flush (controls memory usage)

    Returns:
        Tuple of (contracts_checked, flags_created)
    """
    contracts_checked = 0
    flags_created = 0

    # Ensure flag definitions exist in DB
    for code in FLAG_CATALOG:
        _get_or_create_flag_def(session, code)

    stmt = select(Contract).execution_options(yield_per=batch_size)
    contracts = session.execute(stmt).scalars()

    for contract in contracts:
        # Delete old flags for this contract from other runs
        session.execute(
            delete(ContractRiskFlag).where(
                ContractRiskFlag.crz_contract_id == contract.crz_contract_id,
                ContractRiskFlag.source_run_id != run_id,
            )
        )

        # Evaluate flags
        matches = evaluate_contract(contract)
        for match in matches:
            flag_def = _get_or_create_flag_def(session, match.flag_code)
            crf = ContractRiskFlag(
                crz_contract_id=contract.crz_contract_id,
                flag_id=flag_def.id,
                source_run_id=run_id,
                severity=match.severity,
                reason=match.reason,
                evidence_json=match.evidence,
            )
            session.add(crf)
            flags_created += 1

        contracts_checked += 1

        # Periodic flush to control memory
        if contracts_checked % batch_size == 0:
            session.flush()
            logger.info(
                f"Flag evaluation progress: {contracts_checked} contracts, {flags_created} flags"
            )

    session.execute(
        delete(ContractRiskFlag).where(
            ContractRiskFlag.source_run_id != run_id,
        )
    )

    session.flush()
    logger.info(
        f"Flag evaluation complete: {contracts_checked} contracts checked, "
        f"{flags_created} flags created"
    )
    return contracts_checked, flags_created
