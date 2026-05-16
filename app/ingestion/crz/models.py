from __future__ import annotations

from pydantic import BaseModel, Field


class ParsedAttachment(BaseModel):
    attachment_id: str | None = None
    attachment_name: str | None = None
    scan_filename: str | None = None
    scan_size_bytes: int | None = None
    text_filename: str | None = None
    text_size_bytes: int | None = None


class ParsedContract(BaseModel):
    crz_contract_id: str
    title: str | None = None
    buyer_name: str | None = None
    supplier_name: str | None = None
    supplier_ico: str | None = None
    supplier_address: str | None = None
    buyer_ico: str | None = None
    buyer_address: str | None = None
    subject: str | None = None
    effective_date: str | None = None
    valid_until: str | None = None
    price_contract: str | None = None
    price_total: str | None = None
    publication_date: str | None = None
    contract_type: str | None = None
    contract_kind: str | None = None
    department: str | None = None
    contract_date: str | None = None
    attachments: list[ParsedAttachment] = Field(default_factory=list)
    unmapped_fields: dict[str, str] = Field(default_factory=dict)


class SchemaFingerprint(BaseModel):
    element_names: list[str]
    fingerprint: str
    contract_count: int


class ParseResult(BaseModel):
    export_date: str
    contracts: list[ParsedContract]
    schema_fingerprint: SchemaFingerprint | None = None
