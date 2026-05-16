from __future__ import annotations

import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


def parse_slovak_price(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    stripped = re.sub(r"\s*(EUR|€|eur)\s*$", "", stripped).strip()
    stripped = stripped.replace("\xa0", " ").replace(" ", "")

    # Handle European format: dots as thousand separators, comma as decimal
    if "," in stripped:
        parts = stripped.split(",")
        parts[0] = parts[0].replace(".", "")
        stripped = ".".join(parts)
    elif "." in stripped:
        # Could be "1.234" (thousand sep) or "1234.56" (decimal)
        parts = stripped.split(".")
        if len(parts) > 1 and len(parts[-1]) == 3 and all(len(p) == 3 for p in parts[:-1]):
            stripped = "".join(parts)

    try:
        return Decimal(stripped)
    except InvalidOperation:
        return None


def parse_crz_date(raw: str | None) -> date | None:
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped or stripped == "0000-00-00":
        return None
    try:
        return date.fromisoformat(stripped)
    except ValueError:
        return None


def parse_crz_datetime(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    try:
        return datetime.fromisoformat(stripped)
    except ValueError:
        return None


def normalize_ico(raw: str | None) -> str | None:
    if raw is None:
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    result = digits.zfill(8)
    if len(digits) > 8:
        logger.warning(f"Suspicious ICO length ({len(digits)} digits): {raw}")
    return result


def clean_name(raw: str | None) -> str | None:
    if raw is None:
        return None
    cleaned = raw.strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned if cleaned else None


def parse_int_or_none(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw.strip())
    except (ValueError, AttributeError):
        return None
