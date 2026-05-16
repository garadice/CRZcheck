"""Flag definitions — single source of truth for all risk flags."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FlagDefinition:
    """Metadata for a single risk flag."""

    flag_code: str
    name: str  # Slovak display name
    description: str  # Slovak description
    severity_default: str  # "low" | "medium" | "high"
    methodology: str  # Explanation of logic for methodology page
    is_active: bool = True
    phase: str = "mvp"


FLAG_CATALOG: dict[str, FlagDefinition] = {
    "MISSING_PRICE": FlagDefinition(
        flag_code="MISSING_PRICE",
        name="Chýba cena",
        description="Zmluva neobsahuje žiadnu informáciu o cene (ani celková, ani zmluvná).",
        severity_default="medium",
        methodology=(
            "Flag je aktivovaný, ak price_total aj price_contract sú NULL. "
            "Niektoré zmluvy legitímne neobsahujú jednoduchú cenu "
            "(napr. rámcové dohody, bezodplatné prevody)."
        ),
    ),
    "ZERO_PRICE": FlagDefinition(
        flag_code="ZERO_PRICE",
        name="Nulová cena",
        description="Uvedená cena je nulová.",
        severity_default="low",
        methodology=(
            "Flag je aktivovaný, ak COALESCE(price_total, price_contract) = 0. "
            "Nulová cena môže byť legitímna (rámcové dohody, bezodplatné prevody, "
            "opravy, metadatové konvencie)."
        ),
    ),
    "MISSING_SUPPLIER": FlagDefinition(
        flag_code="MISSING_SUPPLIER",
        name="Chýba dodávateľ",
        description="Zmluva neobsahuje názov dodávateľa.",
        severity_default="medium",
        methodology=(
            "Flag je aktivovaný, ak supplier_name je NULL alebo prázdny reťazec. "
            "Niektoré záznamy môžu mať dodávateľa uvedeného inde "
            "alebo ísť o špeciálne typy zmlúv."
        ),
    ),
    "MISSING_SUPPLIER_ICO": FlagDefinition(
        flag_code="MISSING_SUPPLIER_ICO",
        name="Chýba IČO dodávateľa",
        description="Zmluva neobsahuje IČO dodávateľa.",
        severity_default="medium",
        methodology=(
            "Flag je aktivovaný, ak supplier_ico je NULL alebo prázdny reťazec. "
            "Zahraniční dodávatelia, fyzické osoby alebo špeciálne prípady "
            "nemusia mať slovenské IČO."
        ),
    ),
    "INVALID_ICO_FORMAT": FlagDefinition(
        flag_code="INVALID_ICO_FORMAT",
        name="Neplatný formát IČO",
        description="IČO dodávateľa alebo obstarávateľa nie je v očakávanom formáte (8 číslic).",
        severity_default="low",
        methodology=(
            "Flag je aktivovaný, ak je IČO prítomné, ale po normalizácii "
            "neobsahuje presne 8 číslic. Môže ísť o zahraničné identifikátory "
            "alebo chyby vo formátovaní."
        ),
    ),
    "MISSING_BUYER_ICO": FlagDefinition(
        flag_code="MISSING_BUYER_ICO",
        name="Chýba IČO obstarávateľa",
        description="Zmluva neobsahuje IČO obstarávateľa.",
        severity_default="medium",
        methodology=(
            "Flag je aktivovaný, ak buyer_ico je NULL alebo prázdny reťazec. "
            "Môže ísť o staršie záznamy alebo nezvyčajné verejné subjekty."
        ),
    ),
}


def get_flag_by_code(code: str) -> FlagDefinition:
    """Look up a flag definition by its code.

    Raises KeyError if the code is not found.
    """
    return FLAG_CATALOG[code]


def get_active_flags() -> list[FlagDefinition]:
    """Return all active flag definitions."""
    return [f for f in FLAG_CATALOG.values() if f.is_active]
