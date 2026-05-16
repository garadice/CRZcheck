from __future__ import annotations


def make_detail_url(contract_id: str) -> str:
    return f"https://www.crz.gov.sk/index.php?ID={contract_id}"


def make_attachment_url(filename: str | None) -> str | None:
    if not filename:
        return None
    return f"https://www.crz.gov.sk/data/att/{filename}"
