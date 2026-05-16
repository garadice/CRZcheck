from __future__ import annotations

import re

LEGAL_FORM_SUFFIXES = [
    "s.r.o.",
    "spol. s r.o.",
    "a.s.",
    "v.o.s.",
    "k.s.",
    "š.p.",
    "o.z.",
    "príspevková organizácia",
    "rozpočtová organizácia",
    "nadácia",
    "n.o.",
    "živnostník",
]


def is_probable_natural_person(name: str | None, ico: str | None) -> bool:
    if not name or not name.strip():
        return False
    has_ico = ico and ico.strip() and ico.strip() != "0"
    if has_ico:
        return False
    name_lower = name.strip().lower()
    return all(suffix not in name_lower for suffix in LEGAL_FORM_SUFFIXES)


def normalize_entity_name(name: str | None) -> str | None:
    if not name:
        return None
    normalized = name.strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized if normalized else None
