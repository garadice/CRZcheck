from __future__ import annotations

import hashlib
import io
from pathlib import Path

from lxml import etree

from app.ingestion.crz.models import (
    ParsedAttachment,
    ParsedContract,
    ParseResult,
    SchemaFingerprint,
)

FIELD_MAP: dict[str, str] = {
    "ID": "crz_contract_id",
    "nazov": "title",
    "zs1": "buyer_name",
    "zs2": "supplier_name",
    "ico": "supplier_ico",
    "sidlo": "supplier_address",
    "ico1": "buyer_ico",
    "sidlo1": "buyer_address",
    "predmet": "subject",
    "datum_ucinnost": "effective_date",
    "datum_platnost_do": "valid_until",
    "suma_zmluva": "price_contract",
    "suma_spolu": "price_total",
    "datum_zverejnene": "publication_date",
    "typ": "contract_type",
    "druh": "contract_kind",
    "rezort": "department",
}

UNMAPPED_TAGS: set[str] = {
    "id",
    "poznamka",
    "stav",
    "potv_ziadost",
    "potv_datum",
    "zdroj",
    "text_ucinnost",
    "potvrdenie",
    "popis",
    "ref",
    "internapozn",
    "popis_predmetu",
    "poznamka_zmena",
    "uvo",
    "chan",
}

ATTACHMENT_FIELD_MAP: dict[str, str] = {
    "ID": "attachment_id",
    "nazov": "attachment_name",
    "dokument": "scan_filename",
    "dokument1": "text_filename",
    "velkost": "scan_size_bytes",
    "velkost1": "text_size_bytes",
}

MAX_XML_SIZE = 100 * 1024 * 1024  # 100 MB — guard against ZIP bombs / malformed data


def compute_schema_fingerprint(element_names: list[str]) -> str:
    canonical = ",".join(sorted(element_names))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _text(element: etree._Element) -> str | None:
    text = element.text
    if text is None or text.strip() == "":
        return None
    return text.strip()


def _parse_attachment(priloha: etree._Element) -> ParsedAttachment:
    data: dict[str, str | int | None] = {}
    for child in priloha:
        tag = etree.QName(child).localname
        if tag in ATTACHMENT_FIELD_MAP:
            field = ATTACHMENT_FIELD_MAP[tag]
            value = _text(child)
            if field in ("scan_size_bytes", "text_size_bytes") and value is not None:
                try:
                    data[field] = int(value)
                except ValueError:
                    data[field] = None
            else:
                data[field] = value
    return ParsedAttachment(**data)


def parse_xml(source: Path | str | bytes) -> ParseResult:
    if isinstance(source, Path):
        raw = source.read_bytes()
    elif isinstance(source, str):
        raw = source.encode("utf-8")
    else:
        raw = source

    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]

    if len(raw) > MAX_XML_SIZE:
        raise ValueError(
            f"XML payload too large ({len(raw):,} bytes > {MAX_XML_SIZE:,} bytes). "
            "Possible ZIP bomb or corrupted file."
        )

    contracts: list[ParsedContract] = []
    export_date = ""
    all_element_names: set[str] = set()
    root_date: str | None = None

    _safe = dict(
        resolve_entities=False,
        no_network=True,
        dtd_validation=False,
        load_dtd=False,
        huge_tree=False,
    )

    context = etree.iterparse(
        io.BytesIO(raw), events=("start",), tag="zmluvy", recover=True, **_safe
    )
    for _event, elem in context:
        root_date = elem.get("datum")
        break

    context = etree.iterparse(io.BytesIO(raw), events=("end",), tag="zmluva", recover=True, **_safe)
    for _event, elem in context:
        contract_data: dict[str, str | None] = {}
        unmapped: dict[str, str] = {}
        attachments: list[ParsedAttachment] = []

        for child in elem:
            tag = etree.QName(child).localname
            all_element_names.add(tag)

            if tag == "prilohy":
                for priloha in child.findall("priloha"):
                    attachments.append(_parse_attachment(priloha))
                continue

            text_val = _text(child)

            if tag in FIELD_MAP:
                contract_data[FIELD_MAP[tag]] = text_val
            elif tag in UNMAPPED_TAGS and text_val is not None:
                unmapped[tag] = text_val

        if root_date:
            contract_data["contract_date"] = root_date

        contract = ParsedContract(
            attachments=attachments,
            unmapped_fields=unmapped,
            **{k: v for k, v in contract_data.items() if v is not None},
        )
        contracts.append(contract)
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]

    if root_date:
        export_date = root_date

    schema_fp = None
    if all_element_names:
        names = sorted(all_element_names)
        fp = compute_schema_fingerprint(names)
        schema_fp = SchemaFingerprint(
            element_names=names, fingerprint=fp, contract_count=len(contracts)
        )

    return ParseResult(export_date=export_date, contracts=contracts, schema_fingerprint=schema_fp)
